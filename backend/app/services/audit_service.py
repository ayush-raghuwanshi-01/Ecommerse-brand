"""Append-only audit trail. No code path updates or deletes audit rows."""

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.net import client_ip
from app.models.commerce import AuditLog
from app.models.user import User

AUDITABLE = {
    "product.create",
    "product.update",
    "product.publish",
    "product.archive",
    "product.price_change",
    "variant.update",
    "inventory.adjust",
    "order.create_staff",
    "order.edit",
    "order.status_change",
    "order.cancel_request",
    "order.cancel_approve",
    "order.cancel_reject",
    "refund.approve",
    "refund.reject",
    "refund.complete",
    "return.approve",
    "return.reject",
    "return.status_change",
    "coupon.create",
    "coupon.update",
    "user.role_change",
    "shipment.update",
    "payment.status_change",
    "settings.update",
}


def _snapshot(obj: Any) -> dict | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    from sqlalchemy.orm import DeclarativeBase

    if isinstance(obj, DeclarativeBase):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    return None


def record(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: Any = None,
    after: Any = None,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        role=user.role.value if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=_snapshot(before),
        after_json=_snapshot(after),
        ip=client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(entry)
    db.flush()
    return entry
