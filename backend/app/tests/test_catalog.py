from datetime import timedelta

from app.core.database import utcnow
from app.models.catalog import ProductStatus
from app.tests.conftest import make_product, variant_of


def test_public_visibility_rules(client, clean_db, warehouse):
    make_product(clean_db, name="Active Coat", status=ProductStatus.active)
    make_product(clean_db, name="Draft Coat", status=ProductStatus.draft)
    make_product(clean_db, name="Archived Coat", status=ProductStatus.archived)
    make_product(clean_db, name="Upcoming Coat", status=ProductStatus.upcoming, preorder=True)
    make_product(clean_db, name="OOS Coat", status=ProductStatus.out_of_stock, stock={})
    silent = make_product(clean_db, name="OOS Silent Coat", status=ProductStatus.out_of_stock, stock={})
    silent.restock_note = None
    clean_db.commit()

    slugs = {p["slug"] for p in client.get("/api/v1/products?page_size=50").json()["items"]}
    assert "active-coat" in slugs
    assert "upcoming-coat" in slugs
    assert "oos-coat" in slugs  # visible: has restock info
    assert "oos-silent-coat" not in slugs  # hidden: no restock info
    assert "draft-coat" not in slugs
    assert "archived-coat" not in slugs


def test_upcoming_not_purchasable_unless_preorder(client, clean_db, warehouse, customer_headers):
    upcoming = make_product(clean_db, name="Launch Coat", status=ProductStatus.upcoming, preorder=False)
    pre = make_product(
        clean_db,
        name="Preorder Coat",
        status=ProductStatus.upcoming,
        preorder=True,
        stock={},
    )
    clean_db.commit()
    r = client.post(
        "/api/v1/carts/me/items",
        headers=customer_headers,
        json={"variant_id": variant_of(upcoming, "M").id, "qty": 1},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "POLICY_VIOLATION"

    r = client.post(
        "/api/v1/carts/me/items",
        headers=customer_headers,
        json={"variant_id": variant_of(pre, "M").id, "qty": 1},
    )
    assert r.status_code == 201
    assert r.json()["items"][0]["is_preorder"] is True


def test_preorder_window_respected(client, clean_db, warehouse, customer_headers):
    pre = make_product(clean_db, name="Future Coat", status=ProductStatus.upcoming, preorder=True, stock={})
    pre.preorder_start_at = utcnow() + timedelta(days=5)
    clean_db.commit()
    r = client.post(
        "/api/v1/carts/me/items",
        headers=customer_headers,
        json={"variant_id": variant_of(pre, "M").id, "qty": 1},
    )
    assert r.status_code == 422


def test_disabled_variants_visible_but_blocked(client, clean_db, warehouse, customer_headers):
    product = make_product(clean_db, name="Mixed Coat")
    xs = variant_of(product, "XS")
    xs.is_active = False
    clean_db.commit()
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    sizes = {v["size"]: v for v in detail["variants"]}
    assert sizes["XS"]["availability"] == "disabled"
    assert sizes["M"]["availability"] == "available"
    r = client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": xs.id, "qty": 1})
    assert r.status_code == 422


def test_size_specific_pricing(client, clean_db, warehouse):
    product = make_product(clean_db, name="Priced Coat", price=199900)
    clean_db.commit()
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    prices = {v["size"]: v["price_paise"] for v in detail["variants"]}
    assert prices["M"] == 199900
    assert prices["XL"] == 209900  # size surcharge from factory


def test_out_of_stock_variant_state(client, clean_db, warehouse):
    product = make_product(clean_db, name="Empty Coat", stock={"M": 0})
    clean_db.commit()
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert detail["variants"][0]["availability"] in ("out_of_stock", "upcoming")
