"""Refunds: manager/admin approved, gateway-executed, idempotent completion.

Staff can never initiate or approve refunds. Refunds always target the
original payment method via the gateway abstraction.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.models.order import Order, PaymentStatus
from app.models.payment import Payment, PaymentRecordStatus
from app.models.returns import Refund, RefundStatus
from app.models.user import User
from app.services import audit_service, notification_service, payment_service


def _assert_approver(actor: User) -> None:
    if actor.role.value not in ("manager", "admin"):
        raise PermissionDeniedError("Only a manager or admin can approve refunds.")


def request_refund(
    db: Session,
    order: Order,
    amount_paise: int,
    actor: User,
    *,
    return_request=None,
    reason: str | None = None,
) -> Refund:
    """Create a refund in `requested` state. Idempotent per order+return."""
    existing = db.scalar(
        select(Refund).where(
            Refund.order_id == order.id,
            Refund.return_request_id == (return_request.id if return_request else None),
            Refund.status.notin_([RefundStatus.rejected, RefundStatus.failed]),
        )
    )
    if existing:
        return existing
    payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id, Payment.status == PaymentRecordStatus.paid.value)
        .order_by(Payment.created_at.desc())
    )
    refund = Refund(
        order_id=order.id,
        return_request_id=return_request.id if return_request else None,
        payment_id=payment.id if payment else None,
        amount_paise=amount_paise,
        status=RefundStatus.requested,
        initiated_by=actor.id,
    )
    db.add(refund)
    db.flush()
    audit_service.record(
        db,
        user=actor,
        action="refund.request",
        entity_type="refund",
        entity_id=refund.id,
        after={"order": order.number, "amount_paise": amount_paise, "reason": reason},
    )
    return refund


def decide_refund(db: Session, refund: Refund, *, actor: User, approve: bool, note: str | None) -> Refund:
    _assert_approver(actor)
    if refund.status != RefundStatus.requested:
        raise ConflictError("Refund is not awaiting approval.", details={"status": refund.status.value})
    if not approve:
        refund.status = RefundStatus.rejected
        refund.failure_reason = note
        audit_service.record(
            db,
            user=actor,
            action="refund.reject",
            entity_type="refund",
            entity_id=refund.id,
            after={"note": note},
        )
        db.flush()
        return refund

    refund.status = RefundStatus.approved
    refund.approved_by = actor.id
    audit_service.record(
        db,
        user=actor,
        action="refund.approve",
        entity_type="refund",
        entity_id=refund.id,
        after={"note": note},
    )
    return initiate_refund(db, refund, actor=actor)


def initiate_refund(db: Session, refund: Refund, *, actor: User) -> Refund:
    """Push the refund to the gateway. Idempotent: skips when already processing."""
    if refund.status in (RefundStatus.processing, RefundStatus.completed):
        return refund
    order = db.get(Order, refund.order_id)
    payment = db.get(Payment, refund.payment_id) if refund.payment_id else None
    if payment is None or payment.status != PaymentRecordStatus.paid.value:
        refund.status = RefundStatus.failed
        refund.failure_reason = "No captured payment to refund."
        db.flush()
        return refund

    gateway = payment_service.get_gateway()
    provider_refund_id = gateway.create_refund(
        payment.provider_payment_id or payment.provider_order_id or "",
        refund.amount_paise,
        {"order_number": order.number, "refund_id": refund.id},
    )
    refund.provider_refund_id = provider_refund_id
    refund.status = RefundStatus.processing
    db.flush()
    if order.customer:
        notification_service.notify(
            db,
            event_type="refund_initiated",
            recipient=order.customer.email,
            payload={"order_number": order.number, "amount_paise": refund.amount_paise},
        )
    # Mock gateway completes synchronously; Razorpay completes via webhook.
    from app.core.config import settings

    if not settings.razorpay_enabled:
        complete_refund(db, refund, gateway_meta={"mock": True})
    return refund


def complete_refund(db: Session, refund: Refund, *, gateway_meta: dict | None = None) -> Refund:
    """Idempotent completion (webhook-safe)."""
    if refund.status == RefundStatus.completed:
        return refund
    refund.status = RefundStatus.completed
    refund.completed_at = utcnow()
    refund.gateway_metadata = gateway_meta or refund.gateway_metadata

    order = db.get(Order, refund.order_id)
    payment = db.get(Payment, refund.payment_id) if refund.payment_id else None
    if payment:
        total_paid = payment.amount_paise
        refunded_now = refund.amount_paise + sum(
            r.amount_paise
            for r in db.scalars(
                select(Refund).where(
                    Refund.payment_id == payment.id,
                    Refund.status == RefundStatus.completed,
                    Refund.id != refund.id,
                )
            )
        )
        payment.status = (
            PaymentRecordStatus.refunded.value
            if refunded_now >= total_paid
            else PaymentRecordStatus.partially_refunded.value
        )
        order.payment_status = (
            PaymentStatus.refunded if refunded_now >= total_paid else PaymentStatus.partially_refunded
        )
    if order and order.customer:
        notification_service.notify(
            db,
            event_type="refund_completed",
            recipient=order.customer.email,
            payload={"order_number": order.number, "amount_paise": refund.amount_paise},
        )

    audit_service.record(
        db,
        user=None,
        action="refund.complete",
        entity_type="refund",
        entity_id=refund.id,
        after={"amount_paise": refund.amount_paise, "gateway": gateway_meta},
    )
    db.flush()
    return refund
