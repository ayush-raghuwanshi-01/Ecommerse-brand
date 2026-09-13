from app.models.user import UserRole
from app.tests.conftest import _user, auth_headers


def test_register_and_login(client, clean_db):
    r = client.post("/api/v1/auth/register", json={
        "email": "new@example.com", "password": "Strong@12345", "full_name": "New Customer"})
    assert r.status_code == 201
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    r = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "Strong@12345"})
    assert r.status_code == 200
    r = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_register_duplicate_email(client, customer):
    r = client.post("/api/v1/auth/register", json={
        "email": customer.email, "password": "Strong@12345", "full_name": "Dup"})
    assert r.status_code == 409


def test_refresh_rotation_and_reuse_detection(client, customer):
    r = client.post("/api/v1/auth/login", json={"email": customer.email, "password": "Password@123"})
    refresh = r.json()["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != refresh

    # reusing the old (now used) token revokes the whole family
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r.status_code == 401


def test_role_protection(client, customer_headers, staff_headers, manager_headers):
    assert client.get("/api/v1/orders", headers=customer_headers).status_code == 403
    assert client.get("/api/v1/orders", headers=staff_headers).status_code == 200
    assert client.get("/api/v1/inventory/variants", headers=staff_headers).status_code == 200
    assert client.post("/api/v1/products", headers=staff_headers, json={
        "name": "Nope", "base_price_paise": 100}).status_code == 403
    r = client.post("/api/v1/products", headers=manager_headers, json={
        "name": "Manager Made", "base_price_paise": 100})
    assert r.status_code == 201


def test_password_reset_flow(client, clean_db):
    # Created for its side effect: the reset flow must find a matching user.
    _user(clean_db, UserRole.customer, email="reset@example.com")
    r = client.post("/api/v1/auth/password-reset/request", json={"email": "reset@example.com"})
    assert r.status_code == 200
    from sqlalchemy import select

    from app.models.commerce import Notification
    note = clean_db.scalars(select(Notification).where(Notification.recipient == "reset@example.com")).first()
    token = note.payload_json["reset_token"]
    r = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "BrandNew@123"})
    assert r.status_code == 200
    # old password dead, new works
    assert client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "Password@123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "BrandNew@123"}).status_code == 200
    # token single-use
    r = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Another@1234"})
    assert r.status_code == 401


def test_change_password_revokes_sessions(client, clean_db):
    user = _user(clean_db, UserRole.customer, email="chg@example.com")
    refresh = _login_refresh(client, user)
    headers = auth_headers(client, user)
    r = client.post("/api/v1/auth/change-password", headers=headers,
                    json={"current_password": "Password@123", "new_password": "Changed@1234"})
    assert r.status_code == 200
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def _login_refresh(client, user):
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Password@123"})
    return r.json()["refresh_token"]
