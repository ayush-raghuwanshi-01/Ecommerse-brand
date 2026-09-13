"""Categories & collections: public reads, manager writes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ManagerUser
from app.models.catalog import Category, Collection
from app.schemas.catalog import CategoryCreate, CategoryOut, CollectionCreate, CollectionOut

router = APIRouter(tags=["taxonomy"])
Db = Annotated[Session, Depends(get_db)]


def _slugify(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Db):
    return db.scalars(select(Category).where(Category.is_active.is_(True))).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, manager: ManagerUser, db: Db):
    category = Category(name=payload.name, slug=payload.slug or _slugify(payload.name),
                        parent_id=payload.parent_id)
    db.add(category)
    db.commit()
    return category


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(db: Db):
    return db.scalars(select(Collection).where(Collection.is_active.is_(True))).all()


@router.post("/collections", response_model=CollectionOut, status_code=201)
def create_collection(payload: CollectionCreate, manager: ManagerUser, db: Db):
    collection = Collection(name=payload.name, slug=payload.slug or _slugify(payload.name),
                            description=payload.description)
    db.add(collection)
    db.commit()
    return collection
