from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, ManagerUser, StaffUser
from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, page_meta, paginate
from app.models.returns import Refund, ReturnRequest, ReturnStatus, ReturnReason, ReturnType
from app.schemas.common import Message, Page
from app.schemas.ops import RefundApproveRequest, RefundOut, ReturnCreate, ReturnOut, ReturnStatusUpdate
from app.services import order_service, refund_service, return_service

router = APIRouter(prefix="/returns", tags=["returns"])
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ReturnOut, status_code=201)
def create_return(payload: ReturnCreate, user: CurrentUser, db: Db):
    order = order_service.get_order_for_user(db, payload.order_id, user)
    ret = return_service.create_return(
        db, customer=user, order=order, order_item_id=payload.order_item_id,
        return_type=ReturnType(payload.return_type), reason=ReturnReason(payload.reason),
        notes=payload.notes, exchange_variant_id=payload.exchange_variant_id,
    )
    db.commit()
    return ret


@router.get("/me", response_model=list[ReturnOut])
def my_returns(user: CurrentUser, db: Db):
    return db.scalars(select(ReturnRequest).where(ReturnRequest.customer_id == user.id)).all()


@router.get("", response_model=Page[ReturnOut])
def list_returns(params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db, status: str | None = None):
    stmt = select(ReturnRequest)
    if status:
        stmt = stmt.where(ReturnRequest.status == status)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": ReturnRequest.created_at})
    return Page(items=items, meta=page_meta(params, total))


@router.post("/{return_id}/status", response_model=ReturnOut)
def advance(return_id: str, payload: ReturnStatusUpdate, staff: StaffUser, db: Db):
    ret = db.get(ReturnRequest, return_id)
    if ret is None:
        raise NotFoundError("Return not found.")
    return_service.advance_return(
        db, ret, actor=staff, new_status=ReturnStatus(payload.status),
        staff_notes=payload.staff_notes, accept_items=payload.accept_items,
    )
    db.commit()
    return ret


@router.get("/{return_id}/refunds", response_model=list[RefundOut])
def return_refunds(return_id: str, staff: StaffUser, db: Db):
    return db.scalars(select(Refund).where(Refund.return_request_id == return_id)).all()


@router.post("/refunds/decide", response_model=RefundOut)
def decide_refund(payload: RefundApproveRequest, manager: ManagerUser, db: Db):
    refund = db.get(Refund, payload.refund_id)
    if refund is None:
        raise NotFoundError("Refund not found.")
    refund_service.decide_refund(db, refund, actor=manager, approve=payload.approve, note=payload.note)
    db.commit()
    return refund


@router.get("/refunds", response_model=Page[RefundOut])
def list_refunds(params: Annotated[PageParams, Depends()], manager: ManagerUser, db: Db):
    stmt = select(Refund)
    items, total = paginate(db, stmt, params, sort_columns={"created_at": Refund.created_at})
    return Page(items=items, meta=page_meta(params, total))
