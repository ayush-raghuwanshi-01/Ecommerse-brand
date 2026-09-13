from datetime import timedelta

from sqlalchemy import select

from app.core.database import utcnow
from app.models.order import Order, OrderStatus
from app.models.returns import ReturnRequest, ReturnStatus
from app.tests.conftest import make_product, variant_of


def _delivered_order(client, clean_db, product, customer_headers, address, key="ret-1", sale=False):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    r = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": key},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    )
    order_id = r.json()["order"]["id"]
    order = clean_db.get(Order, order_id)
    order.status = OrderStatus.delivered
    order.delivered_at = utcnow() - timedelta(days=1)
    clean_db.commit()
    return order


def test_return_window_enforced(client, clean_db, product, customer_headers, address):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    r = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "ret-old"},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    )
    order = clean_db.get(Order, r.json()["order"]["id"])
    order.status = OrderStatus.delivered
    order.delivered_at = utcnow() - timedelta(days=10)
    clean_db.commit()
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={"order_id": order.id, "return_type": "refund", "reason": "size_issue"},
    )
    assert r.status_code == 422
    assert "return window" in r.json()["error"]["message"].lower()


def test_undelivered_order_cannot_return(client, clean_db, product, customer_headers, address):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    r = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "ret-undel"},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    )
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={"order_id": r.json()["order"]["id"], "return_type": "refund", "reason": "size_issue"},
    )
    assert r.status_code == 422


def test_sale_item_refund_restricted_but_exchange_allowed(
    client, clean_db, warehouse, customer_headers, address
):
    sale = make_product(clean_db, name="Sale Coat", sale_item=True)
    clean_db.commit()
    order = _delivered_order(client, clean_db, sale, customer_headers, address, key="ret-sale")
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={"order_id": order.id, "return_type": "refund", "reason": "changed_mind"},
    )
    assert r.status_code == 422
    assert "exchange" in r.json()["error"]["message"].lower()

    xs = variant_of(sale, "XS")
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "order_id": order.id,
            "return_type": "size_exchange",
            "reason": "size_issue",
            "exchange_variant_id": xs.id,
        },
    )
    assert r.status_code == 201


def test_damaged_item_company_pays_and_replacement(
    client, clean_db, product, customer_headers, staff_headers, manager_headers, address
):
    order = _delivered_order(client, clean_db, product, customer_headers, address, key="ret-dmg")
    m = variant_of(product, "M")
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "order_id": order.id,
            "order_item_id": order.items[0].id,
            "return_type": "replacement",
            "reason": "damaged_product",
        },
    )
    assert r.status_code == 201
    ret = r.json()
    assert ret["company_pays_shipping"] is True
    return_id = ret["id"]

    for status in ("under_review",):
        r = client.post(f"/api/v1/returns/{return_id}/status", headers=staff_headers, json={"status": status})
        assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/returns/{return_id}/status", headers=manager_headers, json={"status": "approved"}
    )
    assert r.status_code == 200
    for status in ("pickup_scheduled", "picked_up", "received", "inspected"):
        r = client.post(
            f"/api/v1/returns/{return_id}/status",
            headers=staff_headers,
            json={"status": status, "accept_items": False},
        )
        assert r.status_code == 200, r.text
    clean_db.expire_all()
    ret_row = clean_db.get(ReturnRequest, return_id)
    assert ret_row.status == ReturnStatus.approved_for_exchange
    # damaged units never re-enter sellable stock
    assert variant_of(product, "M").stock_qty == m.stock_qty


def test_refund_flow_after_pickup_and_inspection(
    client, clean_db, product, customer_headers, staff_headers, manager_headers, address
):
    order = _delivered_order(client, clean_db, product, customer_headers, address, key="ret-ref")
    r = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={"order_id": order.id, "return_type": "refund", "reason": "size_issue"},
    )
    return_id = r.json()["id"]

    client.post(f"/api/v1/returns/{return_id}/status", headers=staff_headers, json={"status": "under_review"})
    client.post(f"/api/v1/returns/{return_id}/status", headers=manager_headers, json={"status": "approved"})
    client.post(
        f"/api/v1/returns/{return_id}/status", headers=staff_headers, json={"status": "pickup_scheduled"}
    )
    r = client.post(
        f"/api/v1/returns/{return_id}/status", headers=staff_headers, json={"status": "picked_up"}
    )
    assert r.status_code == 200
    # refund eligibility begins at pickup
    from app.models.returns import Refund

    clean_db.expire_all()
    refund = clean_db.scalars(select(Refund).where(Refund.return_request_id == return_id)).first()
    assert refund is not None and refund.status.value in ("requested", "approved", "processing", "completed")

    client.post(f"/api/v1/returns/{return_id}/status", headers=staff_headers, json={"status": "received"})
    clean_db.expire_all()
    pre_inspect_stock = variant_of(product, "M").stock_qty
    r = client.post(
        f"/api/v1/returns/{return_id}/status",
        headers=staff_headers,
        json={"status": "inspected", "accept_items": True},
    )
    assert r.status_code == 200
    clean_db.expire_all()
    # accepted return re-enters sellable stock
    assert variant_of(product, "M").stock_qty == pre_inspect_stock + 1
    ret_row = clean_db.get(ReturnRequest, return_id)
    assert ret_row.status == ReturnStatus.approved_for_refund
