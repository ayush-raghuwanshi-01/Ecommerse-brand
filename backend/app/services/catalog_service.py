"""Catalog rules: public visibility, upcoming/pre-order behaviour, variant states."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError, PolicyError
from app.models.catalog import Product, ProductStatus, ProductVariant


def public_product_query(db: Session):
    """Only active / upcoming / restock-flagged out-of-stock products are public."""
    stmt = select(Product).options(joinedload(Product.variants), joinedload(Product.images))
    return stmt


def is_publicly_visible(product: Product) -> bool:
    return product.publicly_visible


def get_public_product(db: Session, slug: str) -> Product:
    product = db.scalar(
        select(Product)
        .options(joinedload(Product.variants), joinedload(Product.images))
        .where(Product.slug == slug)
    )
    if product is None or not product.publicly_visible:
        raise NotFoundError("Product not found.")
    return product


def assert_purchasable(db: Session, product: Product, variant: ProductVariant) -> None:
    """Business rules for adding to cart / ordering a variant."""
    if not variant.is_active:
        raise PolicyError("This size is currently unavailable.", details={"sku": variant.sku})
    if product.status == ProductStatus.upcoming:
        if not (product.preorder_open and (variant.is_preorder or product.is_preorder)):
            raise PolicyError(
                "This piece launches soon and is not purchasable yet.",
                details={"slug": product.slug},
            )
    if product.status == ProductStatus.archived:
        raise PolicyError("This product is no longer available.")
    if not variant.is_purchasable and not variant.is_preorder:
        raise PolicyError("This size cannot be purchased right now.", details={"sku": variant.sku})


def primary_image_url(product: Product) -> str | None:
    primary = next((i for i in product.images if i.is_primary), None)
    return (primary or (product.images[0] if product.images else None)).url if product.images else None
