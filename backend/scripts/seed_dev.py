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

        warehouse = Warehouse(name="Bhopal Fulfilment Centre", city="Bhopal",
                              state="Madhya Pradesh", country="IN", is_default=True)
        db.add(warehouse)

        users = {
            "admin": User(email="admin@blackhouse.example", full_name="Owner", role=UserRole.admin,
                          password_hash=hash_password("Admin@12345")),
            "manager": User(email="manager@blackhouse.example", full_name="Store Manager", role=UserRole.manager,
                            password_hash=hash_password("Manager@12345")),
            "staff": User(email="staff@blackhouse.example", full_name="Floor Staff", role=UserRole.staff,
                          password_hash=hash_password("Staff@12345")),
            "customer": User(email="customer@example.com", full_name="Asha Verma", role=UserRole.customer,
                             phone="9876543210", password_hash=hash_password("Customer@12345")),
        }
        db.add_all(users.values())

        category = Category(name="Outerwear", slug="outerwear")
        collection = Collection(name="Autumn—Winter 24/25", slug="aw-24-25",
                                description="Small-batch winter layers.")
        db.add_all([category, collection])
        db.flush()

        for idx, (name, short, price, status, stock) in enumerate(PRODUCTS):
            product = Product(
                name=name, slug=name.lower().replace("the ", "").replace(" ", "-"),
                short_description=short,
                description=f"{name}: {short}. Cut in Bhopal in limited runs, numbered by hand.",
                status=ProductStatus(status),
                product_type="overcoat" if "coat" in name.lower() or "trench" in short else "jacket",
                category_id=category.id, collection_id=collection.id,
                fabric="100% heavyweight wool" if idx % 2 == 0 else "Wool-cotton blend",
                care_instructions="Dry clean only. Store on a wide hanger.",
                size_guide="True to size. Size up for layering.",
                base_price_paise=price, gst_percentage=5.0,
                is_preorder=status == "upcoming",
                preorder_fulfillment_note="Pre-orders ship in 4–6 weeks." if status == "upcoming" else None,
                restock_expected_at=None,
                restock_note="Restocking next batch." if status == "out_of_stock" else None,
                is_sale_item=name == "The Rook",
            )
            db.add(product)
            db.flush()
            db.add(ProductImage(product_id=product.id, url=f"/static/uploads/seed/{product.slug}.jpg",
                                alt_text=f"{name} on model", is_primary=True, sort_order=0))
            for order, size in enumerate(SIZES):
                qty = stock.get(size.value if hasattr(size, "value") else size, 0)
                db.add(ProductVariant(
                    product_id=product.id, sku=f"BH-{product.slug[:6].upper()}-{size.value}",
                    size=size, price_paise=price + (50000 if size in (VariantSize.XL, VariantSize.XXL) else 0),
                    gst_percentage=5.0, stock_qty=qty,
                    is_purchasable=status != "upcoming",
                    is_preorder=status == "upcoming",
                    warehouse_id=warehouse.id, sort_order=order,
                ))

        db.add_all([
            ShippingRule(kind=ShippingRuleKind.blocked, pincode_from="190000", pincode_to="194999"),
            ShippingRule(kind=ShippingRuleKind.rate_state, state="Madhya Pradesh", charge_paise=4900),
            ShippingRule(kind=ShippingRuleKind.rate_pincode, pincode_from="462001", pincode_to="462999",
                         charge_paise=0),
        ])
        db.add(Coupon(code="WELCOME500", discount_type="fixed", discount_value=50000,
                      min_order_paise=1000000, usage_limit=500, per_customer_limit=1))
        db.flush()
        settings_service.set_setting(db, "free_shipping_threshold_paise", 1500000)
        db.commit()
        print("seeded: 4 users, 6 products, warehouse Bhopal, coupon WELCOME500")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
