"""Inventory: reservation lifecycle, adjustments, movement ledger.

Oversell protection is a conditional UPDATE guard (`WHERE stock - reserved >= q`)
which is atomic on both PostgreSQL and SQLite; on PostgreSQL we additionally take
a row lock (SELECT ... FOR UPDATE) before mutating.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import supports_row_locking, utcnow
from app.core.exceptions import InsufficientStockError, NotFoundError, ValidationError
from app.models.catalog import ProductVariant
from app.models.commerce import NotificationChannel, RestockStatus, RestockSubscription
from app.models.inventory import AdjustmentType, InventoryAdjustment
from app.models.user import User
from app.services import audit_service, notification_service, settings_service


def get_variant(db: Session, variant_id: str) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise NotFoundError("Product variant not found.")
    return variant


def _lock(db: Session, variant: ProductVariant) -> None:
    if supports_row_locking(db):
        db.execute(select(ProductVariant).where(ProductVariant.id == variant.id).with_for_update())


def _ledger(
    db: Session,
    variant: ProductVariant,
    adj_type: AdjustmentType,
    qty_before: int,
    qty_change: int,
    *,
    user: User | None = None,
    reason: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> None:
    db.add(
        InventoryAdjustment(
            variant_id=variant.id,
            warehouse_id=variant.warehouse_id,
            user_id=user.id if user else None,
            adjustment_type=adj_type,
            qty_before=qty_before,
            qty_change=qty_change,
            qty_after=qty_before + qty_change,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )


def _preorder_capacity_ok(variant: ProductVariant, qty: int) -> bool:
    product = variant.product
    limit = product.preorder_limit if product else None
    if not limit:
        return True
    return (variant.reserved_qty + variant.sold_qty + qty) <= limit


def reserve(
    db: Session,
    variant: ProductVariant,
    qty: int,
    *,
    user: User | None = None,
    reference_id: str | None = None,
    is_preorder_line: bool = False,
) -> None:
    """Reserve stock inside the caller's transaction. Raises on oversell."""
    if qty <= 0:
        raise ValidationError("Quantity must be positive.")
    _lock(db, variant)
    before = variant.available_qty
    if is_preorder_line or variant.is_preorder:
        if not _preorder_capacity_ok(variant, qty):
            raise InsufficientStockError(
                "Pre-order limit reached for this style.",
                details={"variant_id": variant.id, "sku": variant.sku},
            )
        variant.reserved_qty += qty
    else:
        result = db.execute(
            update(ProductVariant)
            .where(ProductVariant.id == variant.id)
            .where(ProductVariant.stock_qty - ProductVariant.reserved_qty >= qty)
            .values(reserved_qty=ProductVariant.reserved_qty + qty)
        )
        if result.rowcount != 1:
            raise InsufficientStockError(
                "The selected size is no longer available.",
                details={"variant_id": variant.id, "sku": variant.sku, "requested": qty, "available": before},
            )
    db.expire(variant)
    db.refresh(variant)
    _ledger(
        db,
        variant,
        AdjustmentType.reserve,
        before,
        -qty,
        user=user,
        reason="stock reserved",
        reference_type="order",
        reference_id=reference_id,
    )


def release(db: Session, variant: ProductVariant, qty: int, *, reference_id: str | None = None) -> None:
    _lock(db, variant)
    before = variant.available_qty
    delta = min(qty, variant.reserved_qty)
    if delta <= 0:
        return
    variant.reserved_qty -= delta
    _ledger(
        db,
        variant,
        AdjustmentType.release,
        before,
        delta,
        reason="reservation released",
        reference_type="order",
        reference_id=reference_id,
    )


def commit_reservation(
    db: Session,
    variant: ProductVariant,
    qty: int,
    *,
    reference_id: str | None = None,
    is_preorder_line: bool = False,
) -> None:
    """Payment/confirmation success: reservation becomes a sale."""
    _lock(db, variant)
    before = variant.available_qty
    delta = min(qty, variant.reserved_qty)
    variant.reserved_qty -= delta
    if not (is_preorder_line or variant.is_preorder):
        variant.stock_qty -= delta
    variant.sold_qty += delta
    _ledger(
        db,
        variant,
        AdjustmentType.sale,
        before,
        -delta,
        reason="sale committed",
        reference_type="order",
        reference_id=reference_id,
    )


