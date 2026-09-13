"""Orders, order items (immutable snapshots), status history."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.types import UTCDateTime
from app.models.base import Timestamps, UUIDPk, enum_col

if TYPE_CHECKING:
    # Import-for-typing only: `Payment` lives in a sibling module that itself
    # references Order, so importing it at runtime would be circular. SQLAlchemy
    # resolves the string annotation through its mapper registry instead.
    from app.models.payment import Payment


class OrderSource(StrEnum):
    website = "website"
    whatsapp = "whatsapp"
    instagram = "instagram"
    physical_store = "physical_store"
    staff_manual = "staff_manual"


class PaymentMethod(StrEnum):
    razorpay = "razorpay"  # cards / netbanking / wallets via gateway
    upi = "upi"  # UPI via Razorpay
    cod = "cod"


class PaymentStatus(StrEnum):
    created = "created"
    pending = "pending"
    pending_cod = "pending_cod"
    authorized = "authorized"
    paid = "paid"
    failed = "failed"
    expired = "expired"
    partially_refunded = "partially_refunded"
    refunded = "refunded"


class OrderStatus(StrEnum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    processing = "processing"
    packed = "packed"
    shipped = "shipped"
    delivered = "delivered"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    return_requested = "return_requested"
    return_approved = "return_approved"
    returned = "returned"
    completed = "completed"


PACKED_AND_BEYOND = {
    OrderStatus.packed,
    OrderStatus.shipped,
    OrderStatus.delivered,
    OrderStatus.return_requested,
    OrderStatus.return_approved,
    OrderStatus.returned,
    OrderStatus.completed,
}


class FulfillmentStatus(StrEnum):
    unfulfilled = "unfulfilled"
    partially_fulfilled = "partially_fulfilled"
    fulfilled = "fulfilled"
    returned = "returned"


class CancellationReason(StrEnum):
    ordered_by_mistake = "ordered_by_mistake"
    changed_mind = "changed_mind"
    payment_issue = "payment_issue"
    delivery_delay = "delivery_delay"
    customer_request = "customer_request"
    inventory_issue = "inventory_issue"
    other = "other"


class Order(UUIDPk, Timestamps, Base):
    __tablename__ = "orders"

    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_staff_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    order_source: Mapped[OrderSource] = mapped_column(
        enum_col(OrderSource), default=OrderSource.website, index=True
    )

    payment_method: Mapped[PaymentMethod] = mapped_column(enum_col(PaymentMethod))
    payment_status: Mapped[PaymentStatus] = mapped_column(
        enum_col(PaymentStatus), default=PaymentStatus.created, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        enum_col(OrderStatus), default=OrderStatus.pending_payment, index=True
    )
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        enum_col(FulfillmentStatus), default=FulfillmentStatus.unfulfilled
    )

    currency: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0)
    shipping_paise: Mapped[int] = mapped_column(Integer, default=0)
    tax_paise: Mapped[int] = mapped_column(Integer, default=0)  # GST included in prices
    grand_total_paise: Mapped[int] = mapped_column(Integer, default=0)

    coupon_id: Mapped[str | None] = mapped_column(ForeignKey("coupons.id"))
    billing_address: Mapped[dict] = mapped_column(JSON)
    shipping_address: Mapped[dict] = mapped_column(JSON)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)

    is_preorder: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reserved_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    cancellation_reason: Mapped[CancellationReason | None] = mapped_column(enum_col(CancellationReason))
    cancellation_requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancellation_decision_note: Mapped[str | None] = mapped_column(String(500))

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.created_at"
    )
    customer = relationship("User", foreign_keys=[customer_id])
    created_by_staff = relationship("User", foreign_keys=[created_by_staff_id])


class OrderItem(UUIDPk, Base):
    """Immutable price/name/SKU snapshot — historical orders never drift."""

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[str] = mapped_column(ForeignKey("product_variants.id"))
    product_name: Mapped[str] = mapped_column(String(160))
    variant_name: Mapped[str] = mapped_column(String(80))
    sku: Mapped[str] = mapped_column(String(64))
    product_image_url: Mapped[str | None] = mapped_column(String(500))
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    gst_percentage: Mapped[float] = mapped_column(Numeric(5, 2))
    tax_paise: Mapped[int] = mapped_column(Integer, default=0)
    qty: Mapped[int] = mapped_column(Integer)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer)
    is_preorder: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_fulfillment_note: Mapped[str | None] = mapped_column(String(500))

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusHistory(UUIDPk, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    order: Mapped[Order] = relationship(back_populates="history")
