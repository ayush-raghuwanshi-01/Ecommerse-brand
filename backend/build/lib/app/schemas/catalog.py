from datetime import datetime

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: str
    name: str
    slug: str
    is_active: bool


class CategoryCreate(BaseModel):
    name: str
    slug: str | None = None
    parent_id: str | None = None


class CollectionOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str | None


class CollectionCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None


class ProductImageOut(ORMModel):
    id: str
    url: str
    alt_text: str | None
    sort_order: int
    is_primary: bool
    variant_id: str | None


class ProductImageCreate(BaseModel):
    url: str | None = None          # provide url or upload a file
    alt_text: str | None = None
    sort_order: int = 0
    is_primary: bool = False
    variant_id: str | None = None


class VariantOut(ORMModel):
    id: str
    sku: str
    size: str
    price_paise: int
    gst_percentage: float
    stock_qty: int
    reserved_qty: int
    available_qty: int
    is_active: bool
    is_purchasable: bool
    is_preorder: bool
    availability: str

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, data):
        if isinstance(data, dict):
            return data
        out = {c.name: getattr(data, c.name) for c in data.__table__.columns}
        out["available_qty"] = data.available_qty
        out["availability"] = data.availability(3).value
        return out

    @field_serializer("gst_percentage")
    def _gst(self, v, _info):  # Numeric comes back as Decimal
        return float(v)


class VariantCreate(BaseModel):
    sku: str
    size: str
    price_paise: int = Field(ge=0)
    gst_percentage: float = Field(default=5.0, ge=0, le=100)
    stock_qty: int = Field(default=0, ge=0)
    is_active: bool = True
    is_purchasable: bool = True
    is_preorder: bool = False
    sort_order: int = 0


class VariantUpdate(BaseModel):
    price_paise: int | None = Field(default=None, ge=0)
    gst_percentage: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    is_purchasable: bool | None = None
    is_preorder: bool | None = None
    sort_order: int | None = None


class ProductOut(ORMModel):
    id: str
    name: str
    slug: str
    short_description: str | None
    description: str | None
    status: str
    product_type: str | None
    fabric: str | None
    fit_info: str | None
    care_instructions: str | None
    size_guide: str | None
    base_price_paise: int
    gst_percentage: float
    is_preorder: bool
    preorder_open: bool
    preorder_fulfillment_note: str | None
    preorder_limit: int | None
    restock_expected_at: datetime | None
    restock_note: str | None
    is_sale_item: bool
    seo_title: str | None
    seo_description: str | None
    category: CategoryOut | None = None
    collection: CollectionOut | None = None
    variants: list[VariantOut] = []
    images: list[ProductImageOut] = []
    created_at: datetime
    updated_at: datetime

    @field_serializer("gst_percentage")
    def _gst(self, v, _info):
        return float(v)


class ProductListItem(ORMModel):
    id: str
    name: str
    slug: str
    short_description: str | None
    status: str
    base_price_paise: int
    is_preorder: bool
    preorder_open: bool
    primary_image_url: str | None = None
    sizes_available: list[str] = []


class ProductCreate(BaseModel):
    name: str
    slug: str | None = None
    short_description: str | None = None
    description: str | None = None
    status: str = "draft"
    product_type: str | None = None
    category_id: str | None = None
    collection_id: str | None = None
    fabric: str | None = None
    fit_info: str | None = None
    care_instructions: str | None = None
    size_guide: str | None = None
    base_price_paise: int = Field(ge=0)
    gst_percentage: float = Field(default=5.0, ge=0, le=100)
    is_sale_item: bool = False
    is_preorder: bool = False
    preorder_start_at: datetime | None = None
    preorder_end_at: datetime | None = None
    preorder_fulfillment_note: str | None = None
    preorder_limit: int | None = Field(default=None, ge=1)
    restock_expected_at: datetime | None = None
    restock_note: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    tag_slugs: list[str] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    short_description: str | None = None
    description: str | None = None
    status: str | None = None
    product_type: str | None = None
    category_id: str | None = None
    collection_id: str | None = None
    fabric: str | None = None
    fit_info: str | None = None
    care_instructions: str | None = None
    size_guide: str | None = None
    base_price_paise: int | None = Field(default=None, ge=0)
    gst_percentage: float | None = Field(default=None, ge=0, le=100)
    is_sale_item: bool | None = None
    is_preorder: bool | None = None
    preorder_start_at: datetime | None = None
    preorder_end_at: datetime | None = None
    preorder_fulfillment_note: str | None = None
    preorder_limit: int | None = None
    restock_expected_at: datetime | None = None
    restock_note: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
