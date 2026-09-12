"""Payments, webhook event log (idempotency), checkout idempotency keys."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import UTCDateTime
from app.core.database import Base, utcnow
from app.models.base import Timestamps, UUIDPk, enum_col
from app.models.order import Order


class PaymentProvider(str, Enum):
    razorpay = "razorpay"
    mock = "mock"


class PaymentRecordStatus(str, Enum):
    created = "created"
    pending = "pending"
    authorized = "authorized"
    paid = "paid"
    failed = "failed"
    expired = "expired"
    partially_refunded = "partially_refunded"
    refunded = "refunded"


class Payment(UUIDPk, Timestamps, Base):
    __tablename__ = "payments"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProvider] = mapped_column(enum_col(PaymentProvider))
    provider_order_id: Mapped[str | None] = mapped_column(String(120), index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    method: Mapped[str] = mapped_column(String(40))  # razorpay | upi | cod
    status: Mapped[PaymentRecordStatus] = mapped_column(enum_col(PaymentRecordStatus), default=PaymentRecordStatus.created)
    webhook_event_id: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    failure_reason: Mapped[str | None] = mapped_column(String(300))

    order: Mapped[Order] = relationship(back_populates="payments")


class WebhookEvent(UUIDPk, Base):
    """One row per provider event id → idempotent webhook processing."""

    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(String(40))
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[dict] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class IdempotencyKey(UUIDPk, Base):
    """Guards duplicate checkout submissions (header Idempotency-Key)."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    path: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_code: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())

