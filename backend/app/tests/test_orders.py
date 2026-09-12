from sqlalchemy import select

from app.models.commerce import AuditLog
from app.models.order import Order, OrderStatus
from app.tests.conftest import _user, auth_headers, make_product, variant_of
from app.models.user import UserRole


def _cod_order(client, clean_db, product, customer_headers, address, qty=1, key="ord-1"):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": qty})
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": key},
                    json={"shipping_address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 201
    return r.json()["order"]


def test_staff_created_order_whatsapp_source(client, clean_db, product, staff_headers, customer):
    m = variant_of(product, "M")
    r = client.post("/api/v1/staff/orders", headers=staff_headers, json={
        "customer_id": customer.id,
        "order_source": "whatsapp",
        "lines": [{"variant_id": m.id, "qty": 2}],
        "shipping_address": {"full_name": customer.full_name, "phone": "9876500000",
                             "line1": "5 Store Lane", "city": "Bhopal", "state": "Madhya Pradesh",
                             "postal_code": "462001"},
        "payment_method": "cod",
        "internal_notes": "Customer ordered via WhatsApp",
    })
    assert r.status_code == 201, r.text
    order = r.json()["order"]
    assert order["order_source"] == "whatsapp"
    assert order["status"] == "confirmed"
    audit = clean_db.scalars(select(AuditLog).where(AuditLog.action == "order.create_staff")).all()
    assert len(audit) == 1


def test_staff_cannot_create_customer_without_record(client, clean_db, product, staff_headers):
    m = variant_of(product, "M")
    r = client.post("/api/v1/staff/orders", headers=staff_headers, json={
        "order_source": "physical_store",
        "lines": [{"variant_id": m.id, "qty": 1}],
        "shipping_address": {"full_name": "Walk In", "phone": "9876500000", "line1": "Store",
                             "city": "Bhopal", "state": "Madhya Pradesh", "postal_code": "462001"},
        "payment_method": "cod",
    })
    assert r.status_code == 422


def test_cod_confirm_commits_stock(client, clean_db, product, customer_headers, staff_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, qty=2, key="ord-2")
    clean_db.expire_all()
    m = variant_of(product, "M")
    assert m.reserved_qty == 2 and m.sold_qty == 0

    r = client.post(f"/api/v1/orders/{order['id']}/status", headers=staff_headers,
                    json={"status": "processing"})
    assert r.status_code == 200
    clean_db.expire_all()
    m = variant_of(product, "M")
    assert m.reserved_qty == 0 and m.sold_qty == 2


def test_status_transition_guard(client, clean_db, product, customer_headers, staff_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, key="ord-3")
    r = client.post(f"/api/v1/orders/{order['id']}/status", headers=staff_headers,
                    json={"status": "shipped"})  # skips processing/packed
    assert r.status_code == 422


def test_customer_cancel_before_packing_and_manager_approval(client, clean_db, product,
                                                             customer_headers, manager_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, key="ord-4")
    r = client.post(f"/api/v1/orders/me/{order['id']}/cancel-request", headers=customer_headers,
                    json={"reason": "changed_mind", "note": "please cancel"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancel_requested"
    r = client.post(f"/api/v1/orders/{order['id']}/cancel-decision", headers=manager_headers,
                    json={"approve": True})
    assert r.json()["status"] == "cancelled"
    clean_db.expire_all()
    assert variant_of(product, "M").reserved_qty == 0


def test_customer_cannot_cancel_after_packing(client, clean_db, product, customer_headers,
                                              staff_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, key="ord-5")
    for status in ("processing", "packed"):
        r = client.post(f"/api/v1/orders/{order['id']}/status", headers=staff_headers, json={"status": status})
        assert r.status_code == 200
    r = client.post(f"/api/v1/orders/me/{order['id']}/cancel-request", headers=customer_headers,
                    json={"reason": "changed_mind"})
    assert r.status_code == 422


def test_staff_cannot_edit_after_packing_but_manager_can(client, clean_db, product, customer_headers,
                                                         staff_headers, manager_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, key="ord-6")
    for status in ("processing", "packed"):
        client.post(f"/api/v1/orders/{order['id']}/status", headers=staff_headers, json={"status": status})
    payload = {"customer_notes": "changed by staff"}
    r = client.patch(f"/api/v1/orders/{order['id']}", headers=staff_headers, json=payload)
    assert r.status_code == 403
    r = client.patch(f"/api/v1/orders/{order['id']}", headers=manager_headers, json=payload)
    assert r.status_code == 200
    assert r.json()["customer_notes"] == "changed by staff"


def test_order_edit_revalidates_and_audits(client, clean_db, product, customer_headers,
                                           staff_headers, address):
    order = _cod_order(client, clean_db, product, customer_headers, address, qty=1, key="ord-7")
    item_id = order["items"][0]["id"]
    m = variant_of(product, "M")
    r = client.patch(f"/api/v1/orders/{order['id']}", headers=staff_headers, json={
        "line_updates": [{"order_item_id": item_id, "qty": 4}],
    })
    assert r.status_code == 200
    edited = r.json()
    assert edited["items"][0]["qty"] == 4
    assert edited["grand_total_paise"] > order["grand_total_paise"]
    clean_db.expire_all()
    assert variant_of(product, "M").reserved_qty == 4
    audits = clean_db.scalars(select(AuditLog).where(AuditLog.action == "order.edit")).all()
    assert audits and audits[0].before_json is not None


def test_edit_beyond_stock_fails(client, clean_db, warehouse, customer_headers, staff_headers, address):
    product = make_product(clean_db, name="Tiny Stock", stock={"M": 2})
    clean_db.commit()
    order = _cod_order(client, clean_db, product, customer_headers, address, qty=1, key="ord-8")
    item_id = order["items"][0]["id"]
    r = client.patch(f"/api/v1/orders/{order['id']}", headers=staff_headers, json={
        "line_updates": [{"order_item_id": item_id, "qty": 9}],
    })
    assert r.status_code == 409


def test_audit_log_records_manager_actions(client, clean_db, product, manager_headers, manager):
    r = client.post("/api/v1/products", headers=manager_headers, json={
        "name": "Audit Coat", "base_price_paise": 150000})
    assert r.status_code == 201
    audits = clean_db.scalars(select(AuditLog).where(AuditLog.action == "product.create")).all()
    assert audits[0].user_id == manager.id
    assert audits[0].role == "manager"
    assert audits[0].ip is not None
