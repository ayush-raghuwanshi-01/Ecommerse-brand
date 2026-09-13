"""Coupons, PIN-code/shipping rules, restock alerts, bulk enquiries,
notifications, audit log, business settings, counters."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.types import UTCDateTime
from app.models.base import Timestamps, UUIDPk, enum_col


class CouponType(StrEnum):
    fixed = "fixed"          # flat amount off (paise)
    percentage = "percentage"  # percent off eligible subtotal (value = percent * 100)


class Coupon(UUIDPk, Timestamps, Base):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    discount_type: Mapped[CouponType] = mapped_column(enum_col(CouponType), default=CouponType.fixed)
    discount_value: Mapped[int] = mapped_column(Integer)  # paise, or percent*100
    max_discount_paise: Mapped[int | None] = mapped_column(Integer)
    min_order_paise: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eligible_product_ids: Mapped[list | None] = mapped_column(JSON)  # null = entire catalogue

    usages: Mapped[list["CouponUsage"]] = relationship(back_populates="coupon", cascade="all, delete-orphan")


class CouponUsage(UUIDPk, Base):
    __tablename__ = "coupon_usages"

    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    coupon: Mapped[Coupon] = relationship(back_populates="usages")


class ShippingRuleKind(StrEnum):
    serviceable = "serviceable"
    blocked = "blocked"
    rate_pincode = "rate_pincode"
    rate_state = "rate_state"


class ShippingRule(UUIDPk, Timestamps, Base):
    """PIN-code ranges / state based serviceability and rates.

    denylist mode (default): everything in India serviceable unless blocked.
    allowlist mode: only ranges marked serviceable.
    """

    __tablename__ = "shipping_rules"

    kind: Mapped[ShippingRuleKind] = mapped_column(enum_col(ShippingRuleKind))
    pincode_from: Mapped[str | None] = mapped_column(String(10))
    pincode_to: Mapped[str | None] = mapped_column(String(10))
    state: Mapped[str | None] = mapped_column(String(120))
    charge_paise: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def matches_pincode(self, pin: str) -> bool:
        if self.pincode_from is None:
            return False
        lo = self.pincode_from
        hi = self.pincode_to or self.pincode_from
        return lo <= pin <= hi


class RestockStatus(StrEnum):
    active = "active"
    notified = "notified"
    cancelled = "cancelled"


class RestockSubscription(UUIDPk, Base):
    __tablename__ = "restock_subscriptions"

    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[RestockStatus] = mapped_column(enum_col(RestockStatus), default=RestockStatus.active)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    variant = relationship("ProductVariant")


class BulkEnquiryStatus(StrEnum):
    new = "new"
    contacted = "contacted"
    in_progress = "in_progress"
    quoted = "quoted"
    closed = "closed"
    cancelled = "cancelled"


class BulkEnquiry(UUIDPk, Timestamps, Base):
    __tablename__ = "bulk_enquiries"

    name: Mapped[str] = mapped_column(String(160))
    business_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(20))
    product_interest: Mapped[str] = mapped_column(String(300))
    estimated_qty: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BulkEnquiryStatus] = mapped_column(enum_col(BulkEnquiryStatus), default=BulkEnquiryStatus.new)
    staff_notes: Mapped[str | None] = mapped_column(Text)


class NotificationChannel(StrEnum):
    email = "email"
    whatsapp = "whatsapp"
    sms = "sms"
    internal = "internal"


class NotificationStatus(StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"

    recipient: Mapped[str] = mapped_column(String(320))
    channel: Mapped[NotificationChannel] = mapped_column(enum_col(NotificationChannel))
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[NotificationStatus] = mapped_column(enum_col(NotificationStatus), default=NotificationStatus.pending)
    provider_message_id: Mapped[str | None] = mapped_column(String(120))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class AuditLog(UUIDPk, Base):
    """Append-only. No update/delete paths exist in the application layer."""

    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    user = relationship("User")


class BusinessSetting(Base):
    """Runtime-tunable business configuration (admin-managed)."""

    __tablename__ = "business_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Counter(Base):
    """Sequential, transaction-safe counters (order numbers)."""

    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
