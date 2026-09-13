"""Shared fixtures: SQLite-backed app, users per role, catalogue factories."""

import os
import tempfile
from uuid import uuid4

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec_test"
os.environ["EMAIL_PROVIDER"] = "log"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"  # rate limiting is infra behaviour, not under unit test
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.catalog import (  # noqa: E402
    Product,
    ProductImage,
    ProductStatus,
    ProductVariant,
    VariantSize,
)
from app.models.inventory import Warehouse  # noqa: E402
from app.models.user import Address, User, UserRole  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def clean_db(db):
    """Truncate all tables between tests for isolation."""
    yield db
    db.rollback()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def warehouse(clean_db: Session) -> Warehouse:
    wh = Warehouse(name="Bhopal Fulfilment Centre", city="Bhopal", state="Madhya Pradesh",
                   country="IN", is_default=True)
    clean_db.add(wh)
    clean_db.commit()
    return wh


def _user(clean_db: Session, role: UserRole, email: str | None = None, password="Password@123") -> User:
    user = User(
        email=email or f"{role.value}-{uuid4().hex[:6]}@example.com",
        full_name=f"{role.value.title()} Person",
        phone="9876500000",
        password_hash=hash_password(password),
        role=role,
        is_email_verified=True,
    )
    clean_db.add(user)
    clean_db.commit()
    return user


@pytest.fixture()
def customer(clean_db: Session) -> User:
    return _user(clean_db, UserRole.customer)


@pytest.fixture()
def staff(clean_db: Session) -> User:
    return _user(clean_db, UserRole.staff)


@pytest.fixture()
def manager(clean_db: Session) -> User:
    return _user(clean_db, UserRole.manager)


@pytest.fixture()
def admin(clean_db: Session) -> User:
    return _user(clean_db, UserRole.admin)


def auth_headers(client: TestClient, user: User, password="Password@123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def customer_headers(client, customer) -> dict:
    return auth_headers(client, customer)


@pytest.fixture()
def staff_headers(client, staff) -> dict:
    return auth_headers(client, staff)


@pytest.fixture()
def manager_headers(client, manager) -> dict:
    return auth_headers(client, manager)


@pytest.fixture()
def admin_headers(client, admin) -> dict:
    return auth_headers(client, admin)


@pytest.fixture()
def address(clean_db: Session, customer: User, postal_code="462001") -> Address:
    addr = Address(
        user_id=customer.id, full_name=customer.full_name, phone="9876500000",
        line1="12 Mall Road", city="Bhopal", state="Madhya Pradesh",
        postal_code=postal_code, country="IN", is_default_shipping=True,
    )
    clean_db.add(addr)
    clean_db.commit()
    return addr


def make_product(
    clean_db: Session,
    *,
    name: str | None = None,
    status: ProductStatus = ProductStatus.active,
    stock: dict[str, int] | None = None,
    price: int = 199900,
    gst: float = 5.0,
    preorder: bool = False,
    sale_item: bool = False,
    sizes: list[VariantSize] | None = None,
    warehouse_id: str | None = None,
) -> Product:
    name = name or f"Test Coat {uuid4().hex[:5]}"
    product = Product(
        name=name, slug=f"{name.lower().replace(' ', '-')}",
        short_description="test", description="test product",
        status=status, base_price_paise=price, gst_percentage=gst,
        is_preorder=preorder, is_sale_item=sale_item,
        restock_note="Restock next month" if status == ProductStatus.out_of_stock else None,
        preorder_fulfillment_note="Ships in 4 weeks" if preorder else None,
    )
    clean_db.add(product)
    clean_db.flush()
    clean_db.add(ProductImage(product_id=product.id, url="/static/uploads/test.jpg",
                              alt_text=name, is_primary=True))
    stock = stock or {"M": 5, "L": 0}
    for order, size in enumerate(sizes or list(VariantSize)):
        clean_db.add(ProductVariant(
            product_id=product.id, sku=f"T-{uuid4().hex[:6]}-{size.value}".upper(),
            size=size, price_paise=price + (10000 if size in (VariantSize.XL, VariantSize.XXL) else 0),
            gst_percentage=gst, stock_qty=stock.get(size.value, 0),
            is_purchasable=not preorder, is_preorder=preorder,
            warehouse_id=warehouse_id, sort_order=order,
        ))
    clean_db.commit()
    clean_db.expire_all()
    return product


@pytest.fixture()
def product(clean_db: Session, warehouse: Warehouse) -> Product:
    return make_product(clean_db, warehouse_id=warehouse.id)


def variant_of(product: Product, size: str = "M") -> ProductVariant:
    return next(v for v in product.variants if v.size.value == size)
