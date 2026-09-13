from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import StaffUser
from app.core.pagination import PageParams, page_meta, paginate
from app.models.catalog import ProductVariant
from app.models.inventory import AdjustmentType, InventoryAdjustment
from app.schemas.common import Page
from app.schemas.ops import AdjustmentOut, AdjustmentRequest, VariantStockOut
from app.services import inventory_service, settings_service

router = APIRouter(prefix="/inventory", tags=["inventory"])
Db = Annotated[Session, Depends(get_db)]


def _stock_view(variant: ProductVariant, threshold: int) -> VariantStockOut:
    return VariantStockOut(
        variant_id=variant.id,
        sku=variant.sku,
        product_name=variant.product.name if variant.product else "",
        size=variant.size.value,
        stock_qty=variant.stock_qty,
        reserved_qty=variant.reserved_qty,
        available_qty=variant.available_qty,
        sold_qty=variant.sold_qty,
        damaged_qty=variant.damaged_qty,
        defective_qty=variant.defective_qty,
        returned_qty=variant.returned_qty,
        is_low_stock=0 < variant.available_qty <= threshold,
    )


@router.get("/variants", response_model=Page[VariantStockOut])
def list_stock(
    params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db, low_stock: bool | None = None
):
    threshold = int(settings_service.get_setting(db, "low_stock_threshold") or 3)
    stmt = select(ProductVariant)
    items, total = paginate(db, stmt, params, sort_columns={"sku": ProductVariant.sku})
    views = [_stock_view(v, threshold) for v in items]
    if low_stock:
        views = [v for v in views if v.is_low_stock or v.available_qty == 0]
    return Page(items=views, meta=page_meta(params, total))


@router.post("/adjustments", response_model=AdjustmentOut, status_code=201)
def adjust(payload: AdjustmentRequest, staff: StaffUser, db: Db):
    variant = inventory_service.get_variant(db, payload.variant_id)
    entry = inventory_service.adjust(
        db,
        variant,
        AdjustmentType(payload.adjustment_type),
        payload.qty_change,
        user=staff,
        reason=payload.reason,
    )
    db.commit()
    return entry


@router.get("/adjustments", response_model=Page[AdjustmentOut])
def list_adjustments(
    params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db, variant_id: str | None = None
):
    stmt = select(InventoryAdjustment)
    if variant_id:
        stmt = stmt.where(InventoryAdjustment.variant_id == variant_id)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": InventoryAdjustment.created_at})
    return Page(items=items, meta=page_meta(params, total))
