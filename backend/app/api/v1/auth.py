from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, request_context
from app.core.ratelimit import rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=TokenPair, status_code=201, dependencies=[Depends(rate_limit(10))])
def register(payload: RegisterRequest, request: Request, db: Db):
    _user, tokens = auth_service.register(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        request_meta=request_context(request),
    )
    db.commit()
    return tokens


@router.post("/login", response_model=TokenPair, dependencies=[Depends(rate_limit(10))])
def login(payload: LoginRequest, request: Request, db: Db):
    _user, tokens = auth_service.login(
        db, email=payload.email, password=payload.password, request_meta=request_context(request)
    )
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, request: Request, db: Db):
    _user, tokens = auth_service.rotate_refresh(
        db, payload.refresh_token, request_meta=request_context(request)
    )
    db.commit()
    return tokens


@router.post("/logout", response_model=Message)
def logout(payload: RefreshRequest, db: Db):
    auth_service.logout(db, payload.refresh_token)
    db.commit()
    return Message(message="Logged out.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.post("/password-reset/request", response_model=Message, dependencies=[Depends(rate_limit(5))])
def password_reset_request(payload: PasswordResetRequest, db: Db):
    auth_service.request_password_reset(db, payload.email)
    db.commit()
    return Message(message="If the account exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=Message)
def password_reset_confirm(payload: PasswordResetConfirm, db: Db):
    auth_service.reset_password(db, payload.token, payload.new_password)
    db.commit()
    return Message(message="Password updated. Please log in again.")


@router.post("/verify-email", response_model=Message)
def verify_email(token: str, db: Db):
    auth_service.verify_email(db, token)
    db.commit()
    return Message(message="Email verified.")


@router.post("/verify-email/request", response_model=Message)
def verify_email_request(user: CurrentUser, db: Db):
    auth_service.request_email_verification(db, user)
    db.commit()
    return Message(message="Verification email sent.")


@router.post("/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: Db):
    auth_service.change_password(db, user, payload.current_password, payload.new_password)
    db.commit()
    return Message(message="Password changed; other sessions were signed out.")
