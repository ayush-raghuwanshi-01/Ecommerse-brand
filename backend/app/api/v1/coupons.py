from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ManagerUser
from app.core.exceptions import NotFoundError
from app.models.commerce import Coupon
from app.schemas.ops import CouponCreate, CouponOut, CouponUpdate
from app.services import audit_service

router = APIRouter(prefix="/coupons", tags=["coupons"])
Db = Annotated[Session, Depends(get_db)]


def _out(db: Session, coupon: Coupon) -> CouponOut:
    out = CouponOut.model_validate(coupon)
    out.times_used = len(coupon.usages)
    return out


@router.get("", response_model=list[CouponOut])
def list_coupons(manager: ManagerUser, db: Db):
    return [_out(db, c) for c in db.scalars(select(Coupon)).all()]


@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(payload: CouponCreate, manager: ManagerUser, db: Db, request: Request):
    coupon = Coupon(**payload.model_dump(), code=payload.code.upper().strip())
    db.add(coupon)
    db.flush()
    audit_service.record(
        db,
        user=manager,
        action="coupon.create",
        entity_type="coupon",
        entity_id=coupon.id,
        after=payload.model_dump(),
        request=request,
    )
    db.commit()
    return _out(db, coupon)


@router.patch("/{coupon_id}", response_model=CouponOut)
def update_coupon(coupon_id: str, payload: CouponUpdate, manager: ManagerUser, db: Db, request: Request):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise NotFoundError("Coupon not found.")
    before = {k: getattr(coupon, k) for k in payload.model_dump(exclude_unset=True)}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, key, value)
    audit_service.record(
        db,
        user=manager,
        action="coupon.update",
        entity_type="coupon",
        entity_id=coupon.id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    db.commit()
    return _out(db, coupon)
