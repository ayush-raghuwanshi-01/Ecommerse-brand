from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import AdminUser, CurrentUser, StaffUser
from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, page_meta, paginate
from app.models.user import Address, User
from app.schemas.auth import AddressBase, AddressOut, UserOut, UserUpdate
from app.schemas.common import Page
from app.services import audit_service

router = APIRouter(tags=["users"])
Db = Annotated[Session, Depends(get_db)]


# ── Own profile & addresses ─────────────────────────────────────────────────
@router.patch("/users/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: CurrentUser, db: Db):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    db.flush()
    db.commit()
    return user


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(user: CurrentUser, db: Db):
    return db.query(Address).filter_by(user_id=user.id).order_by(Address.created_at).all()


@router.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(payload: AddressBase, user: CurrentUser, db: Db):
    if payload.is_default_shipping:
        for a in db.query(Address).filter_by(user_id=user.id):
            a.is_default_shipping = False
    if payload.is_default_billing:
        for a in db.query(Address).filter_by(user_id=user.id):
            a.is_default_billing = False
    address = Address(user_id=user.id, **payload.model_dump())
    db.add(address)
    db.flush()
    db.commit()
    return address


@router.patch("/addresses/{address_id}", response_model=AddressOut)
def update_address(address_id: str, payload: AddressBase, user: CurrentUser, db: Db):
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise NotFoundError("Address not found.")
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    db.flush()
    db.commit()
    return address


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: str, user: CurrentUser, db: Db):
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise NotFoundError("Address not found.")
    db.delete(address)
    db.commit()


# ── Staff: customer directory ───────────────────────────────────────────────
@router.get("/customers", response_model=Page[UserOut])
def list_customers(params: Annotated[PageParams, Depends()], staff: StaffUser, db: Db):
    from sqlalchemy import or_, select

    stmt = select(User).where(User.role == "customer")
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like), User.phone.ilike(like)))
    items, total = paginate(db, stmt, params, sort_columns={"created_at": User.created_at, "email": User.email})
    return Page(items=items, meta=page_meta(params, total))


@router.get("/customers/{customer_id}", response_model=dict)
def get_customer(customer_id: str, staff: StaffUser, db: Db):
    customer = db.get(User, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    from app.models.order import Order

    orders = db.query(Order).filter_by(customer_id=customer_id).order_by(Order.created_at.desc()).limit(25).all()
    return {
        "customer": UserOut.model_validate(customer),
        "addresses": [AddressOut.model_validate(a) for a in customer.addresses],
        "recent_orders": [
            {"id": o.id, "number": o.number, "status": o.status.value,
             "grand_total_paise": o.grand_total_paise, "created_at": o.created_at}
            for o in orders
        ],
    }


# ── Admin: user & role management ───────────────────────────────────────────
@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def change_role(user_id: str, role: str, admin: AdminUser, db: Db):
    from app.models.user import UserRole

    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found.")
    before = target.role.value
    target.role = UserRole(role)
    audit_service.record(db, user=admin, action="user.role_change", entity_type="user",
                         entity_id=target.id, before={"role": before}, after={"role": role})
    db.flush()
    db.commit()
    return target
