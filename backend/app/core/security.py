"""Password hashing (Argon2id), JWT access tokens, opaque refresh/reset tokens."""

import hashlib
import secrets
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.database import utcnow
from app.core.exceptions import TokenError

_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def create_access_token(*, user_id: str, role: str, expires_minutes: int | None = None) -> str:
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)).timestamp()
        ),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("Access token is invalid or expired.") from exc
    if payload.get("type") != "access":
        raise TokenError("Wrong token type.")
    return payload


def generate_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash) — only the hash is stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_family_id() -> str:
    return secrets.token_hex(8)
