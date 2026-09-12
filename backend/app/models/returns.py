"""Shipments (courier abstraction data) and returns/exchanges/refunds."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import UTCDateTime
from app.core.database import Base, utcnow
from app.models.base import Timestamps, UUIDPk, enum_col


class ShipmentStatus(str, Enum):
    pending = "pending"
    ready_to_ship = "ready_to_ship"
    picked_up = "picked_up"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    delivery_failed = "delivery_failed"
    returned_to_origin = "returned_to_origin"
    cancelled = "cancelled"


class Shipment(UUIDPk, Timestamps, Base):
    __tablename__ = "shipments"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(20), default="forward")  # forward | return (reverse pickup)
    provider: Mapped[str] = mapped_column(String(60), default="manual")
    tracking_number: Mapped[str | None] = mapped_column(String(120))
    tracking_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ShipmentStatus] = mapped_column(enum_col(ShipmentStatus), default=ShipmentStatus.pending)
    pickup_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    shipped_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    return_tracking_number: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    order = relationship("Order")


class ReturnType(str, Enum):
    refund = "refund"
    size_exchange = "size_exchange"
    product_exchange = "product_exchange"
    replacement = "replacement"


class ReturnReason(str, Enum):
    size_issue = "size_issue"
    wrong_product = "wrong_product"
    damaged_product = "damaged_product"
    defective_product = "defective_product"
    changed_mind = "changed_mind"
    quality_issue = "quality_issue"
    other = "other"


COMPANY_PAYS_RETURN_SHIPPING = {
    ReturnReason.wrong_product,
    ReturnReason.damaged_product,
    ReturnReason.defective_product,
}


class ReturnStatus(str, Enum):
    requested = "requested"
    under_review = "under_review"
    approved = "approved"
    pickup_scheduled = "pickup_scheduled"
    picked_up = "picked_up"
    received = "received"
    inspected = "inspected"
    approved_for_refund = "approved_for_refund"
    approved_for_exchange = "approved_for_exchange"
    rejected = "rejected"
    completed = "completed"


class ReturnRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "return_requests"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[str | None] = mapped_column(ForeignKey("order_items.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    return_type: Mapped[ReturnType] = mapped_column(enum_col(ReturnType))
    reason: Mapped[ReturnReason] = mapped_column(enum_col(ReturnReason))
    status: Mapped[ReturnStatus] = mapped_column(enum_col(ReturnStatus), default=ReturnStatus.requested, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    staff_notes: Mapped[str | None] = mapped_column(Text)
    company_pays_shipping: Mapped[bool] = mapped_column(Boolean, default=False)
    exchange_variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    order = relationship("Order")
    order_item = relationship("OrderItem")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="return_request")


class RefundStatus(str, Enum):
    requested = "requested"
    approved = "approved"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class Refund(UUIDPk, Timestamps, Base):
    __tablename__ = "refunds"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    return_request_id: Mapped[str | None] = mapped_column(ForeignKey("return_requests.id"))
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[RefundStatus] = mapped_column(enum_col(RefundStatus), default=RefundStatus.requested)
    provider_refund_id: Mapped[str | None] = mapped_column(String(120))
    gateway_metadata: Mapped[dict | None] = mapped_column(JSON)
    initiated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_reason: Mapped[str | None] = mapped_column(String(300))

    order = relationship("Order")
    return_request: Mapped[ReturnRequest | None] = relationship(back_populates="refunds")
    payment = relationship("Payment")
