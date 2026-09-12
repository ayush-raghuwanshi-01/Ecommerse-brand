from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    is_email_verified: bool


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class RoleUpdate(BaseModel):
    role: str


class AddressBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=8, max_length=20)
    line1: str = Field(min_length=3, max_length=255)
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str
    postal_code: str = Field(pattern=r"^[1-9][0-9]{5}$")  # Indian PIN
    country: str = "IN"
    address_type: str = "home"
    is_default_shipping: bool = False
    is_default_billing: bool = False


class AddressOut(ORMModel):
    id: str
    address_type: str
    full_name: str
    phone: str
    line1: str
    line2: str | None
    landmark: str | None
    city: str
    state: str
    postal_code: str
    country: str
    is_default_shipping: bool
    is_default_billing: bool
