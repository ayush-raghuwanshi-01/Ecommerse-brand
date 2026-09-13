import json
from datetime import timedelta

from sqlalchemy import select

from app.core.database import utcnow
from app.models.catalog import ProductStatus
from app.models.commerce import Coupon
from app.models.order import Order, OrderStatus
from app.tests.conftest import make_product, variant_of


def _add(client, headers, variant_id, qty=1):
    return client.post("/api/v1/carts/me/items", headers=headers, json={"variant_id": variant_id, "qty": qty})


def test_cart_requires_auth(client, product):
    r = client.get("/api/v1/carts/me")
    assert r.status_code == 401


def test_cart_crud_and_totals(client, clean_db, product, customer_headers):
    m = variant_of(product, "M")
    r = _add(client, customer_headers, m.id, 2)
    assert r.status_code == 201
    cart = r.json()
    assert cart["totals"]["subtotal_paise"] == m.price_paise * 2
    item_id = cart["items"][0]["id"]

    r = client.patch(f"/api/v1/carts/me/items/{item_id}", headers=customer_headers, json={"qty": 3})
    assert r.json()["totals"]["subtotal_paise"] == m.price_paise * 3

    r = client.delete(f"/api/v1/carts/me/items/{item_id}", headers=customer_headers)
    assert r.json()["items"] == []


def test_price_change_surfaced_and_blocks_checkout(client, clean_db, product, customer_headers, manager_headers, address):
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)
    # manager changes price
    r = client.patch(f"/api/v1/products/variants/{m.id}", headers=manager_headers,
                     json={"price_paise": m.price_paise + 50000})
    assert r.status_code == 200

    preview = client.get("/api/v1/checkout/preview", headers=customer_headers).json()
    assert preview["price_changes"], "price change must be surfaced before payment"
    assert preview["checkout_blocked"] is True

    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "pc-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PRICE_CHANGED"


def test_coupon_validation_matrix(client, clean_db, product, customer_headers, manager_headers, address):
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)

    # expired
    clean_db.add(Coupon(code="EXPIRED", discount_type="fixed", discount_value=10000,
                        expires_at=utcnow() - timedelta(days=1)))
    # min order
    clean_db.add(Coupon(code="BIGONLY", discount_type="fixed", discount_value=10000, min_order_paise=99_000_00))
    # usage limit reached
    clean_db.add(Coupon(code="ONCE", discount_type="fixed", discount_value=10000, usage_limit=0))
    # product specific, wrong product
    clean_db.add(Coupon(code="OTHERPROD", discount_type="fixed", discount_value=10000,
                        eligible_product_ids=["does-not-exist"]))
    # good one
    clean_db.add(Coupon(code="SAVE10", discount_type="percentage", discount_value=1000,  # 10%
                        max_discount_paise=50000))
    clean_db.commit()

    for code in ("EXPIRED", "BIGONLY", "ONCE", "OTHERPROD"):
        r = client.post("/api/v1/carts/me/coupon", headers=customer_headers, json={"code": code})
        assert r.status_code == 422, code

    r = client.post("/api/v1/carts/me/coupon", headers=customer_headers, json={"code": "SAVE10"})
    assert r.status_code == 200
    cart = r.json()
    assert cart["totals"]["discount_paise"] == int(m.price_paise * 0.10)

    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "cp-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 201
    order = r.json()["order"]
    assert order["discount_paise"] == int(m.price_paise * 0.10)


def test_pincode_blocked_rejects_checkout(client, clean_db, product, customer_headers, admin_headers, address):
    r = client.post("/api/v1/admin/shipping-rules", headers=admin_headers,
                    json={"kind": "blocked", "pincode_from": "462001", "pincode_to": "462001"})
    assert r.status_code == 201
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "pin-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "POLICY_VIOLATION"


def test_insufficient_stock_blocks_checkout(client, clean_db, warehouse, customer_headers, address):
    product = make_product(clean_db, name="Scarce Coat", stock={"M": 1})
    clean_db.commit()
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 5)
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "stock-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSUFFICIENT_STOCK"


def test_unavailable_item_stays_in_cart_but_blocks(client, clean_db, warehouse, customer_headers):
    product = make_product(clean_db, name="Vanish Coat", stock={"M": 2})
    clean_db.commit()
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 2)
    m.stock_qty = 0
    clean_db.commit()
    cart = client.get("/api/v1/carts/me", headers=customer_headers).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["is_available"] is False
    assert cart["checkout_blocked"] is True


def test_duplicate_checkout_prevented_by_idempotency_key(client, clean_db, product, customer_headers, address):
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)
    payload = {"shipping_address_id": address.id, "payment_method": "cod"}
    h = {**customer_headers, "Idempotency-Key": "dup-1"}
    r1 = client.post("/api/v1/checkout/orders", headers=h, json=payload)
    r2 = client.post("/api/v1/checkout/orders", headers=h, json=payload)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["order"]["number"] == r2.json()["order"]["number"]
    # different payload with same key → conflict
    r3 = client.post("/api/v1/checkout/orders", headers=h,
                     json={**payload, "customer_notes": "changed"})
    assert r3.status_code == 409


def test_cod_order_created_with_reservation(client, clean_db, product, customer_headers, address):
    m = variant_of(product, "M")
    before = m.available_qty
    _add(client, customer_headers, m.id, 2)
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "cod-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 201
    order = r.json()["order"]
    assert order["status"] == "confirmed"
    assert order["payment_status"] == "pending_cod"
    clean_db.expire_all()
    assert variant_of(product, "M").reserved_qty == 2
    assert variant_of(product, "M").stock_qty == before  # not reduced yet


def test_prepaid_order_and_payment_session(client, clean_db, product, customer_headers, address):
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "pre-1"},
                    json={"shipping_address_id": address.id, "payment_method": "upi"})
    assert r.status_code == 201
    body = r.json()
    assert body["requires_payment"] is True
    assert body["payment_session"]["mock"] is True
    assert body["order"]["status"] == "pending_payment"


def test_order_items_are_snapshots(client, clean_db, product, customer_headers, manager_headers, address):
    m = variant_of(product, "M")
    _add(client, customer_headers, m.id, 1)
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": "snap-1"},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    order_id = r.json()["order"]["id"]
    snapshot_name = r.json()["order"]["items"][0]["product_name"]
    snapshot_price = r.json()["order"]["items"][0]["unit_price_paise"]
    # rename + reprice product afterwards
    client.patch(f"/api/v1/products/{product.id}", headers=manager_headers, json={"name": "Renamed Coat"})
    client.patch(f"/api/v1/products/variants/{m.id}", headers=manager_headers, json={"price_paise": 1})
    r = client.get(f"/api/v1/orders/me/{order_id}", headers=customer_headers)
    item = r.json()["items"][0]
    assert item["product_name"] == snapshot_name
    assert item["unit_price_paise"] == snapshot_price
