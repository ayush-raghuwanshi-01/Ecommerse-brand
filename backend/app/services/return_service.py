"""Returns, exchanges, replacements — 7-day window, policy-driven shipping,
refund eligibility after pickup, completion after inspection."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.exceptions import NotFoundError, PolicyError, ValidationError
from app.models.catalog import ProductVariant
from app.models.order import Order, OrderStatus
from app.models.returns import (
    COMPANY_PAYS_RETURN_SHIPPING,
    ReturnReason,
    ReturnRequest,
    ReturnStatus,
    ReturnType,
)
from app.models.user import User
from app.services import (
    audit_service,
    inventory_service,
    notification_service,
    refund_service,
    settings_service,
)

RETURN_FLOW = [
    ReturnStatus.requested,
    ReturnStatus.under_review,
    ReturnStatus.approved,
    ReturnStatus.pickup_scheduled,
    ReturnStatus.picked_up,
    ReturnStatus.received,
    ReturnStatus.inspected,
    ReturnStatus.completed,
]


def create_return(
    db: Session,
    *,
    customer: User,
    order: Order,
    order_item_id: str | None,
    return_type: ReturnType,
    reason: ReturnReason,
    notes: str | None,
    exchange_variant_id: str | None,
) -> ReturnRequest:
    if order.customer_id != customer.id:
        raise NotFoundError("Order not found.")
    if order.status not in (
        OrderStatus.delivered,
        OrderStatus.completed,
        OrderStatus.return_requested,
        OrderStatus.return_approved,
        OrderStatus.returned,
    ):
        raise PolicyError("Returns can only be requested for delivered orders.")
    window = int(settings_service.get_setting(db, "return_window_days") or 7)
    if not order.delivered_at or (utcnow() - order.delivered_at).days > window:
        raise PolicyError(
            f"The return window is {window} days from delivery.",
            details={"delivered_at": order.delivered_at.isoformat() if order.delivered_at else None},
        )
    item = None
    if order_item_id:
        item = next((i for i in order.items if i.id == order_item_id), None)
        if item is None:
            raise NotFoundError("Order item not found on this order.")

    product = None
    if item:
        product = db.get(ProductVariant, item.variant_id).product
    elif order.items:
        product = db.get(ProductVariant, order.items[0].variant_id).product

    if product and product.is_sale_item and return_type == ReturnType.refund:
        raise PolicyError(
            "Sale items are returnable for exchange or replacement, not cash refunds.",
            details={"allowed": ["size_exchange", "product_exchange", "replacement"]},
        )
    if return_type in (ReturnType.size_exchange, ReturnType.product_exchange) and not exchange_variant_id:
        raise ValidationError("Choose the variant you want in exchange.")

    existing = db.scalar(
        select(ReturnRequest).where(
            ReturnRequest.order_id == order.id,
            ReturnRequest.order_item_id == order_item_id,
            ReturnRequest.status.notin_([ReturnStatus.rejected, ReturnStatus.completed]),
        )
    )
    if existing:
        raise PolicyError("A return is already open for this order/item.")

    ret = ReturnRequest(
        order_id=order.id,
        order_item_id=order_item_id,
        customer_id=customer.id,
        return_type=return_type,
        reason=reason,
        notes=notes,
        company_pays_shipping=reason in COMPANY_PAYS_RETURN_SHIPPING,
        exchange_variant_id=exchange_variant_id,
    )
    db.add(ret)
    if order.status == OrderStatus.delivered:
        order.status = OrderStatus.return_requested
    notification_service.notify(
        db,
        event_type="return_requested",
        recipient="cs@blackhouse.internal",
        payload={"order_number": order.number, "return_type": return_type.value, "reason": reason.value},
    )
    db.flush()
    return ret


def advance_return(
    db: Session,
    ret: ReturnRequest,
    *,
    actor: User,
    new_status: ReturnStatus,
    staff_notes: str | None = None,
    accept_items: bool = True,
) -> ReturnRequest:
    order = db.get(Order, ret.order_id)
    is_manager = actor.role.value in ("manager", "admin")

    if new_status in (ReturnStatus.approved, ReturnStatus.rejected):
        if not is_manager:
            from app.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Only managers/admins can approve or reject returns.")
        audit_service.record(
            db,
            user=actor,
            action="return.approve" if new_status == ReturnStatus.approved else "return.reject",
            entity_type="return",
            entity_id=ret.id,
            after={"status": new_status.value},
        )
    elif new_status in (ReturnStatus.approved_for_refund, ReturnStatus.approved_for_exchange):
        if not is_manager:
            from app.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Only managers/admins can approve refunds or exchanges.")

    if new_status == ReturnStatus.rejected:
        ret.status = new_status
        ret.staff_notes = staff_notes
        if order and order.status == OrderStatus.return_requested:
            order.status = OrderStatus.delivered
        db.flush()
        return ret

    if RETURN_FLOW.index(new_status) != RETURN_FLOW.index(ret.status) + 1 and new_status not in (
        ReturnStatus.approved_for_refund,
        ReturnStatus.approved_for_exchange,
    ):
        raise ValidationError(
            "Invalid return transition.", details={"from": ret.status.value, "to": new_status.value}
        )

    ret.status = new_status
    if staff_notes:
        ret.staff_notes = staff_notes

    # Refund eligibility begins once courier pickup is confirmed.
    if new_status == ReturnStatus.picked_up and ret.return_type == ReturnType.refund:
        amount = _return_amount(db, ret)
        refund_service.request_refund(db, order, amount, actor, return_request=ret, reason=ret.reason.value)

    # Final completion happens after inspection/validation.
    if new_status == ReturnStatus.inspected:
        if accept_items:
            _restock_returned_items(db, ret, actor)
        if ret.return_type == ReturnType.refund:
            ret.status = ReturnStatus.approved_for_refund
        else:
            ret.status = ReturnStatus.approved_for_exchange
            _schedule_exchange(db, ret, actor)

    if (
        new_status in (ReturnStatus.approved_for_refund, ReturnStatus.approved_for_exchange)
        and ret.status != new_status
    ):
        ret.status = new_status

    if new_status == ReturnStatus.completed:
        ret.completed_at = utcnow()
        if order:
            order.status = OrderStatus.returned

    audit_service.record(
        db,
        user=actor,
        action="return.status_change",
        entity_type="return",
        entity_id=ret.id,
        before={"status": ret.status.value},
        after={"status": new_status.value},
    )
    db.flush()
    return ret


def _return_amount(db: Session, ret: ReturnRequest) -> int:
    order = db.get(Order, ret.order_id)
    if ret.order_item_id:
        item = next(i for i in order.items if i.id == ret.order_item_id)
        return item.total_paise
    # full-order return: goods value + shipping originally paid
    return order.grand_total_paise


def _restock_returned_items(db: Session, ret: ReturnRequest, actor: User) -> None:
    order = db.get(Order, ret.order_id)
    items = [i for i in order.items if i.id == ret.order_item_id] if ret.order_item_id else list(order.items)
    damaged = ret.reason in (ReturnReason.damaged_product, ReturnReason.defective_product)
    for item in items:
        variant = inventory_service.get_variant(db, item.variant_id)
        inventory_service.record_return_intake(
            db, variant, item.qty, damaged=damaged, user=actor, reference_id=ret.id
        )


def _schedule_exchange(db: Session, ret: ReturnRequest, actor: User) -> None:
    from app.services import shipping_service

    order = db.get(Order, ret.order_id)
    shipment = shipping_service.get_provider().create_shipment(db, order, direction="forward")
    shipment.metadata_json = {"exchange_for_return": ret.id, "variant_id": ret.exchange_variant_id}
    if order and order.customer:
        notification_service.notify(
            db,
            event_type="exchange_approved",
            recipient=order.customer.email,
            payload={"order_number": order.number},
        )
