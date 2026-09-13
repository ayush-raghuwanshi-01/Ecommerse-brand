"""Customer carts (one active cart per customer) and cart items."""

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class Cart(UUIDPk, Timestamps, Base):
    __tablename__ = "carts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    coupon_id: Mapped[str | None] = mapped_column(ForeignKey("coupons.id"))

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.created_at"
    )
    coupon = relationship("Coupon")


class CartItem(UUIDPk, Timestamps, Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_paise_snapshot: Mapped[int] = mapped_column(Integer)  # price at add-time; recalculated at checkout

    cart: Mapped[Cart] = relationship(back_populates="items")
    variant = relationship("ProductVariant")
