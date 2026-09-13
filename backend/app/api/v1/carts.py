from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.schemas.common import Message
from app.schemas.order import CartAddRequest, CartOut, CartUpdateRequest, CouponApplyRequest
from app.services import cart_service, shipping_service

router = APIRouter(prefix="/carts", tags=["carts"])
Db = Annotated[Session, Depends(get_db)]


def serialize_cart(db: Session, cart, postal_code: str | None = None) -> CartOut:
    lines, coupon, discount, totals = cart_service.compute_cart(db, cart, postal_code)
    items = []
    block_reasons: list[str] = []
    for ln in lines:
        variant = ln.variant
        snapshot = ln.extra.get("snapshot_price", variant.price_paise)
        available = variant.is_preorder or ln.is_preorder or variant.available_qty >= ln.qty
        if not available:
            block_reasons.append(f"{variant.sku}: only {variant.available_qty} left in stock")
        items.append(
            {
                "id": ln.extra["cart_item_id"],
                "variant_id": variant.id,
                "product_id": variant.product_id,
                "product_name": variant.product.name,
                "variant_name": f"Size {variant.size.value}",
                "sku": variant.sku,
                "size": variant.size.value,
                "image_url": next((i.url for i in variant.product.images if i.is_primary), None),
                "qty": ln.qty,
                "unit_price_paise_snapshot": snapshot,
                "current_unit_price_paise": variant.price_paise,
                "price_changed": snapshot != variant.price_paise,
                "is_available": available,
                "is_preorder": ln.is_preorder,
                "available_qty": variant.available_qty,
                "line_total_paise": ln.line_gross_paise,
            }
        )
    if any(i["price_changed"] for i in items):
        block_reasons.append("Prices changed since items were added; review the new totals.")
    return CartOut(
        id=cart.id,
        items=items,
        coupon_code=coupon.code if coupon else None,
        totals=totals,
        checkout_blocked=bool(block_reasons),
        block_reasons=block_reasons,
    )


@router.get("/me", response_model=CartOut)
def get_cart(user: CurrentUser, db: Db):
    cart = cart_service.get_or_create_cart(db, user)
    return serialize_cart(db, cart)


@router.post("/me/items", response_model=CartOut, status_code=201)
def add_item(payload: CartAddRequest, user: CurrentUser, db: Db):
    cart = cart_service.add_item(db, user, payload.variant_id, payload.qty)
    db.commit()
    return serialize_cart(db, cart)


@router.patch("/me/items/{item_id}", response_model=CartOut)
def update_item(item_id: str, payload: CartUpdateRequest, user: CurrentUser, db: Db):
    cart = cart_service.update_item_qty(db, user, item_id, payload.qty)
    db.commit()
    return serialize_cart(db, cart)


@router.delete("/me/items/{item_id}", response_model=CartOut)
def remove_item(item_id: str, user: CurrentUser, db: Db):
    cart = cart_service.remove_item(db, user, item_id)
    db.commit()
    return serialize_cart(db, cart)


@router.delete("/me", response_model=Message)
def clear_cart(user: CurrentUser, db: Db):
    cart_service.clear_cart(db, user)
    db.commit()
    return Message(message="Cart cleared.")


@router.post("/me/coupon", response_model=CartOut)
def apply_coupon(payload: CouponApplyRequest, user: CurrentUser, db: Db):
    cart = cart_service.apply_coupon(db, user, payload.code)
    db.commit()
    return serialize_cart(db, cart)


@router.delete("/me/coupon", response_model=CartOut)
def remove_coupon(user: CurrentUser, db: Db):
    cart = cart_service.remove_coupon(db, user)
    db.commit()
    return serialize_cart(db, cart)


@router.get("/me/shipping-estimate", response_model=dict)
def shipping_estimate(postal_code: str, user: CurrentUser, db: Db):
    # The cart is deliberately not loaded: this endpoint quotes a rate for a PIN
    # code, and shipping is state/PIN-based rather than weight- or value-based,
    # so the cart contents cannot change the answer. Fetching it here only
    # created a cart row as a side effect of a read-only GET.
    result = shipping_service.get_provider().check_serviceability(db, postal_code)
    return {
        "postal_code": postal_code,
        "serviceable": result.serviceable,
        "shipping_charge_paise": result.charge_paise,
        "estimated_delivery_days": result.estimated_delivery_days,
        "reason": result.reason,
    }
