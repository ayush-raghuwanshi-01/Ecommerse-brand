import threading

from sqlalchemy import select

from app.models.commerce import Notification, RestockStatus, RestockSubscription
from app.models.inventory import AdjustmentType, InventoryAdjustment
from app.models.order import Order, OrderStatus
from app.models.user import UserRole
from app.tests.conftest import _user, auth_headers, make_product, variant_of


def test_adjustment_ledger_and_negative_prevention(client, clean_db, product, staff_headers, manager):
    m = variant_of(product, "M")
    r = client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_headers,
        json={
            "variant_id": m.id,
            "adjustment_type": "increase",
            "qty_change": 10,
            "reason": "batch received",
        },
    )
    assert r.status_code == 201
    r = client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_headers,
        json={"variant_id": m.id, "adjustment_type": "decrease", "qty_change": -9999},
    )
    assert r.status_code == 422

    ledgers = clean_db.scalars(
        select(InventoryAdjustment).where(InventoryAdjustment.variant_id == m.id)
    ).all()
    assert any(
        entry.adjustment_type == AdjustmentType.increase and entry.qty_change == 10 for entry in ledgers
    )
    # ledger records user + before/after
    inc = next(e for e in ledgers if e.adjustment_type == AdjustmentType.increase)
    assert inc.user_id is not None and inc.qty_after == inc.qty_before + 10


def test_damage_and_defect_movements(client, clean_db, product, staff_headers):
    m = variant_of(product, "M")
    before = m.stock_qty
    r = client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_headers,
        json={"variant_id": m.id, "adjustment_type": "damage", "qty_change": -2, "reason": "water damage"},
    )
    assert r.status_code == 201
    clean_db.expire_all()
    assert variant_of(product, "M").stock_qty == before - 2
    assert variant_of(product, "M").damaged_qty == 2


def test_concurrent_reservation_no_oversell(client, clean_db, warehouse):
    """5 customers race for the last unit: exactly one order may succeed."""
    product = make_product(clean_db, name="Race Coat", stock={"M": 1})
    racers = [_user(clean_db, UserRole.customer, email=f"racer{i}@example.com") for i in range(5)]
    clean_db.commit()
    variant_id = variant_of(product, "M").id

    results = []
    lock = threading.Lock()

    def buy(i):
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as c:
            headers = auth_headers(c, racers[i])
            addr = c.post(
                "/api/v1/addresses",
                headers=headers,
                json={
                    "full_name": racers[i].full_name,
                    "phone": "9876500000",
                    "line1": "1 Race St",
                    "city": "Bhopal",
                    "state": "Madhya Pradesh",
                    "postal_code": "462001",
                },
            )
            addr_id = addr.json()["id"]
            c.post("/api/v1/carts/me/items", headers=headers, json={"variant_id": variant_id, "qty": 1})
            r = c.post(
                "/api/v1/checkout/orders",
                headers={**headers, "Idempotency-Key": f"race-{i}"},
                json={"shipping_address_id": addr_id, "payment_method": "cod"},
            )
            with lock:
                results.append(r.status_code)

    threads = [threading.Thread(target=buy, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(201) == 1, f"expected exactly one success, got {results}"
    assert results.count(409) == 4


def test_reservation_release_on_cancel(client, clean_db, product, customer_headers, manager_headers, address):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 3})
    r = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "rel-1"},
        json={"shipping_address_id": address.id, "payment_method": "cod"},
    )
    order_id = r.json()["order"]["id"]
    clean_db.expire_all()
    assert variant_of(product, "M").reserved_qty == 3

    client.post(
        f"/api/v1/orders/me/{order_id}/cancel-request",
        headers=customer_headers,
        json={"reason": "changed_mind"},
    )
    r = client.post(
        f"/api/v1/orders/{order_id}/cancel-decision", headers=manager_headers, json={"approve": True}
    )
    assert r.status_code == 200
    clean_db.expire_all()
    assert variant_of(product, "M").reserved_qty == 0
    assert variant_of(product, "M").stock_qty == m.stock_qty


def test_restock_alert_fires_once(client, clean_db, warehouse, customer, customer_headers):
    product = make_product(clean_db, name="Alert Coat", stock={"M": 0})
    clean_db.commit()
    m = variant_of(product, "M")
    r = client.post("/api/v1/restock-alerts", headers=customer_headers, json={"variant_id": m.id})
    assert r.status_code == 201

    staff_h = auth_headers(client, _user(clean_db, UserRole.staff, email="alert-staff@example.com"))
    client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_h,
        json={"variant_id": m.id, "adjustment_type": "increase", "qty_change": 4},
    )
    clean_db.expire_all()
    subs = clean_db.scalars(select(RestockSubscription)).all()
    assert subs[0].status == RestockStatus.notified
    notes = clean_db.scalars(
        select(Notification).where(
            Notification.event_type == "restock_alert",
            Notification.channel == "email",
        )
    ).all()
    assert len(notes) == 1

    # second restock event does not re-notify the same (already notified) subscription
    client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_h,
        json={"variant_id": m.id, "adjustment_type": "decrease", "qty_change": -4},
    )
    client.post(
        "/api/v1/inventory/adjustments",
        headers=staff_h,
        json={"variant_id": m.id, "adjustment_type": "increase", "qty_change": 2},
    )
    clean_db.expire_all()
    notes = clean_db.scalars(
        select(Notification).where(
            Notification.event_type == "restock_alert", Notification.channel == "email"
        )
    ).all()
    assert len(notes) == 1


def test_expired_reservation_sweep(client, clean_db, product, customer_headers, address, admin_headers):
    from datetime import timedelta

    from app.core.database import utcnow

    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 2})
    r = client.post(
        "/api/v1/checkout/orders",
        headers={**customer_headers, "Idempotency-Key": "sweep-1"},
        json={"shipping_address_id": address.id, "payment_method": "upi"},
    )
    order_id = r.json()["order"]["id"]
    order = clean_db.get(Order, order_id)
    order.reserved_until = utcnow() - timedelta(minutes=1)
    clean_db.commit()

    r = client.post("/api/v1/admin/maintenance/sweep-expired", headers=admin_headers)
    assert r.status_code == 200
    clean_db.expire_all()
    order = clean_db.get(Order, order_id)
    assert order.status == OrderStatus.cancelled
    assert variant_of(product, "M").reserved_qty == 0
