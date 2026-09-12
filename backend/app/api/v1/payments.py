from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.exceptions import NotFoundError
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.ops import PaymentOut, RetryPaymentRequest, VerifyPaymentRequest
from app.schemas.order import PaymentSessionOut
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["payments"])
Db = Annotated[Session, Depends(get_db)]


def _own_order(db: Session, order_id: str, user) -> Order:
    order = db.get(Order, order_id)
    if order is None or (user.role.value == "customer" and order.customer_id != user.id):
        raise NotFoundError("Order not found.")
    return order


@router.post("/session", response_model=PaymentSessionOut)
def create_session(order_id: str, user: CurrentUser, db: Db):
    order = _own_order(db, order_id, user)
    session = payment_service.create_payment_session(db, order)
    db.commit()
    return session


@router.post("/verify", response_model=dict)
def verify(payload: VerifyPaymentRequest, user: CurrentUser, db: Db):
    order = _own_order(db, payload.order_id, user)
    payment_service.verify_frontend_payment(db, order, payload.razorpay_payment_id, payload.razorpay_signature)
    db.commit()
    return {"status": "paid", "order_number": order.number}


@router.post("/retry", response_model=PaymentSessionOut)
def retry(payload: RetryPaymentRequest, user: CurrentUser, db: Db):
    order = _own_order(db, payload.order_id, user)
    session = payment_service.retry_payment(db, order)
    db.commit()
    return session


@router.post("/mock-capture/{order_id}", response_model=dict)
def mock_capture(order_id: str, user: CurrentUser, db: Db):
    """Dev/test only: simulates the gateway capturing payment when Razorpay keys
    are absent (mock gateway). Refuses to exist in live mode."""
    from app.core.config import settings as env_settings
    from app.core.exceptions import ConflictError

    if env_settings.razorpay_enabled:
        raise ConflictError("Mock capture is disabled when Razorpay is configured.")
    order = _own_order(db, order_id, user)
    payment = payment_service.latest_payment(db, order)
    payment_service.confirm_payment_success(
        db, order,
        provider_payment_id=f"mock_pay_{order.number}",
        gateway_meta={"mock_capture": True},
    )
    db.commit()
    return {"status": "paid", "order_number": order.number, "payment_id": payment.id}


@router.get("/order/{order_id}", response_model=list[PaymentOut])
def list_payments(order_id: str, user: CurrentUser, db: Db):
    order = _own_order(db, order_id, user)
    return db.scalars(select(Payment).where(Payment.order_id == order.id)).all()
