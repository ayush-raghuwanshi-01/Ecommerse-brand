from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core import uploads
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ManagerUser, StaffUser
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.pagination import PageParams, page_meta, paginate
from app.models.catalog import (
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    Tag,
)
from app.schemas.catalog import (
    ProductCreate,
    ProductImageCreate,
    ProductImageOut,
    ProductListItem,
    ProductOut,
    ProductUpdate,
    VariantCreate,
    VariantOut,
    VariantUpdate,
)
from app.schemas.common import Page
from app.services import audit_service, catalog_service, storage_service
from app.services.settings_service import get_setting

log = get_logger("products")

router = APIRouter(prefix="/products", tags=["products"])
Db = Annotated[Session, Depends(get_db)]


def _list_item(product: Product) -> ProductListItem:
    item = ProductListItem.model_validate(product)
    item.primary_image_url = catalog_service.primary_image_url(product)
    item.sizes_available = [
        v.size.value for v in product.variants if v.availability(3).value in ("available", "low_stock")
    ]
    return item


@router.get("", response_model=Page[ProductListItem])
def list_products(
    params: Annotated[PageParams, Depends()],
    db: Db,
    status: str | None = None,
    collection: str | None = None,
    category: str | None = None,
    preorder: bool | None = None,
):
    """Public catalogue: active + upcoming + restock-flagged out-of-stock."""
    stmt = select(Product).options(joinedload(Product.variants), joinedload(Product.images))
    if status:
        stmt = stmt.where(Product.status == status)
    else:
        stmt = stmt.where(
            or_(
                Product.status.in_([ProductStatus.active, ProductStatus.upcoming]),
                (Product.status == ProductStatus.out_of_stock)
                & or_(Product.restock_expected_at.is_not(None), Product.restock_note.is_not(None)),
            )
        )
    if collection:
        stmt = stmt.where(Product.collection.has(**{"slug": collection}))
    if category:
        stmt = stmt.where(Product.category.has(**{"slug": category}))
    if preorder is not None:
        stmt = stmt.where(Product.is_preorder.is_(preorder))
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like)))
    items, total = paginate(
        db, stmt, params, sort_columns={"created_at": Product.created_at, "name": Product.name}
    )
    return Page(items=[_list_item(p) for p in items], meta=page_meta(params, total))


# ── Staff/manager views & management ────────────────────────────────────────
@router.get("/internal/all", response_model=Page[ProductOut], include_in_schema=False)
def list_all_products(params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db):
    stmt = select(Product).options(joinedload(Product.variants), joinedload(Product.images))
    items, total = paginate(db, stmt, params, sort_columns={"created_at": Product.created_at})
    return Page(items=items, meta=page_meta(params, total))


