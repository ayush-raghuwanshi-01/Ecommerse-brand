"""Payment gateways: Razorpay (live) + Mock (dev/test), webhook idempotency,
payment retry with cooldown, and the payment→order→inventory commit chain.

The frontend success page is never trusted: signatures are verified and the
gateway is re-queried (live mode) before money is considered captured.
"""

import hashlib
import hmac
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.logging import get_logger
from app.models.order import Order, OrderStatus, PaymentMethod, PaymentStatus
from app.models.payment import Payment, PaymentProvider, PaymentRecordStatus, WebhookEvent
from app.models.user import User
from app.services import inventory_service, notification_service, order_service

log = get_logger("payments")

RAZORPAY_BASE = "https://api.razorpay.com/v1"


class PaymentGateway(ABC):
    name: PaymentProvider

    @abstractmethod
    def create_order(self, amount_paise: int, receipt: str, notes: dict) -> str: ...

    @abstractmethod
    def fetch_payment_status(self, provider_payment_id: str) -> str: ...

    @abstractmethod
    def create_refund(self, provider_payment_id: str, amount_paise: int, notes: dict) -> str: ...

    @abstractmethod
    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class MockGateway(PaymentGateway):
    """Deterministic gateway for dev/tests. Never used when Razorpay keys exist."""

    name = PaymentProvider.mock

    def create_order(self, amount_paise: int, receipt: str, notes: dict) -> str:
        return f"mock_order_{uuid4().hex[:14]}"

    def fetch_payment_status(self, provider_payment_id: str) -> str:
        return "captured"

    def create_refund(self, provider_payment_id: str, amount_paise: int, notes: dict) -> str:
        return f"mock_refund_{uuid4().hex[:12]}"

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return hmac.compare_digest(self._sig(f"{order_id}|{payment_id}"), signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return hmac.compare_digest(
            hmac.new(settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest(),
            signature,
        )

    def _sig(self, payload: str) -> str:
        return hmac.new(settings.razorpay_key_secret.encode() or b"mock", payload.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def sign_checkout(order_id: str, payment_id: str) -> str:
        key = settings.razorpay_key_secret.encode() or b"mock"
        return hmac.new(key, f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def sign_webhook(raw_body: bytes) -> str:
        return hmac.new(settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()


class RazorpayGateway(PaymentGateway):  # pragma: no cover - requires live keys
    name = PaymentProvider.razorpay

    def __init__(self) -> None:
        self._auth = (settings.razorpay_key_id, settings.razorpay_key_secret)

    def _post(self, path: str, payload: dict) -> dict:
        r = httpx.post(f"{RAZORPAY_BASE}{path}", json=payload, auth=self._auth, timeout=15)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str) -> dict:
        r = httpx.get(f"{RAZORPAY_BASE}{path}", auth=self._auth, timeout=15)
        r.raise_for_status()
        return r.json()

    def create_order(self, amount_paise: int, receipt: str, notes: dict) -> str:
        data = self._post(
            "/orders",
            {"amount": amount_paise, "currency": settings.default_currency, "receipt": receipt, "notes": notes},
        )
        return data["id"]

    def fetch_payment_status(self, provider_payment_id: str) -> str:
        return self._get(f"/payments/{provider_payment_id}")["status"]

    def create_refund(self, provider_payment_id: str, amount_paise: int, notes: dict) -> str:
        data = self._post(
            f"/payments/{provider_payment_id}/refund", {"amount": amount_paise, "notes": notes}
        )
        return data["id"]

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac.new(
            settings.razorpay_key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def get_gateway() -> PaymentGateway:
    return RazorpayGateway() if settings.razorpay_enabled else MockGateway()


def latest_payment(db: Session, order: Order) -> Payment:
    payment = db.scalar(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc())
    )
    if payment is None:
        raise NotFoundError("No payment record for this order.")
    return payment


def create_payment_session(db: Session, order: Order) -> dict:
    if order.status != OrderStatus.pending_payment:
        raise ConflictError("This order is not awaiting payment.", details={"status": order.status.value})
    if order.payment_method == PaymentMethod.cod:
        raise ConflictError("COD orders do not use online payment sessions.")
    payment = latest_payment(db, order)
    if payment.status == PaymentRecordStatus.paid.value:
        raise ConflictError("This order is already paid.")
    gateway = get_gateway()
    if not payment.provider_order_id:
        provider_order_id = gateway.create_order(
            order.grand_total_paise,
            order.number,
            {"order_number": order.number, "customer": order.customer_id or ""},
        )
        payment.provider_order_id = provider_order_id
        payment.status = PaymentRecordStatus.pending
        db.flush()
    return {
        "provider": payment.provider,
        "provider_order_id": payment.provider_order_id,
        "key_id": settings.razorpay_key_id or "rzp_test_mock",
        "amount_paise": order.grand_total_paise,
        "currency": order.currency,
        "order_number": order.number,
        "mock": not settings.razorpay_enabled,
        "notes": {"order_number": order.number},
    }


def retry_payment(db: Session, order: Order) -> dict:
    """Eligible ~2 min after the last failed attempt (no hot retries)."""
    if order.status != OrderStatus.pending_payment:
        raise ConflictError("Only pending-payment orders can retry payment.")
    payment = latest_payment(db, order)
    if payment.status not in (
        PaymentRecordStatus.failed.value,
        PaymentRecordStatus.expired.value,
        PaymentRecordStatus.created.value,
        PaymentRecordStatus.pending.value,
    ):
        raise ConflictError("This payment is not retryable.", details={"status": payment.status})
    from app.services import settings_service

    cooldown = int(settings_service.get_setting(db, "payment_retry_cooldown_seconds") or 120)
    age = (utcnow() - payment.updated_at).total_seconds()
    if payment.status in (PaymentRecordStatus.failed.value, PaymentRecordStatus.expired.value) and age < cooldown:
        raise ConflictError(
            "Please wait before retrying payment.",
            details={"retry_after_seconds": int(cooldown - age)},
        )
    payment.provider_order_id = None  # fresh gateway order
    payment.status = PaymentRecordStatus.created
    db.flush()
    return create_payment_session(db, order)


def confirm_payment_success(
    db: Session,
    order: Order,
    *,
    provider_payment_id: str,
    gateway_meta: dict | None = None,
    webhook_event_id: str | None = None,
) -> Order:
    """Idempotent: paid payments are left untouched."""
    payment = latest_payment(db, order)
    if payment.status == PaymentRecordStatus.paid.value:
        return order
    if order.status not in (OrderStatus.pending_payment, OrderStatus.cancel_requested):
        if order.status in (OrderStatus.cancelled,):
            # Paid after cancellation: mark paid; refund flow handles money.
            payment.status = PaymentRecordStatus.paid
            payment.provider_payment_id = provider_payment_id
            order.payment_status = PaymentStatus.paid
            db.flush()
            return order
        raise ConflictError("Order is not in a payable state.", details={"status": order.status.value})

    payment.status = PaymentRecordStatus.paid
    payment.provider_payment_id = provider_payment_id
    payment.webhook_event_id = webhook_event_id
    payment.metadata_json = gateway_meta or payment.metadata_json
    order.payment_status = PaymentStatus.paid
    if order.status == OrderStatus.pending_payment:
        order.status = OrderStatus.confirmed
        order.confirmed_at = utcnow()
        db.add(
            order_service.OrderStatusHistory(
                order_id=order.id,
                from_status=OrderStatus.pending_payment.value,
                to_status=OrderStatus.confirmed.value,
                changed_by=None,
                note="payment captured",
            )
        )
    order.reserved_until = None
    for item in order.items:
        variant = inventory_service.get_variant(db, item.variant_id)
        inventory_service.commit_reservation(
            db, variant, item.qty, reference_id=order.id, is_preorder_line=item.is_preorder
        )
    if order.customer:
        notification_service.notify(
            db, event_type="payment_successful", recipient=order.customer.email,
            payload={"order_number": order.number, "subject": f"Payment received for {order.number}"},
        )
    db.flush()
    return order


def mark_payment_failed(db: Session, order: Order, *, reason: str, webhook_event_id: str | None = None) -> None:
    payment = latest_payment(db, order)
    if payment.status == PaymentRecordStatus.paid.value:
        return
    payment.status = PaymentRecordStatus.failed
    payment.failure_reason = reason[:300]
    payment.webhook_event_id = webhook_event_id
    order.payment_status = PaymentStatus.failed
    if order.customer:
        notification_service.notify(
            db, event_type="payment_failed", recipient=order.customer.email,
            payload={"order_number": order.number, "reason": reason},
        )
    db.flush()


def verify_frontend_payment(db: Session, order: Order, payment_id: str, signature: str) -> Order:
    """Convenience verifier for the checkout return-flow; webhook remains authoritative."""
    payment = latest_payment(db, order)
    gateway = get_gateway()
    if not gateway.verify_checkout_signature(payment.provider_order_id or "", payment_id, signature):
        raise PermissionDeniedError("Payment signature verification failed.")
    if settings.razorpay_enabled:  # pragma: no cover - live only
        status = gateway.fetch_payment_status(payment_id)
        if status != "captured":
            raise ConflictError("Gateway has not captured this payment.", details={"gateway_status": status})
    return confirm_payment_success(
        db, order, provider_payment_id=payment_id,
        gateway_meta={"verified_via": "checkout_signature"},
    )


def process_webhook(db: Session, raw_body: bytes, signature: str) -> dict:
    gateway = get_gateway()
    if not gateway.verify_webhook_signature(raw_body, signature):
        raise PermissionDeniedError("Invalid webhook signature.")
    import json

    payload = json.loads(raw_body)
    event_id = payload.get("id") or ""
    event_type = payload.get("event") or "unknown"
    if not event_id:
        raise ValidationError("Webhook payload missing event id.")
    existing = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    if existing:
        return {"status": "duplicate", "event_id": event_id}
    event = WebhookEvent(
        provider=gateway.name.value, event_id=event_id, event_type=event_type, payload_json=payload
    )
    db.add(event)
    db.flush()

    entity = payload.get("payload", {}).get("payment", {}).get("entity") or {}
    provider_order_id = entity.get("order_id")
    payment = db.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id))
    order = db.get(Order, payment.order_id) if payment else None

    if event_type == "payment.captured" and order:
        confirm_payment_success(
            db, order,
            provider_payment_id=entity.get("id", ""),
            gateway_meta={"webhook": event_type, "raw": entity},
            webhook_event_id=event_id,
        )
    elif event_type == "payment.failed" and order:
        mark_payment_failed(db, order, reason=entity.get("error_description") or "payment failed",
                            webhook_event_id=event_id)
    elif event_type.startswith("refund.") and payment:
        from app.models.returns import Refund
        from app.services import refund_service

        refund = db.scalar(
            select(Refund).where(Refund.provider_refund_id == entity.get("id"))
        )
        if refund:
            refund_service.complete_refund(db, refund, gateway_meta={"webhook": event_type})
    event.processed_at = utcnow()
    db.flush()
    return {"status": "processed", "event_id": event_id, "event_type": event_type}


def collect_cod(db: Session, order: Order, *, actor: User, method_note: str | None) -> Order:
    if order.payment_method != PaymentMethod.cod:
        raise ConflictError("Only COD orders can be marked collected.")
    if order.payment_status == PaymentStatus.paid:
        raise ConflictError("Payment already collected.")
    payment = latest_payment(db, order)
    payment.status = PaymentRecordStatus.paid
    payment.metadata_json = {"collected_by": actor.id, "method_note": method_note, "collected_at": utcnow().isoformat()}
    order.payment_status = PaymentStatus.paid
    from app.services import audit_service

    audit_service.record(
        db, user=actor, action="payment.status_change", entity_type="order", entity_id=order.id,
        before={"payment_status": "pending_cod"}, after={"payment_status": "paid", "note": method_note},
    )
    db.flush()
    return order
