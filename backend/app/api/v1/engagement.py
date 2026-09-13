"""Restock alerts + bulk enquiries + notification inbox."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, StaffUser
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams, page_meta, paginate
from app.models.commerce import (
    BulkEnquiry,
    Notification,
    RestockStatus,
    RestockSubscription,
)
from app.schemas.common import Message, Page
from app.schemas.ops import (
    BulkEnquiryCreate,
    BulkEnquiryOut,
    BulkEnquiryUpdate,
    NotificationOut,
    RestockSubscribeRequest,
    RestockSubscriptionOut,
)
from app.services import inventory_service, notification_service

router = APIRouter(tags=["engagement"])
Db = Annotated[Session, Depends(get_db)]


# ── Restock alerts ──────────────────────────────────────────────────────────
@router.post("/restock-alerts", response_model=RestockSubscriptionOut, status_code=201)
def subscribe(payload: RestockSubscribeRequest, user: CurrentUser, db: Db):
    variant = inventory_service.get_variant(db, payload.variant_id)
    existing = db.scalar(
        select(RestockSubscription).where(
            RestockSubscription.customer_id == user.id,
            RestockSubscription.variant_id == variant.id,
            RestockSubscription.status == RestockStatus.active,
        )
    )
    if existing:
        raise ConflictError("You are already subscribed to restock alerts for this size.")
    sub = RestockSubscription(
        customer_id=user.id, variant_id=variant.id, email=user.email, phone=payload.phone or user.phone
    )
    db.add(sub)
    db.flush()
    db.commit()
    return sub


@router.get("/restock-alerts", response_model=list[RestockSubscriptionOut])
def my_subscriptions(user: CurrentUser, db: Db):
    return db.scalars(select(RestockSubscription).where(RestockSubscription.customer_id == user.id)).all()


@router.delete("/restock-alerts/{subscription_id}", response_model=Message)
def unsubscribe(subscription_id: str, user: CurrentUser, db: Db):
    sub = db.get(RestockSubscription, subscription_id)
    if sub is None or sub.customer_id != user.id:
        raise NotFoundError("Subscription not found.")
    sub.status = RestockStatus.cancelled
    db.commit()
    return Message(message="Subscription cancelled.")


# ── Bulk enquiries (public intake, staff pipeline) ──────────────────────────
@router.post("/bulk-enquiries", response_model=BulkEnquiryOut, status_code=201)
def create_enquiry(payload: BulkEnquiryCreate, db: Db):
    enquiry = BulkEnquiry(**payload.model_dump())
    db.add(enquiry)
    db.flush()
    notification_service.notify(
        db, event_type="bulk_enquiry_received", recipient="sales@blackhouse.internal",
        payload={"name": enquiry.name, "business": enquiry.business_name, "qty": enquiry.estimated_qty},
    )
    db.commit()
    return enquiry


@router.get("/bulk-enquiries", response_model=Page[BulkEnquiryOut])
def list_enquiries(params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db, status: str | None = None):
    stmt = select(BulkEnquiry)
    if status:
        stmt = stmt.where(BulkEnquiry.status == status)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": BulkEnquiry.created_at})
    return Page(items=items, meta=page_meta(params, total))


@router.patch("/bulk-enquiries/{enquiry_id}", response_model=BulkEnquiryOut)
def update_enquiry(enquiry_id: str, payload: BulkEnquiryUpdate, staff: StaffUser, db: Db):
    enquiry = db.get(BulkEnquiry, enquiry_id)
    if enquiry is None:
        raise NotFoundError("Enquiry not found.")
    if payload.status:
        enquiry.status = payload.status
    if payload.staff_notes is not None:
        enquiry.staff_notes = payload.staff_notes
    db.commit()
    return enquiry


# ── Notification inbox ──────────────────────────────────────────────────────
@router.get("/notifications/me", response_model=list[NotificationOut])
def my_notifications(user: CurrentUser, db: Db):
    return db.scalars(
        select(Notification).where(Notification.recipient == user.email)
        .order_by(Notification.created_at.desc()).limit(50)
    ).all()


@router.get("/notifications", response_model=Page[NotificationOut])
def all_notifications(params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db):
    stmt = select(Notification)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": Notification.created_at})
    return Page(items=items, meta=page_meta(params, total))


@router.post("/notifications/{notification_id}/retry", response_model=NotificationOut)
def retry_notification(notification_id: str, staff: StaffUser, db: Db):
    note = db.get(Notification, notification_id)
    if note is None:
        raise NotFoundError("Notification not found.")
    notification_service.retry_notification(db, note)
    db.commit()
    return note
