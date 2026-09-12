"""Shared schema primitives. All money values are integer paise."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class Totals(BaseModel):
    subtotal_paise: int
    discount_paise: int
    shipping_paise: int
    tax_paise: int
    grand_total_paise: int
    currency: str = "INR"


class Message(BaseModel):
    message: str
    detail: dict[str, Any] | None = None
