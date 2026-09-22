from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import CurrentUser, ManagerUser, StaffUser
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.pagination import PageParams, page_meta, paginate
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.common import Page
from app.schemas.order import (
    CancelDecision,
    CancelRequest,
    CollectPaymentRequest,
    NoteRequest,
    OrderEditRequest,
    OrderOut,
    StatusUpdateRequest,
)
from app.services import order_service, payment_service

router = APIRouter(prefix="/orders", tags=["orders"])
Db = Annotated[Session, Depends(get_db)]


def serialize_order(db: Session, order: Order, viewer: User | None = None) -> OrderOut:
    out = OrderOut.model_validate(order)
    if viewer is None or viewer.role.value == "customer":
        out.internal_notes = None
    return out


@router.get("/me", response_model=Page[OrderOut])
def my_orders(params: Annotated[PageParams, Depends()], user: CurrentUser, db: Db, status: str | None = None):
    stmt = (
        select(Order)
        .options(joinedload(Order.items), joinedload(Order.history))
        .where(Order.customer_id == user.id)
    )
    if status:
        stmt = stmt.where(Order.status == status)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": Order.created_at})
    return Page(items=[serialize_order(db, o, user) for o in items], meta=page_meta(params, total))


@router.get("/me/{order_id}", response_model=OrderOut)
def my_order(order_id: str, user: CurrentUser, db: Db):
    order = order_service.get_order_for_user(db, order_id, user)
    return serialize_order(db, order, user)


@router.post("/me/{order_id}/cancel-request", response_model=OrderOut)
def request_cancel(order_id: str, payload: CancelRequest, user: CurrentUser, db: Db):
    order = order_service.get_order_for_user(db, order_id, user)
    order_service.request_cancellation(db, order, actor=user, reason=payload.reason, note=payload.note)
    db.commit()
    return serialize_order(db, order, user)


# ── Staff & manager: all orders ─────────────────────────────────────────────
@router.get("", response_model=Page[OrderOut])
def list_orders(
    params: Annotated[PageParams, Depends()],
    staff: StaffUser,
    db: Db,
    status: str | None = None,
    source: str | None = None,
    preorder: bool | None = None,
    payment_status: str | None = None,
):
    stmt = select(Order).options(joinedload(Order.items), joinedload(Order.history))
    if status:
        stmt = stmt.where(Order.status == status)
    if source:
        stmt = stmt.where(Order.order_source == source)
    if preorder is not None:
        stmt = stmt.where(Order.is_preorder.is_(preorder))
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(
            or_(Order.number.ilike(like), Order.shipping_address["postal_code"].as_string().ilike(like))
        )
    items, total = paginate(db, stmt, params, sort_columns={"created_at": Order.created_at})
    return Page(items=[serialize_order(db, o, staff) for o in items], meta=page_meta(params, total))


@router.get("/guest/{order_number}", response_model=OrderOut)
def get_guest_order(order_number: str, db: Db):
    """Public guest lookup for order confirmation screen."""
    order = db.scalar(
        select(Order).options(joinedload(Order.items), joinedload(Order.history)).where(Order.number == order_number)
    )
    if order is None:
        raise NotFoundError("Order not found.")
    return serialize_order(db, order, viewer=None)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: str, staff: StaffUser, db: Db):
    order = db.scalar(
        select(Order).options(joinedload(Order.items), joinedload(Order.history)).where(Order.id == order_id)
    )
    if order is None:
        raise NotFoundError("Order not found.")
    return serialize_order(db, order, staff)


@router.patch("/{order_id}", response_model=OrderOut)
def edit_order(order_id: str, payload: OrderEditRequest, staff: StaffUser, db: Db, request: Request):
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    order_service.edit_order(db, order, actor=staff, changes=changes)
    db.commit()
    return serialize_order(db, order, staff)


@router.post("/{order_id}/status", response_model=OrderOut)
def update_status(order_id: str, payload: StatusUpdateRequest, staff: StaffUser, db: Db):
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    order_service.set_status(db, order, OrderStatus(payload.status), actor=staff, note=payload.note)
    db.commit()
    return serialize_order(db, order, staff)


@router.post("/{order_id}/notes", response_model=OrderOut)
def add_note(order_id: str, payload: NoteRequest, staff: StaffUser, db: Db):
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    order_service.add_internal_note(db, order, actor=staff, note=payload.note)
    db.commit()
    return serialize_order(db, order, staff)


@router.post("/{order_id}/cancel-decision", response_model=OrderOut)
def cancel_decision(order_id: str, payload: CancelDecision, manager: ManagerUser, db: Db):
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    order_service.decide_cancellation(db, order, approver=manager, approve=payload.approve, note=payload.note)
    db.commit()
    return serialize_order(db, order, manager)


@router.post("/{order_id}/collect-cod", response_model=OrderOut)
def collect_cod(order_id: str, payload: CollectPaymentRequest, staff: StaffUser, db: Db):
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    if not payload.collected:
        raise PermissionDeniedError("Use status updates for non-collection changes.")
    payment_service.collect_cod(db, order, actor=staff, method_note=payload.method_note)
    db.commit()
    return serialize_order(db, order, staff)


@router.get("/{order_id}/whatsapp-link", response_model=dict)
def whatsapp_link(order_id: str, staff: StaffUser, db: Db):
    """Manual staff-assist wa.me link (not an automated notification channel)."""
    from app.services.notification_service import whatsapp_link as build_link

    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    phone = order.shipping_address.get("phone", "")
    message = (
        f"Hello! Regarding your Black House order {order.number} (₹{order.grand_total_paise / 100:,.0f})."
    )
    return {"link": build_link(phone, message)}