def adjust(
    db: Session,
    variant: ProductVariant,
    adj_type: AdjustmentType,
    qty_change: int,
    *,
    user: User,
    reason: str | None = None,
    reference_type: str | None = "manual",
    reference_id: str | None = None,
) -> InventoryAdjustment:
    """Manual/operational stock movement. Negative available stock is impossible."""
    _lock(db, variant)
    before_stock = variant.stock_qty
    before_avail = variant.available_qty

    if adj_type == AdjustmentType.increase:
        if qty_change <= 0:
            raise ValidationError("increase requires a positive qty_change.")
        variant.stock_qty += qty_change
    elif adj_type == AdjustmentType.decrease:
        if qty_change >= 0:
            raise ValidationError("decrease requires a negative qty_change.")
        if before_stock + qty_change < 0:
            raise ValidationError(
                "Cannot decrease below on-hand stock.",
                details={"stock_qty": before_stock, "requested": qty_change},
            )
        variant.stock_qty += qty_change
    elif adj_type == AdjustmentType.return_:
        if qty_change <= 0:
            raise ValidationError("return requires a positive qty_change.")
        variant.stock_qty += qty_change
        variant.returned_qty += qty_change
    elif adj_type in (AdjustmentType.damage, AdjustmentType.defect):
        if qty_change >= 0:
            raise ValidationError("damage/defect requires a negative qty_change.")
        if before_stock + qty_change < 0:
            raise ValidationError("Cannot write off more than on-hand stock.")
        variant.stock_qty += qty_change
        if adj_type == AdjustmentType.damage:
            variant.damaged_qty += -qty_change
        else:
            variant.defective_qty += -qty_change
    elif adj_type == AdjustmentType.correction:
        if before_stock + qty_change < 0:
            raise ValidationError("Correction would result in negative stock.")
        variant.stock_qty += qty_change
    else:  # pragma: no cover
        raise ValidationError("Unsupported adjustment type.")

    if variant.stock_qty - variant.reserved_qty < 0:
        raise ValidationError("Adjustment would make reserved stock exceed on-hand stock.")

    entry = InventoryAdjustment(
        variant_id=variant.id,
        warehouse_id=variant.warehouse_id,
        user_id=user.id,
        adjustment_type=adj_type,
        qty_before=before_stock,
        qty_change=qty_change,
        qty_after=variant.stock_qty,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(entry)

    audit_service.record(
        db,
        user=user,
        action="inventory.adjust",
        entity_type="product_variant",
        entity_id=variant.id,
        before={"stock_qty": before_stock},
        after={"stock_qty": variant.stock_qty, "type": adj_type.value, "reason": reason},
    )

    after_avail = variant.available_qty
    _fire_restock_alerts(db, variant, before_avail, after_avail)
    _fire_low_stock(db, variant, after_avail)
    return entry


def _fire_restock_alerts(db: Session, variant: ProductVariant, before_avail: int, after_avail: int) -> None:
    """Notify subscribers exactly once per restock event (status flips to notified)."""
    if before_avail > 0 or after_avail <= 0:
        return
    subs = db.scalars(
        select(RestockSubscription).where(
            RestockSubscription.variant_id == variant.id,
            RestockSubscription.status == RestockStatus.active,
        )
    ).all()
    for sub in subs:
        notification_service.notify(
            db,
            event_type="restock_alert",
            recipient=sub.email,
            channel=NotificationChannel.email,
            payload={
                "subject": f"{variant.product.name} is back in stock",
                "sku": variant.sku,
                "size": variant.size.value,
            },
        )
        if sub.phone:
            notification_service.notify(
                db,
                event_type="restock_alert",
                recipient=sub.phone,
                channel=NotificationChannel.whatsapp,
                payload={"sku": variant.sku, "size": variant.size.value},
            )
        sub.status = RestockStatus.notified
        sub.notified_at = utcnow()
    db.flush()


def _fire_low_stock(db: Session, variant: ProductVariant, after_avail: int) -> None:
    threshold = settings_service.get_setting(db, "low_stock_threshold") or 3
    if 0 < after_avail <= threshold:
        notification_service.notify(
            db,
            event_type="low_inventory",
            recipient="ops@blackhouse.internal",
            channel=NotificationChannel.internal,
            payload={"sku": variant.sku, "available": after_avail, "threshold": threshold},
        )


def record_return_intake(
    db: Session,
    variant: ProductVariant,
    qty: int,
    *,
    damaged: bool,
    user: User,
    reference_id: str | None = None,
) -> None:
    """Returned units re-enter sellable stock only when accepted in good condition."""
    _lock(db, variant)
    before = variant.stock_qty
    variant.returned_qty += qty
    if damaged:
        variant.damaged_qty += qty
        change = 0
        adj_type = AdjustmentType.damage
    else:
        variant.stock_qty += qty
        change = qty
        adj_type = AdjustmentType.return_
    _ledger(
        db,
        variant,
        adj_type,
        before,
        change,
        user=user,
        reason="return intake",
        reference_type="return",
        reference_id=reference_id,
    )
    after_avail = variant.available_qty
    _fire_restock_alerts(db, variant, max(before - variant.reserved_qty, 0), after_avail)
