"""Checkout: preview (price-change surfacing), transactional place-order with
Idempotency-Key, PIN-code serviceability check."""

import hashlib
import json
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.carts import serialize_cart
from app.api.v1.orders import serialize_order
from app.core.database import get_db, utcnow
from app.core.deps import CurrentUser
from app.models.payment import IdempotencyKey
from app.schemas.order import (
    CheckoutPreview,
    PincodeCheck,
    PincodeCheckOut,
    PlaceOrderOut,
    PlaceOrderRequest,
)
from app.services import cart_service, payment_service, shipping_service
from app.services.order_service import place_order as place_order_service

router = APIRouter(prefix="/checkout", tags=["checkout"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/pincode-check", response_model=PincodeCheckOut)
def pincode_check(payload: PincodeCheck, db: Db):
    result = shipping_service.get_provider().check_serviceability(db, payload.postal_code)
    charge = result.charge_paise
    if payload.subtotal_paise is not None:
        charge = shipping_service.get_provider().get_shipping_rate(
            db, payload.postal_code, "", payload.subtotal_paise
        )
    return PincodeCheckOut(
        postal_code=payload.postal_code,
        serviceable=result.serviceable,
        shipping_charge_paise=charge,
        estimated_delivery_days=result.estimated_delivery_days,
        reason=result.reason,
    )


@router.get("/preview", response_model=CheckoutPreview)
def preview(user: CurrentUser, db: Db, postal_code: str | None = None):
    cart = cart_service.get_or_create_cart(db, user)
    serialized = serialize_cart(db, cart, postal_code)
    shipping = None
    if postal_code:
        result = shipping_service.get_provider().check_serviceability(db, postal_code)
        shipping = PincodeCheckOut(
            postal_code=postal_code,
            serviceable=result.serviceable,
            shipping_charge_paise=result.charge_paise,
            estimated_delivery_days=result.estimated_delivery_days,
            reason=result.reason,
        )
    return CheckoutPreview(
        items=serialized.items,
        totals=serialized.totals,
        price_changes=[
            {"sku": i.sku, "was_paise": i.unit_price_paise_snapshot, "now_paise": i.current_unit_price_paise}
            for i in serialized.items
            if i.price_changed
        ],
        unavailable_items=[
            {"sku": i.sku, "requested": i.qty, "available": i.available_qty}
            for i in serialized.items
            if not i.is_available
        ],
        checkout_blocked=serialized.checkout_blocked,
        block_reasons=serialized.block_reasons,
        shipping=shipping,
    )


@router.post("/orders", response_model=PlaceOrderOut, status_code=201)
def place_order(
    payload: PlaceOrderRequest,
    user: CurrentUser,
    db: Db,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    cart = cart_service.get_or_create_cart(db, user)

    if idempotency_key:
        request_hash = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True).encode()).hexdigest()
        existing = db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key, IdempotencyKey.user_id == user.id
            )
        )
        if existing:
            if existing.request_hash != request_hash:
                from app.core.exceptions import ConflictError

                raise ConflictError("Idempotency-Key reused with a different payload.")
            if existing.response_json:
                return PlaceOrderOut.model_validate(existing.response_json)
    else:
        existing = None
        request_hash = ""

    order = place_order_service(
        db,
        customer=user,
        cart=cart,
        shipping_address_id=payload.shipping_address_id,
        billing_address_id=payload.billing_address_id,
        payment_method=payload.payment_method,
        customer_notes=payload.customer_notes,
    )
    db.flush()

    session = None
    requires_payment = payload.payment_method != "cod"
    if requires_payment:
        session = payment_service.create_payment_session(db, order)

    out = PlaceOrderOut(
        order=serialize_order(db, order, viewer=user),
        payment_session=session,
        requires_payment=requires_payment,
    )

    if idempotency_key:
        db.add(
            IdempotencyKey(
                key=idempotency_key,
                user_id=user.id,
                path=request.url.path,
                request_hash=request_hash,
                response_code=201,
                response_json=out.model_dump(mode="json"),
                expires_at=utcnow() + timedelta(hours=24),
            )
        )
    db.commit()
    return out
