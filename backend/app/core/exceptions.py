"""Application error taxonomy + FastAPI handlers.

All errors serialize as:
    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base business error."""

    code = "INTERNAL_ERROR"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, details: dict[str, Any] | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class AuthenticationError(AppError):
    code = "AUTHENTICATION_FAILED"
    status_code = 401


class TokenError(AuthenticationError):
    code = "INVALID_TOKEN"


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
    status_code = 403


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409


class InsufficientStockError(ConflictError):
    code = "INSUFFICIENT_STOCK"


class PriceChangedError(ConflictError):
    code = "PRICE_CHANGED"


class CouponError(ValidationError):
    code = "COUPON_INVALID"


class ShippingError(ValidationError):
    code = "ADDRESS_NOT_SERVICEABLE"


class PolicyError(ValidationError):
    code = "POLICY_VIOLATION"


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    status_code = 429


class ProviderNotConfiguredError(AppError):
    code = "PROVIDER_NOT_CONFIGURED"
    status_code = 503


def _payload(code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": {"code": code, "message": message, "details": details or {}}})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                }
            },
        )
