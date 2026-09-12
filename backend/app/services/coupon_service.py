"""Coupon validation + discount computation.

Validated at three points: cart apply, checkout preview, and order creation.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.exceptions import CouponError
from app.models.commerce import Coupon, CouponType, CouponUsage
from app.services.pricing_service import PricedLine


def _fail(code: str, message: str, details: dict | None = None) -> None:
    raise CouponError(message, details={"code": code, **(details or {})})


def validate_coupon(
    db: Session,
    coupon: Coupon,
    lines: list[PricedLine],
    *,
    customer_id: str | None,
) -> int:
    """Return discount in paise for the given lines. Raises CouponError."""
    now = utcnow()
    if not coupon.is_active:
        _fail("COUPON_INACTIVE", "This coupon is no longer active.")
    if coupon.starts_at and now < coupon.starts_at:
        _fail("COUPON_NOT_STARTED", "This coupon is not active yet.")
    if coupon.expires_at and now > coupon.expires_at:
        _fail("COUPON_EXPIRED", "This coupon has expired.")

    eligible = lines
    if coupon.eligible_product_ids:
        eligible = [ln for ln in lines if ln.variant.product_id in coupon.eligible_product_ids]
        for ln in lines:
            ln.eligible_for_coupon = ln.variant.product_id in coupon.eligible_product_ids
        if not eligible:
            _fail("COUPON_NOT_APPLICABLE", "This coupon does not apply to items in your cart.")

    eligible_subtotal = sum(ln.line_gross_paise for ln in eligible)
    all_subtotal = sum(ln.line_gross_paise for ln in lines)
    if coupon.min_order_paise and all_subtotal < coupon.min_order_paise:
        _fail(
            "COUPON_MIN_ORDER",
            f"Add items worth ₹{coupon.min_order_paise / 100:,.0f} more to use this coupon.",
            details={"min_order_paise": coupon.min_order_paise, "subtotal_paise": all_subtotal},
        )

    if coupon.usage_limit is not None:
        count = db.query(CouponUsage).filter_by(coupon_id=coupon.id).count()
        if count >= coupon.usage_limit:
            _fail("COUPON_USAGE_LIMIT", "This coupon has reached its usage limit.")
    if coupon.per_customer_limit and customer_id:
        count = db.query(CouponUsage).filter_by(coupon_id=coupon.id, customer_id=customer_id).count()
        if count >= coupon.per_customer_limit:
            _fail("COUPON_CUSTOMER_LIMIT", "You have already used this coupon the maximum number of times.")

    if coupon.discount_type == CouponType.fixed:
        discount = min(coupon.discount_value, eligible_subtotal)
    else:  # percentage stored as percent * 100
        discount = int(eligible_subtotal * coupon.discount_value // 10000)
        if coupon.max_discount_paise:
            discount = min(discount, coupon.max_discount_paise)
        discount = min(discount, eligible_subtotal)
    return discount


def record_usage(db: Session, coupon: Coupon, order_id: str, customer_id: str | None) -> None:
    db.add(CouponUsage(coupon_id=coupon.id, order_id=order_id, customer_id=customer_id))


def get_coupon_by_code(db: Session, code: str) -> Coupon | None:
    return db.scalar(select(Coupon).where(Coupon.code == code.upper().strip()))
