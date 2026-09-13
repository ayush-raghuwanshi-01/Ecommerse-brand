import hashlib
import hmac
import json
from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import utcnow
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.payment import Payment
from app.models.returns import Refund, RefundStatus
from app.tests.conftest import variant_of


def _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-1"):
    m = variant_of(product, "M")
    client.post("/api/v1/carts/me/items", headers=customer_headers, json={"variant_id": m.id, "qty": 1})
    r = client.post("/api/v1/checkout/orders", headers={**customer_headers, "Idempotency-Key": key},
                    json={"shipping_address_id": address.id, "payment_method": "razorpay"})
    assert r.status_code == 201
    return r.json()


def _webhook(client, event_id, event_type, provider_order_id, payment_id="pay_x", sig=None):
    payload = {"id": event_id, "event": event_type,
               "payload": {"payment": {"entity": {"id": payment_id, "order_id": provider_order_id}}}}
    body = json.dumps(payload).encode()
    signature = sig or hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhooks/razorpay", content=body,
                       headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"})


def test_webhook_success_confirms_order(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address)
    rzp_order = body["payment_session"]["provider_order_id"]
    r = _webhook(client, "evt_1", "payment.captured", rzp_order)
    assert r.status_code == 200 and r.json()["status"] == "processed"
    order = clean_db.get(Order, body["order"]["id"])
    assert order.status == OrderStatus.confirmed
    assert order.payment_status == PaymentStatus.paid
    clean_db.expire_all()
    assert variant_of(product, "M").sold_qty == 1
    assert variant_of(product, "M").reserved_qty == 0


def test_webhook_duplicate_idempotent(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-2")
    rzp_order = body["payment_session"]["provider_order_id"]
    r1 = _webhook(client, "evt_dup", "payment.captured", rzp_order)
    r2 = _webhook(client, "evt_dup", "payment.captured", rzp_order)
    assert r1.json()["status"] == "processed"
    assert r2.json()["status"] == "duplicate"
    clean_db.expire_all()
    assert variant_of(product, "M").sold_qty == 1


def test_webhook_invalid_signature_rejected(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-3")
    rzp_order = body["payment_session"]["provider_order_id"]
    r = _webhook(client, "evt_bad", "payment.captured", rzp_order, sig="deadbeef")
    assert r.status_code == 403
    order = clean_db.get(Order, body["order"]["id"])
    assert order.payment_status != PaymentStatus.paid


def test_webhook_payment_failed(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-4")
    rzp_order = body["payment_session"]["provider_order_id"]
    r = _webhook(client, "evt_fail", "payment.failed", rzp_order)
    assert r.status_code == 200
    order = clean_db.get(Order, body["order"]["id"])
    assert order.payment_status == PaymentStatus.failed
    assert order.status == OrderStatus.pending_payment


def test_payment_retry_cooldown(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-5")
    order_id = body["order"]["id"]
    rzp_order = body["payment_session"]["provider_order_id"]
    _webhook(client, "evt_retry_fail", "payment.failed", rzp_order)

    # immediate retry blocked (~2 min cooldown)
    r = client.post("/api/v1/payments/retry", headers=customer_headers, json={"order_id": order_id})
    assert r.status_code == 409

    # age the failed attempt past cooldown
    payment = clean_db.scalars(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    ).first()
    payment.updated_at = utcnow() - timedelta(minutes=3)
    clean_db.commit()

    r = client.post("/api/v1/payments/retry", headers=customer_headers, json={"order_id": order_id})
    assert r.status_code == 200
    assert r.json()["provider_order_id"] != rzp_order


def test_browser_closed_order_recoverable(client, clean_db, product, customer_headers, address):
    """Payment captured via webhook after the customer vanished: order still paid & visible."""
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-6")
    rzp_order = body["payment_session"]["provider_order_id"]
    _webhook(client, "evt_late", "payment.captured", rzp_order)
    r = client.get("/api/v1/orders/me", headers=customer_headers)
    numbers = [o["number"] for o in r.json()["items"]]
    assert body["order"]["number"] in numbers
    order = next(o for o in r.json()["items"] if o["number"] == body["order"]["number"])
    assert order["payment_status"] == "paid"


def test_refund_requires_manager(client, clean_db, product, customer_headers, staff_headers,
                                 manager_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-7")
    order_id = body["order"]["id"]
    rzp_order = body["payment_session"]["provider_order_id"]
    _webhook(client, "evt_ref", "payment.captured", rzp_order)

    # staff cannot approve refunds: create refund via cancellation by manager first
    client.post(f"/api/v1/orders/me/{order_id}/cancel-request", headers=customer_headers,
                json={"reason": "ordered_by_mistake"})
    r = client.post(f"/api/v1/orders/{order_id}/cancel-decision", headers=manager_headers,
                    json={"approve": True})
    assert r.status_code == 200
    clean_db.expire_all()
    refund = clean_db.scalars(select(Refund).where(Refund.order_id == order_id)).first()
    assert refund is not None
    assert refund.status == RefundStatus.requested  # awaits explicit manager approval

    # staff cannot approve refunds
    r = client.post("/api/v1/returns/refunds/decide", headers=staff_headers,
                    json={"refund_id": refund.id, "approve": True})
    assert r.status_code == 403

    r = client.post("/api/v1/returns/refunds/decide", headers=manager_headers,
                    json={"refund_id": refund.id, "approve": True})
    assert r.status_code == 200
    clean_db.expire_all()
    assert clean_db.get(Refund, refund.id).status == RefundStatus.completed
    order = clean_db.get(Order, order_id)
    assert order.payment_status == PaymentStatus.refunded


def test_mock_capture_completes_prepaid_order(client, clean_db, product, customer_headers, address):
    body = _place_prepaid(client, clean_db, product, customer_headers, address, key="pay-mockcap")
    order_id = body["order"]["id"]
    r = client.post(f"/api/v1/payments/mock-capture/{order_id}", headers=customer_headers)
    assert r.status_code == 200, r.text
    order = clean_db.get(Order, order_id)
    assert order.payment_status == PaymentStatus.paid
    assert order.status == OrderStatus.confirmed
    # idempotent: second call is harmless
    r2 = client.post(f"/api/v1/payments/mock-capture/{order_id}", headers=customer_headers)
    assert r2.status_code == 200
