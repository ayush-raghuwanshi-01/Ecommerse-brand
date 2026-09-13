"""Development seed: warehouse, users, catalogue, shipping rules, coupon, settings.

Run:  python -m scripts.seed_dev
Idempotent: skips when the admin user already exists.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.catalog import (  # noqa: E402
    Category,
    Collection,
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    VariantSize,
)
from app.models.commerce import Coupon, ShippingRule, ShippingRuleKind  # noqa: E402
from app.models.inventory import Warehouse  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services import settings_service  # noqa: E402

SIZES = [VariantSize.XS, VariantSize.S, VariantSize.M, VariantSize.L, VariantSize.XL, VariantSize.XXL]

# Placeholder artwork is generated as SVG (no image library needed) so the seeded
# catalogue renders instead of showing broken <img> icons in development.
SEED_IMAGE_DIR = "seed"


def _placeholder_svg(name: str, short: str) -> str:
    """A branded stand-in for real product photography."""
    from xml.sax.saxutils import escape

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1000" width="800" height="1000">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#17140f"/>
      <stop offset="100%" stop-color="#0b0a08"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#c9a24b" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#c9a24b" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="800" height="1000" fill="url(#bg)"/>
  <circle cx="620" cy="250" r="230" fill="url(#sheen)"/>
  <rect x="1" y="1" width="798" height="998" fill="none" stroke="#2b2620" stroke-width="2"/>
  <text x="400" y="470" text-anchor="middle" fill="#ece4d3"
        font-family="Georgia, 'Times New Roman', serif" font-size="52">{escape(name)}</text>
  <text x="400" y="530" text-anchor="middle" fill="#9a8f7a"
        font-family="Helvetica, Arial, sans-serif" font-size="24">{escape(short)}</text>
  <text x="400" y="620" text-anchor="middle" fill="#c9a24b"
        font-family="Helvetica, Arial, sans-serif" font-size="16"
        letter-spacing="6">BLACK HOUSE · PLACEHOLDER</text>
</svg>
"""


def write_seed_images(products) -> None:
    """Write one placeholder SVG per product into the configured local storage path.

    Skipped when a non-local storage provider is configured (the files would be
    unreachable) or when the image already exists.
    """
    from app.core.config import settings

    if settings.storage_provider != "local":
        print("STORAGE_PROVIDER is not local — skipping placeholder image generation")
        return

    target = Path(settings.storage_local_path) / SEED_IMAGE_DIR
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for slug, name, short in products:
        path = target / f"{slug}.svg"
        if path.exists():
            continue
        path.write_text(_placeholder_svg(name, short), encoding="utf-8")
        written += 1
    print(f"wrote {written} placeholder image(s) to {target}")


