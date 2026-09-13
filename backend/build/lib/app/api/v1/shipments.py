from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import StaffUser
from app.core.exceptions import NotFoundError
from app.models.returns import Shipment, ShipmentStatus
from app.schemas.ops import ShipmentCreate, ShipmentOut, ShipmentUpdate
from app.services import audit_service, notification_service, shipping_service

router = APIRouter(prefix="/shipments", tags=["shipments"])
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ShipmentOut, status_code=201)
def create_shipment(payload: ShipmentCreate, staff: StaffUser, db: Db):
    from app.models.order import Order

    order = db.get(Order, payload.order_id)
    if order is None:
        raise NotFoundError("Order not found.")
    shipment = shipping_service.get_provider().create_shipment(
        db, order, provider=payload.provider, tracking_number=payload.tracking_number,
        tracking_url=payload.tracking_url,
    )
    db.commit()
    return shipment


@router.patch("/{shipment_id}", response_model=ShipmentOut)
def update_shipment(shipment_id: str, payload: ShipmentUpdate, staff: StaffUser, db: Db, request: Request):
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise NotFoundError("Shipment not found.")
    before = {"status": shipment.status.value, "tracking_number": shipment.tracking_number}
    if payload.tracking_number is not None:
        shipment.tracking_number = payload.tracking_number
    if payload.tracking_url is not None:
        shipment.tracking_url = payload.tracking_url
    if payload.status:
        shipping_service.advance_shipment(db, shipment, ShipmentStatus(payload.status))
        order = shipment.order
        if order and order.customer and payload.status in ("in_transit", "out_for_delivery", "delivered"):
            notification_service.notify(
                db, event_type="tracking_updated", recipient=order.customer.email,
                payload={"order_number": order.number, "status": payload.status,
                         "tracking_number": shipment.tracking_number},
            )
    audit_service.record(db, user=staff, action="shipment.update", entity_type="shipment",
                         entity_id=shipment.id, before=before,
                         after={"status": shipment.status.value, "tracking_number": shipment.tracking_number},
                         request=request)
    db.commit()
    return shipment


@router.get("/order/{order_id}", response_model=list[ShipmentOut])
def order_shipments(order_id: str, staff: StaffUser, db: Db):
    return db.scalars(select(Shipment).where(Shipment.order_id == order_id)).all()


@router.get("/order/{order_id}/tracking", response_model=dict)
def tracking(order_id: str, db: Db, customer_id: str | None = None):
    """Customer-facing tracking (order id acts as the lookup token in v1)."""
    shipment = db.scalar(
        select(Shipment).where(Shipment.order_id == order_id, Shipment.direction == "forward")
    )
    if shipment is None:
        raise NotFoundError("No shipment for this order yet.")
    return {
        "status": shipping_service.get_provider().get_tracking_status(db, shipment),
        "tracking_number": shipment.tracking_number,
        "tracking_url": shipment.tracking_url,
        "provider": shipment.provider,
        "estimated_delivery_days": "5-8",
    }
