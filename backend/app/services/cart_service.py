"""Authenticated customer carts: one active cart per customer.

Cart stores price snapshots; checkout always recalculates from current prices
and surfaces any difference to the customer before payment.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.cart import Cart, CartItem
from app.models.catalog import ProductVariant
from app.models.commerce import Coupon
from app.models.user import User
from app.services import catalog_service, coupon_service, pricing_service, shipping_service
from app.services.pricing_service import PricedLine


def get_or_create_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()
    return cart


def _variant_with_product(db: Session, variant_id: str) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise NotFoundError("Product variant not found.")
    _ = variant.product  # eager-load product for rules
    return variant


def add_item(db: Session, user: User, variant_id: str, qty: int) -> Cart:
    cart = get_or_create_cart(db, user)
    variant = _variant_with_product(db, variant_id)
    catalog_service.assert_purchasable(db, variant.product, variant)
    existing = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.variant_id == variant_id)
    )
    if existing:
        existing.qty = min(existing.qty + qty, 10)
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                variant_id=variant.id,
                qty=qty,
                unit_price_paise_snapshot=variant.price_paise,
            )
        )
    db.flush()
    return cart


def update_item_qty(db: Session, user: User, item_id: str, qty: int) -> Cart:
    cart = get_or_create_cart(db, user)
    item = db.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise NotFoundError("Cart item not found.")
    if qty <= 0:
        db.delete(item)
    else:
        item.qty = min(qty, 10)
    db.flush()
    return cart


def remove_item(db: Session, user: User, item_id: str) -> Cart:
    cart = get_or_create_cart(db, user)
    item = db.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise NotFoundError("Cart item not found.")
    db.delete(item)
    db.flush()
    return cart


def clear_cart(db: Session, user: User) -> Cart:
    cart = get_or_create_cart(db, user)
    for item in list(cart.items):
        db.delete(item)
    cart.coupon_id = None
    db.flush()
    return cart


def apply_coupon(db: Session, user: User, code: str) -> Cart:
    cart = get_or_create_cart(db, user)
    coupon = coupon_service.get_coupon_by_code(db, code)
    if coupon is None:
        raise ValidationError("Coupon not found.", details={"code": code})
    lines = build_lines(db, cart)
    coupon_service.validate_coupon(db, coupon, lines, customer_id=user.id)
    cart.coupon_id = coupon.id
    db.flush()
    return cart


def remove_coupon(db: Session, user: User) -> Cart:
    cart = get_or_create_cart(db, user)
    cart.coupon_id = None
    db.flush()
    return cart


def build_lines(db: Session, cart: Cart) -> list[PricedLine]:
    lines: list[PricedLine] = []
    for item in cart.items:
        variant = _variant_with_product(db, item.variant_id)
        lines.append(
            PricedLine(
                variant=variant,
                qty=item.qty,
                unit_price_paise=variant.price_paise,  # current price always wins
                is_preorder=bool(variant.is_preorder or variant.product.preorder_open),
                extra={
                    "cart_item_id": item.id,
                    "snapshot_price": item.unit_price_paise_snapshot,
                },
            )
        )
    return lines


def coupon_for(db: Session, cart: Cart) -> Coupon | None:
    return db.get(Coupon, cart.coupon_id) if cart.coupon_id else None


def compute_cart(db: Session, cart: Cart, postal_code: str | None = None):
    """Returns (lines, coupon, discount, totals, issues)."""
    lines = build_lines(db, cart)
    coupon = coupon_for(db, cart)
    discount = 0
    if coupon and lines:
        try:
            discount = coupon_service.validate_coupon(db, coupon, lines, customer_id=cart.user_id)
        except Exception:
            coupon = None  # coupon became invalid since apply-time; drop it silently in preview
            discount = 0
            for ln in lines:
                ln.eligible_for_coupon = True
    state = ""
    if postal_code:
        res = shipping_service.get_provider().check_serviceability(db, postal_code)
        shipping = res.charge_paise if res.serviceable else 0
    else:
        shipping = 0
    totals = pricing_service.finalize(lines, discount_paise=discount, shipping_paise=shipping)
    return lines, coupon, discount, totals
