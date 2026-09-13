"""AuthN/AuthZ dependencies: current user, role guards, request context."""

from enum import IntEnum
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models.user import User, UserRole

_bearer = HTTPBearer(auto_error=False)


class RoleLevel(IntEnum):
    customer = 0
    staff = 1
    manager = 2
    admin = 3


def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if creds is None:
        raise AuthenticationError("Not authenticated.")
    payload = decode_access_token(creds.credentials)
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is disabled.")
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Guard factory. Roles are treated as a hierarchy floor unless explicit.

    require_roles(UserRole.staff) -> staff, manager, admin
    require_roles(UserRole.customer) -> customers only (exact)
    """
    allowed = set(roles)
    hierarchical = UserRole.customer not in allowed

    def guard(user: CurrentUser) -> User:
        if hierarchical:
            if RoleLevel[user.role.value] < min(RoleLevel[r.value] for r in allowed):
                raise PermissionDeniedError("You do not have permission to perform this action.")
        elif user.role not in allowed:
            raise PermissionDeniedError("You do not have permission to perform this action.")
        return user

    return Depends(guard)


StaffUser = Annotated[User, require_roles(UserRole.staff)]
ManagerUser = Annotated[User, require_roles(UserRole.manager)]
AdminUser = Annotated[User, require_roles(UserRole.admin)]
CustomerUser = Annotated[User, require_roles(UserRole.customer)]


def request_context(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
