"""Catalog: categories, collections, products, size variants, images."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.types import UTCDateTime
from app.models.base import Timestamps, UUIDPk, enum_col

product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class ProductStatus(StrEnum):
    draft = "draft"
    upcoming = "upcoming"
    active = "active"
    out_of_stock = "out_of_stock"
    archived = "archived"


class VariantSize(StrEnum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"


class VariantAvailability(StrEnum):
    available = "available"
    low_stock = "low_stock"
    out_of_stock = "out_of_stock"
    upcoming = "upcoming"
    disabled = "disabled"


class Category(UUIDPk, Timestamps, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Collection(UUIDPk, Timestamps, Base):
    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Tag(UUIDPk, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class Product(UUIDPk, Timestamps, Base):
    """A clothing design. Prices are integer paise, GST-inclusive."""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(160), index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    short_description: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProductStatus] = mapped_column(
        enum_col(ProductStatus), default=ProductStatus.draft, index=True
    )
    product_type: Mapped[str | None] = mapped_column(String(80))  # overcoat, trench, jacket...
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    collection_id: Mapped[str | None] = mapped_column(ForeignKey("collections.id"))
    fabric: Mapped[str | None] = mapped_column(String(255))
    fit_info: Mapped[str | None] = mapped_column(Text)
    care_instructions: Mapped[str | None] = mapped_column(Text)
    size_guide: Mapped[str | None] = mapped_column(Text)
    base_price_paise: Mapped[int] = mapped_column(Integer)
    gst_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=5.0)
    is_sale_item: Mapped[bool] = mapped_column(Boolean, default=False)  # returnable, not cash-refundable

    # Pre-orders
    is_preorder: Mapped[bool] = mapped_column(Boolean, default=False)
    preorder_start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    preorder_end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    preorder_fulfillment_note: Mapped[str | None] = mapped_column(String(500))
    preorder_limit: Mapped[int | None] = mapped_column(Integer)

    # Restock visibility for out-of-stock products
    restock_expected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    restock_note: Mapped[str | None] = mapped_column(String(300))

    # SEO
    seo_title: Mapped[str | None] = mapped_column(String(200))
    seo_description: Mapped[str | None] = mapped_column(String(400))

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.sort_order"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.sort_order"
    )
    category: Mapped[Category | None] = relationship()
    collection: Mapped[Collection | None] = relationship()
    tags: Mapped[list[Tag]] = relationship(secondary=product_tags)

    @property
    def preorder_open(self) -> bool:
        now = utcnow()
        if not self.is_preorder:
            return False
        if self.preorder_start_at and now < self.preorder_start_at:
            return False
        if self.preorder_end_at and now > self.preorder_end_at:
            return False
        return True

    @property
    def publicly_visible(self) -> bool:
        if self.status in (ProductStatus.active, ProductStatus.upcoming):
            return True
        if self.status == ProductStatus.out_of_stock:
            return self.restock_expected_at is not None or bool(self.restock_note)
        return False


class ProductVariant(UUIDPk, Timestamps, Base):
    """Size variant. Stock lives here (finished-goods, single warehouse in v1)."""

    __tablename__ = "product_variants"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size: Mapped[VariantSize] = mapped_column(enum_col(VariantSize))
    color: Mapped[str | None] = mapped_column(String(60))  # reserved for future color support
    price_paise: Mapped[int] = mapped_column(Integer)
    gst_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=5.0)

    stock_qty: Mapped[int] = mapped_column(Integer, default=0)  # on-hand sellable
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0)  # held by unpaid/pending orders
    sold_qty: Mapped[int] = mapped_column(Integer, default=0)
    damaged_qty: Mapped[int] = mapped_column(Integer, default=0)
    defective_qty: Mapped[int] = mapped_column(Integer, default=0)
    returned_qty: Mapped[int] = mapped_column(Integer, default=0)

    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"))  # multi-warehouse ready
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_purchasable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_preorder: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def available_qty(self) -> int:
        return max(self.stock_qty - self.reserved_qty, 0)

    def availability(self, low_stock_threshold: int = 3) -> VariantAvailability:
        if not self.is_active:
            return VariantAvailability.disabled
        if (self.product is not None and self.product.status == ProductStatus.upcoming) or (
            self.is_preorder and self.available_qty <= 0
        ):
            return VariantAvailability.upcoming
        if self.available_qty <= 0:
            return VariantAvailability.out_of_stock
        if self.available_qty <= low_stock_threshold:
            return VariantAvailability.low_stock
        return VariantAvailability.available


class ProductImage(UUIDPk, Timestamps, Base):
    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str | None] = mapped_column(String(300))
    alt_text: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    product: Mapped[Product] = relationship(back_populates="images")