PRODUCTS = [
    ("The Waypoint", "Double-faced wool overcoat", 1850000, "active", {"M": 6, "L": 4, "XL": 2}),
    ("The Longline", "Extra-long belted wool trench", 2400000, "active", {"S": 3, "M": 5, "L": 0}),
    ("The Transit", "Utilitarian wool travel jacket", 2150000, "active", {"M": 8, "L": 6, "XL": 3}),
    ("The Field Coat", "Heavyweight cotton field coat", 2800000, "active", {"S": 2, "M": 2, "L": 1}),
    ("The Rook", "Cropped wool bomber", 1680000, "out_of_stock", {}),
    ("The Overcast", "Water-resistant stone mac", 2250000, "upcoming", {}),
]


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.role == UserRole.admin)):
            print("already seeded")
            return

        warehouse = Warehouse(
            name="Bhopal Fulfilment Centre",
            city="Bhopal",
            state="Madhya Pradesh",
            country="IN",
            is_default=True,
        )
        db.add(warehouse)

        users = {
            "admin": User(
                email="admin@blackhouse.example",
                full_name="Owner",
                role=UserRole.admin,
                password_hash=hash_password("Admin@12345"),
            ),
            "manager": User(
                email="manager@blackhouse.example",
                full_name="Store Manager",
                role=UserRole.manager,
                password_hash=hash_password("Manager@12345"),
            ),
            "staff": User(
                email="staff@blackhouse.example",
                full_name="Floor Staff",
                role=UserRole.staff,
                password_hash=hash_password("Staff@12345"),
            ),
            "customer": User(
                email="customer@example.com",
                full_name="Asha Verma",
                role=UserRole.customer,
                phone="9876543210",
                password_hash=hash_password("Customer@12345"),
            ),
        }
        db.add_all(users.values())

        category = Category(name="Outerwear", slug="outerwear")
        collection = Collection(
            name="Autumn—Winter 24/25", slug="aw-24-25", description="Small-batch winter layers."
        )
        db.add_all([category, collection])
        db.flush()

        seeded_images: list[tuple[str, str, str]] = []

        for idx, (name, short, price, status, stock) in enumerate(PRODUCTS):
            product = Product(
                name=name,
                slug=name.lower().replace("the ", "").replace(" ", "-"),
                short_description=short,
                description=f"{name}: {short}. Cut in Bhopal in limited runs, numbered by hand.",
                status=ProductStatus(status),
                product_type="overcoat" if "coat" in name.lower() or "trench" in short else "jacket",
                category_id=category.id,
                collection_id=collection.id,
                fabric="100% heavyweight wool" if idx % 2 == 0 else "Wool-cotton blend",
                care_instructions="Dry clean only. Store on a wide hanger.",
                size_guide="True to size. Size up for layering.",
                base_price_paise=price,
                gst_percentage=5.0,
                is_preorder=status == "upcoming",
                preorder_fulfillment_note="Pre-orders ship in 4–6 weeks." if status == "upcoming" else None,
                restock_expected_at=None,
                restock_note="Restocking next batch." if status == "out_of_stock" else None,
                is_sale_item=name == "The Rook",
            )
            db.add(product)
            db.flush()
            db.add(
                ProductImage(
                    product_id=product.id,
                    url=f"/static/uploads/{SEED_IMAGE_DIR}/{product.slug}.svg",
                    alt_text=f"{name} on model",
                    is_primary=True,
                    sort_order=0,
                )
            )
            seeded_images.append((product.slug, name, short))
            for order, size in enumerate(SIZES):
                qty = stock.get(size.value if hasattr(size, "value") else size, 0)
                db.add(
                    ProductVariant(
                        product_id=product.id,
                        sku=f"BH-{product.slug[:6].upper()}-{size.value}",
                        size=size,
                        price_paise=price + (50000 if size in (VariantSize.XL, VariantSize.XXL) else 0),
                        gst_percentage=5.0,
                        stock_qty=qty,
                        is_purchasable=status != "upcoming",
                        is_preorder=status == "upcoming",
                        warehouse_id=warehouse.id,
                        sort_order=order,
                    )
                )

        db.add_all(
            [
                ShippingRule(kind=ShippingRuleKind.blocked, pincode_from="190000", pincode_to="194999"),
                ShippingRule(kind=ShippingRuleKind.rate_state, state="Madhya Pradesh", charge_paise=4900),
                ShippingRule(
                    kind=ShippingRuleKind.rate_pincode,
                    pincode_from="462001",
                    pincode_to="462999",
                    charge_paise=0,
                ),
            ]
        )
        db.add(
            Coupon(
                code="WELCOME500",
                discount_type="fixed",
                discount_value=50000,
                min_order_paise=1000000,
                usage_limit=500,
                per_customer_limit=1,
            )
        )
        db.flush()
        settings_service.set_setting(db, "free_shipping_threshold_paise", 1500000)
        db.commit()

        # Written after the commit so a failed transaction leaves no orphan files.
        write_seed_images(seeded_images)
        print("seeded: 4 users, 6 products, warehouse Bhopal, coupon WELCOME500")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
