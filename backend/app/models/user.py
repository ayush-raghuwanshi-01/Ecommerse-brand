"""Users, roles, refresh/auth tokens, addresses."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.types import UTCDateTime
from app.models.base import Timestamps, UUIDPk, enum_col


class UserRole(StrEnum):
    customer = "customer"
    staff = "staff"
    manager = "manager"
    admin = "admin"


class AddressType(StrEnum):
    home = "home"
    work = "work"
    other = "other"


class AuthTokenPurpose(StrEnum):
    refresh = "refresh"
    password_reset = "password_reset"
    email_verify = "email_verify"


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_col(UserRole), default=UserRole.customer, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    addresses: Mapped[list["Address"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tokens: Mapped[list["AuthToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthToken(UUIDPk, Base):
    """Opaque token store: refresh rotation families, password resets, email verification."""

    __tablename__ = "auth_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[AuthTokenPurpose] = mapped_column(enum_col(AuthTokenPurpose), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str | None] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="tokens")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


class Address(UUIDPk, Timestamps, Base):
    __tablename__ = "addresses"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    address_type: Mapped[AddressType] = mapped_column(enum_col(AddressType), default=AddressType.home)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(120), index=True)
    postal_code: Mapped[str] = mapped_column(String(10), index=True)
    country: Mapped[str] = mapped_column(String(2), default="IN")
    is_default_shipping: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default_billing: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="addresses")

    def snapshot(self) -> dict:
        """Immutable copy stored on orders so history never drifts."""
        return {
            "full_name": self.full_name,
            "phone": self.phone,
            "line1": self.line1,
            "line2": self.line2,
            "landmark": self.landmark,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "address_type": self.address_type.value,
        }