@router.get("/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Db):
    product = catalog_service.get_public_product(db, slug)
    out = ProductOut.model_validate(product)
    for v in out.variants:
        orm_v = next(o for o in product.variants if o.id == v.id)
        v.availability = orm_v.availability(int(get_setting(db, "low_stock_threshold") or 3)).value
    return out


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, manager: ManagerUser, db: Db, request: Request):
    slug = payload.slug or _slugify(payload.name)
    if db.scalar(select(Product).where(Product.slug == slug)):
        raise ValidationError("Slug already exists.", details={"slug": slug})
    product = Product(**payload.model_dump(exclude={"tag_slugs", "slug"}), slug=slug)
    for tag_slug in payload.tag_slugs:
        tag = db.scalar(select(Tag).where(Tag.slug == tag_slug))
        if tag is None:
            tag = Tag(name=tag_slug, slug=tag_slug)
            db.add(tag)
        product.tags.append(tag)
    db.add(product)
    db.flush()
    audit_service.record(
        db,
        user=manager,
        action="product.create",
        entity_type="product",
        entity_id=product.id,
        after={"name": product.name, "slug": slug},
        request=request,
    )
    db.commit()
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdate, manager: ManagerUser, db: Db, request: Request):
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    before = {c: getattr(product, c) for c in payload.model_dump(exclude_unset=True)}
    price_before = product.base_price_paise
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.flush()
    audit_service.record(
        db,
        user=manager,
        action="product.update",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    if (
        "base_price_paise" in payload.model_dump(exclude_unset=True)
        and price_before != product.base_price_paise
    ):
        audit_service.record(
            db,
            user=manager,
            action="product.price_change",
            entity_type="product",
            entity_id=product.id,
            before={"base_price_paise": price_before},
            after={"base_price_paise": product.base_price_paise},
            request=request,
        )
    db.commit()
    return product


@router.post("/{product_id}/publish", response_model=ProductOut)
def publish_product(product_id: str, manager: ManagerUser, db: Db, request: Request):
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    before = product.status.value
    product.status = ProductStatus.active
    audit_service.record(
        db,
        user=manager,
        action="product.publish",
        entity_type="product",
        entity_id=product.id,
        before={"status": before},
        after={"status": "active"},
        request=request,
    )
    db.commit()
    return product


@router.post("/{product_id}/archive", response_model=ProductOut)
def archive_product(product_id: str, manager: ManagerUser, db: Db, request: Request):
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    before = product.status.value
    product.status = ProductStatus.archived
    audit_service.record(
        db,
        user=manager,
        action="product.archive",
        entity_type="product",
        entity_id=product.id,
        before={"status": before},
        after={"status": "archived"},
        request=request,
    )
    db.commit()
    return product


# ── Variants ────────────────────────────────────────────────────────────────
@router.post("/{product_id}/variants", response_model=VariantOut, status_code=201)
def create_variant(product_id: str, payload: VariantCreate, manager: ManagerUser, db: Db, request: Request):
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    if db.scalar(select(ProductVariant).where(ProductVariant.sku == payload.sku)):
        raise ValidationError("SKU already exists.", details={"sku": payload.sku})
    variant = ProductVariant(product_id=product.id, **payload.model_dump())
    db.add(variant)
    db.flush()
    audit_service.record(
        db,
        user=manager,
        action="variant.update",
        entity_type="product_variant",
        entity_id=variant.id,
        after=payload.model_dump(),
        request=request,
    )
    db.commit()
    out = VariantOut.model_validate(variant)
    out.availability = variant.availability().value
    return out


@router.patch("/variants/{variant_id}", response_model=VariantOut)
def update_variant(variant_id: str, payload: VariantUpdate, manager: ManagerUser, db: Db, request: Request):
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise NotFoundError("Variant not found.")
    before = {k: getattr(variant, k) for k in payload.model_dump(exclude_unset=True)}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, key, value)
    db.flush()
    audit_service.record(
        db,
        user=manager,
        action="variant.update",
        entity_type="product_variant",
        entity_id=variant.id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    db.commit()
    out = VariantOut.model_validate(variant)
    out.availability = variant.availability().value
    return out


# ── Images (object storage, never in PostgreSQL) ────────────────────────────
@router.post("/{product_id}/images", response_model=ProductImageOut, status_code=201)
def add_image(product_id: str, payload: ProductImageCreate, manager: ManagerUser, db: Db):
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    url, key = payload.url, None
    if not url:
        raise ValidationError("Provide a url (or use the upload endpoint).")
    image = ProductImage(
        product_id=product.id,
        url=url,
        storage_key=key,
        alt_text=payload.alt_text,
        sort_order=payload.sort_order,
        is_primary=payload.is_primary,
        variant_id=payload.variant_id,
    )
    if image.is_primary:
        for i in product.images:
            i.is_primary = False
    db.add(image)
    db.flush()
    db.commit()
    return image


@router.post("/{product_id}/images/upload", response_model=ProductImageOut, status_code=201)
def upload_image(
    product_id: str,
    manager: ManagerUser,
    db: Db,
    file: UploadFile = File(...),
    alt_text: str | None = None,
    is_primary: bool = False,
):
    """Upload product imagery.

    The file's *contents* decide the format (see ``app/core/uploads.py``): the
    declared Content-Type and filename are never trusted, and SVG/HTML are
    rejected outright because they are served from this origin and can carry
    script. This closes a stored-XSS path to admin sessions.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")

    raw = uploads.read_upload(file.file, max_bytes=settings.image_max_upload_bytes)
    image = uploads.validate_image(
        raw,
        declared_content_type=file.content_type,
        declared_filename=file.filename,
        max_bytes=settings.image_max_upload_bytes,
    )

    # Soft quality gate: warn an operator who uploads artwork too small to look
    # good on a retina PDP, without blocking the upload.
    dims = image.width_height
    if dims and is_primary and dims[0] < settings.image_min_width:
        log.warning(
            "primary image for product %s is %dx%d (recommended >= %dpx wide)",
            product_id,
            dims[0],
            dims[1],
            settings.image_min_width,
        )

    image_id = uuid4().hex
    key = uploads.storage_key_for(prefix=f"products/{product_id}", image=image, unique_id=image_id)
    url = storage_service.get_storage().put(key, image.data, image.content_type)

    record = ProductImage(
        product_id=product.id, url=url, storage_key=key, alt_text=alt_text, is_primary=is_primary
    )
    if is_primary:
        for existing in product.images:
            existing.is_primary = False
    db.add(record)
    db.flush()
    db.commit()
    return record


def _slugify(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
