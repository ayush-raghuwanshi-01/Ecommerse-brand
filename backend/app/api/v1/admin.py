"""Admin: business settings, shipping rules, reports, audit log, maintenance."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.deps import AdminUser, ManagerUser
from app.core.pagination import PageParams, page_meta, paginate
from app.models.catalog import ProductVariant
from app.models.commerce import AuditLog, ShippingRule
from app.models.order import Order, PaymentStatus
from app.schemas.common import Message, Page
from app.schemas.ops import (
    AuditLogOut,
    ReportsOut,
    SettingsOut,
    SettingsUpdate,
    ShippingRuleCreate,
    ShippingRuleOut,
    VariantStockOut,
)
from app.services import audit_service, order_service, settings_service

router = APIRouter(prefix="/admin", tags=["admin"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/settings", response_model=SettingsOut)
def get_settings(manager: ManagerUser, db: Db):
    return SettingsOut(settings=settings_service.all_settings(db))


@router.patch("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, admin: AdminUser, db: Db, request: Request):
    for key, value in payload.settings.items():
        settings_service.set_setting(db, key, value)
    audit_service.record(
        db,
        user=admin,
        action="settings.update",
        entity_type="settings",
        entity_id=None,
        after=payload.settings,
        request=request,
    )
    db.commit()
    return SettingsOut(settings=settings_service.all_settings(db))


@router.get("/shipping-rules", response_model=list[ShippingRuleOut])
def list_rules(manager: ManagerUser, db: Db):
    return db.scalars(select(ShippingRule)).all()


@router.post("/shipping-rules", response_model=ShippingRuleOut, status_code=201)
def create_rule(payload: ShippingRuleCreate, admin: AdminUser, db: Db, request: Request):
    rule = ShippingRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    audit_service.record(
        db,
        user=admin,
        action="settings.update",
        entity_type="shipping_rule",
        entity_id=rule.id,
        after=payload.model_dump(),
        request=request,
    )
    db.commit()
    return rule


@router.delete("/shipping-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, admin: AdminUser, db: Db, request: Request):
    rule = db.get(ShippingRule, rule_id)
    if rule:
        audit_service.record(
            db,
            user=admin,
            action="settings.update",
            entity_type="shipping_rule",
            entity_id=rule_id,
            before={"kind": rule.kind.value},
            after=None,
            request=request,
        )
        db.delete(rule)
        db.commit()


@router.get("/reports", response_model=ReportsOut)
def reports(manager: ManagerUser, db: Db, period_days: int = 30):
    since = utcnow() - timedelta(days=period_days)
    orders = db.scalars(select(Order).where(Order.created_at >= since)).all()
    paid = [
        o
        for o in orders
        if o.payment_status in (PaymentStatus.paid, PaymentStatus.partially_refunded, PaymentStatus.refunded)
    ]
    revenue = sum(o.grand_total_paise for o in paid)
    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o.status.value] = by_status.get(o.status.value, 0) + 1
    by_source: dict[str, int] = {}
    for o in paid:
        by_source[o.order_source.value] = by_source.get(o.order_source.value, 0) + o.grand_total_paise
    threshold = int(settings_service.get_setting(db, "low_stock_threshold") or 3)
    low = db.scalars(
        select(ProductVariant).where(ProductVariant.stock_qty - ProductVariant.reserved_qty <= threshold)
    ).all()
    return ReportsOut(
        period_days=period_days,
        orders_total=len(orders),
        revenue_paise=revenue,
        aov_paise=int(revenue / len(paid)) if paid else 0,
        units_sold=sum(i.qty for o in paid for i in o.items),
        orders_by_status=by_status,
        revenue_by_source=by_source,
        low_stock_variants=[
            VariantStockOut(
                variant_id=v.id,
                sku=v.sku,
                product_name=v.product.name if v.product else "",
                size=v.size.value,
                stock_qty=v.stock_qty,
                reserved_qty=v.reserved_qty,
                available_qty=v.available_qty,
                sold_qty=v.sold_qty,
                damaged_qty=v.damaged_qty,
                defective_qty=v.defective_qty,
                returned_qty=v.returned_qty,
                is_low_stock=0 < v.available_qty <= threshold,
            )
            for v in low
        ],
    )


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(
    params: Annotated[PageParams, Depends()],
    manager: ManagerUser,
    db: Db,
    entity_type: str | None = None,
    action: str | None = None,
):
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": AuditLog.created_at})
    return Page(items=items, meta=page_meta(params, total))


@router.post("/maintenance/sweep-expired", response_model=Message)
def sweep(admin: AdminUser, db: Db):
    count = order_service.sweep_expired_reservations(db)
    db.commit()
    return Message(message=f"Released reservations for {count} expired order(s).")
