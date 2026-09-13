from app.tests.conftest import variant_of


def test_bulk_enquiry_pipeline(client, clean_db, staff_headers):
    r = client.post(
        "/api/v1/bulk-enquiries",
        json={
            "name": "Ritu Kapoor",
            "business_name": "Kapoor Hotels",
            "email": "ritu@kapoorhotels.in",
            "phone": "9812345678",
            "product_interest": "The Field Coat",
            "estimated_qty": 40,
            "message": "Uniforms for front desk staff.",
        },
    )
    assert r.status_code == 201
    enquiry_id = r.json()["id"]

    r = client.get("/api/v1/bulk-enquiries", headers=staff_headers)
    assert r.status_code == 200 and r.json()["meta"]["total"] == 1

    r = client.patch(
        f"/api/v1/bulk-enquiries/{enquiry_id}",
        headers=staff_headers,
        json={"status": "quoted", "staff_notes": "Quoted 10% bulk discount"},
    )
    assert r.json()["status"] == "quoted"


def test_bulk_enquiry_public_no_auth_needed(client, clean_db):
    r = client.post(
        "/api/v1/bulk-enquiries",
        json={
            "name": "Anon",
            "email": "anon@example.com",
            "phone": "9000000000",
            "product_interest": "Overcoats",
        },
    )
    assert r.status_code == 201


def test_customer_notification_inbox(client, clean_db, product, customer_headers, customer, address):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "notif-1"},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    )
    r = client.get("/api/v1/notifications/me", headers=customer_headers)
    assert r.status_code == 200
    events = [n["event_type"] for n in r.json()]
    assert "order_placed" in events


def test_whatsapp_link_is_manual_tool(client, clean_db, product, customer_headers, staff_headers, address):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    order = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "wa-1"},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    ).json()["order"]
    r = client.get(f"/api/v1/orders/{order['id']}/whatsapp-link", headers=staff_headers)
    assert r.status_code == 200
    assert r.json()["link"].startswith("https://wa.me/")
