"""Authentication: register/login, refresh rotation with reuse detection,
password reset, email verification."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.database import utcnow
from app.core.exceptions import AuthenticationError, ConflictError, TokenError
from app.models.user import AuthToken, AuthTokenPurpose, User, UserRole
from app.services import notification_service


def create_customer_record(
    db: Session, *, email: str, full_name: str, phone: str | None = None, password: str | None = None
) -> User:
    email = email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("An account with this email already exists.")
    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        password_hash=security.hash_password(password or _temporary_password()),
        role=UserRole.customer,
    )
    db.add(user)
    db.flush()
    return user


def _temporary_password() -> str:
    import secrets

    return secrets.token_urlsafe(12)


def register(db: Session, *, email: str, password: str, full_name: str, phone: str | None,
             request_meta: dict | None = None) -> tuple[User, dict]:
    user = create_customer_record(db, email=email, full_name=full_name, phone=phone, password=password)
    verify_raw = _issue_token(db, user, AuthTokenPurpose.email_verify, family=None)
    notification_service.notify(
        db, event_type="account_created", recipient=user.email,
        payload={"subject": "Welcome to Black House", "verify_token": verify_raw},
    )
    tokens = issue_session(db, user, request_meta=request_meta)
    return user, tokens


def issue_session(db: Session, user: User, *, request_meta: dict | None = None) -> dict:
    refresh_raw = _issue_token(db, user, AuthTokenPurpose.refresh, family=security.generate_family_id())
    return {
        "access_token": security.create_access_token(user_id=user.id, role=user.role.value),
        "refresh_token": refresh_raw,
        "token_type": "bearer",
        "expires_in_seconds": settings.access_token_expire_minutes * 60,
    }


def _issue_token(db: Session, user: User, purpose: AuthTokenPurpose, *, family: str | None = None,
                 request_meta: dict | None = None) -> str:
    raw, digest = security.generate_opaque_token()
    if purpose == AuthTokenPurpose.refresh:
        expires = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    elif purpose == AuthTokenPurpose.password_reset:
        expires = utcnow() + timedelta(hours=2)
    else:
        expires = utcnow() + timedelta(days=7)
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=digest,
            family_id=family,
            expires_at=expires,
            user_agent=(request_meta or {}).get("user_agent"),
            ip=(request_meta or {}).get("ip"),
        )
    )
    db.flush()
    return raw


def login(db: Session, *, email: str, password: str, request_meta: dict | None = None) -> tuple[User, dict]:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not security.verify_password(password, user.password_hash):
        raise AuthenticationError("Incorrect email or password.")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.")
    return user, issue_session(db, user, request_meta=request_meta)


def rotate_refresh(db: Session, raw_refresh: str, request_meta: dict | None = None) -> tuple[User, dict]:
    digest = security.hash_token(raw_refresh)
    token = db.scalar(select(AuthToken).where(AuthToken.token_hash == digest))
    if token is None or token.purpose != AuthTokenPurpose.refresh:
        raise TokenError("Refresh token is invalid.")
    if token.revoked_at or token.used_at:
        # Reuse detected: revoke the whole family (stolen-token mitigation).
        if token.family_id:
            for t in db.scalars(
                select(AuthToken).where(AuthToken.family_id == token.family_id)
            ):
                t.revoked_at = utcnow()
        db.commit()  # security-critical revocation must survive the error response
        raise TokenError("Refresh token reuse detected; session family revoked.")
    if token.expires_at < utcnow():
        raise TokenError("Refresh token expired.")
    token.used_at = utcnow()
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account unavailable.")
    new_raw = _issue_token(db, user, AuthTokenPurpose.refresh, family=token.family_id, request_meta=request_meta)
    return user, {
        "access_token": security.create_access_token(user_id=user.id, role=user.role.value),
        "refresh_token": new_raw,
        "token_type": "bearer",
        "expires_in_seconds": settings.access_token_expire_minutes * 60,
    }


def logout(db: Session, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    digest = security.hash_token(raw_refresh)
    token = db.scalar(select(AuthToken).where(AuthToken.token_hash == digest))
    if token and token.family_id:
        for t in db.scalars(select(AuthToken).where(AuthToken.family_id == token.family_id)):
            t.revoked_at = utcnow()
    elif token:
        token.revoked_at = utcnow()
    db.flush()


def revoke_all_sessions(db: Session, user: User) -> None:
    for t in db.scalars(
        select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == AuthTokenPurpose.refresh)
    ):
        t.revoked_at = utcnow()
    db.flush()


def request_password_reset(db: Session, email: str) -> None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None:
        return  # do not leak account existence
    raw = _issue_token(db, user, AuthTokenPurpose.password_reset)
    notification_service.notify(
        db, event_type="password_reset_requested", recipient=user.email,
        payload={"subject": "Reset your Black House password", "reset_token": raw},
    )


def reset_password(db: Session, token: str, new_password: str) -> None:
    digest = security.hash_token(token)
    row = db.scalar(
        select(AuthToken).where(AuthToken.token_hash == digest, AuthToken.purpose == AuthTokenPurpose.password_reset)
    )
    if row is None or row.used_at or row.revoked_at or row.expires_at < utcnow():
        raise TokenError("Reset token is invalid or expired.")
    user = db.get(User, row.user_id)
    user.password_hash = security.hash_password(new_password)
    row.used_at = utcnow()
    revoke_all_sessions(db, user)
    db.flush()


def request_email_verification(db: Session, user: User) -> None:
    raw = _issue_token(db, user, AuthTokenPurpose.email_verify)
    notification_service.notify(
        db, event_type="account_created", recipient=user.email,
        payload={"subject": "Verify your email", "verify_token": raw},
    )


def verify_email(db: Session, token: str) -> User:
    digest = security.hash_token(token)
    row = db.scalar(
        select(AuthToken).where(AuthToken.token_hash == digest, AuthToken.purpose == AuthTokenPurpose.email_verify)
    )
    if row is None or row.used_at or row.expires_at < utcnow():
        raise TokenError("Verification token is invalid or expired.")
    user = db.get(User, row.user_id)
    user.is_email_verified = True
    row.used_at = utcnow()
    db.flush()
    return user


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not security.verify_password(current, user.password_hash):
        raise AuthenticationError("Current password is incorrect.")
    user.password_hash = security.hash_password(new)
    revoke_all_sessions(db, user)
    db.flush()
