"""Warehouses and the inventory movement ledger."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.types import UTCDateTime
from app.models.base import Timestamps, UUIDPk, enum_col


class AdjustmentType(StrEnum):
    # Manual adjustment reasons (business-specified)
    increase = "increase"
    decrease = "decrease"
    return_ = "return"
    damage = "damage"
    defect = "defect"
    correction = "correction"
    # System movements (same ledger, full traceability)
    reserve = "reserve"
    release = "release"
    sale = "sale"


class Warehouse(UUIDPk, Timestamps, Base):
    __tablename__ = "warehouses"

    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), default="IN")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class InventoryAdjustment(UUIDPk, Base):
    """Append-only movement ledger. Stock numbers are always derivable from it."""

    __tablename__ = "inventory_adjustments"

    variant_id: Mapped[str] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    adjustment_type: Mapped[AdjustmentType] = mapped_column(enum_col(AdjustmentType))
    qty_before: Mapped[int] = mapped_column(Integer)
    qty_change: Mapped[int] = mapped_column(Integer)
    qty_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(300))
    reference_type: Mapped[str | None] = mapped_column(String(40))  # order / return / manual
    reference_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    variant = relationship("ProductVariant")
    user = relationship("User")
