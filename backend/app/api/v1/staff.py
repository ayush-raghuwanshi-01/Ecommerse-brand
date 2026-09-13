"""Staff order desk: create orders on behalf of customers (WhatsApp / Instagram /
physical store / phone), plus fulfillment helpers."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.orders import serialize_order
from app.core.database import get_db
from app.core.deps import StaffUser
from app.core.exceptions import NotFoundError
from app.models.order import OrderSource
from app.models.user import User
from app.schemas.order import PaymentSessionOut, StaffOrderCreateRequest
from app.services import order_service, payment_service

router = APIRouter(prefix="/staff", tags=["staff"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/orders", response_model=dict, status_code=201)
def create_order(payload: StaffOrderCreateRequest, staff: StaffUser, db: Db):
    customer = None
    if payload.customer_id:
        customer = db.get(User, payload.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
    order = order_service.staff_create_order(
        db,
        staff=staff,
        customer=customer,
        new_customer=payload.new_customer,
        source=OrderSource(payload.order_source),
        lines_spec=[line.model_dump() for line in payload.lines],
        shipping_address=payload.shipping_address.model_dump(),
        billing_address=payload.billing_address.model_dump() if payload.billing_address else None,
        payment_method=payload.payment_method,
        internal_notes=payload.internal_notes,
        customer_notes=payload.customer_notes,
        coupon_code=payload.coupon_code,
    )
    session = None
    if payload.payment_method in ("razorpay", "upi"):
        session = payment_service.create_payment_session(db, order)
    db.commit()
    return {"order": serialize_order(db, order, staff), "payment_session": session}


@router.get("/orders/{order_id}/payment-session", response_model=PaymentSessionOut)
def order_payment_session(order_id: str, staff: StaffUser, db: Db):
    from app.models.order import Order

    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    session = payment_service.create_payment_session(db, order)
    db.commit()
    return session
