"""Pagination / filtering / sorting helpers shared by list endpoints."""

from typing import Any, TypeVar

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

MAX_PAGE_SIZE = 100


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
        sort_by: str | None = Query(None),
        sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
        q: str | None = Query(None, description="Free-text search (endpoint-defined fields)"),
    ):
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.sort_dir = sort_dir
        self.q = q


def paginate(db: Session, stmt: Select, params: PageParams, sort_columns: dict[str, Any] | None = None):
    """Apply sorting + pagination. Returns (items, total)."""
    if params.sort_by and sort_columns and params.sort_by in sort_columns:
        col = sort_columns[params.sort_by]
        stmt = stmt.order_by(col.desc() if params.sort_dir == "desc" else col.asc())
    # Count via subquery: `with_only_columns(func.count())` implicitly groups by
    # the entity PK and returns wrong totals for ORM selects.
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    stmt = stmt.offset((params.page - 1) * params.page_size).limit(params.page_size)
    return db.scalars(stmt).unique().all(), total


def page_meta(params: PageParams, total: int) -> dict:
    pages = (total + params.page_size - 1) // params.page_size if total else 0
    return {"page": params.page, "page_size": params.page_size, "total": total, "pages": pages}
