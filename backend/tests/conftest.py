"""Shared pytest fixtures.

Isolation strategy:
* Tests run ONLY against TEST_DATABASE_URL (a separate database whose name contains "test").
* The schema is built with Alembic (`upgrade head`), never `metadata.create_all`, so the
  migration itself — including triggers and partial indexes — is under test.
* Every test runs inside an outer transaction that is rolled back afterwards; nothing is
  ever committed, so no records persist.
"""
import secrets
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limiter
from app.core.security import get_password_hash
from app.main import app
from app.models import Admin, Category, Customer, Order, Product
from app.services.email_service import dev_email_provider
from app.services.sms_service import dev_sms_provider

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_database_url() -> str:
    url = settings.TEST_DATABASE_URL
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured in backend/.env", allow_module_level=True)
    db_name = make_url(url).database or ""
    if "test" not in db_name.lower() or url == settings.DATABASE_URL:
        pytest.exit("Refusing to run: TEST_DATABASE_URL must point to a separate *test* database.")
    return url


@pytest.fixture(scope="session")
def engine():
    url = _test_database_url()
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    alembic_cfg.attributes["database_url"] = url
    command.upgrade(alembic_cfg, "head")

    eng = create_engine(url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _isolated_private_asset_storage(monkeypatch, tmp_path_factory):
    """Isolate private digital asset storage per test inside a temporary directory."""
    asset_dir = tmp_path_factory.mktemp("digiverse_test_private_assets")
    monkeypatch.setattr(settings, "ASSET_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "ASSET_STORAGE_LOCAL_ROOT", str(asset_dir))
    return asset_dir


@pytest.fixture()
def db(engine):
    """Session bound to an outer transaction that is always rolled back."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture()
def api_client(db):
    """FastAPI TestClient wired to the isolated, rolled-back test database session."""
    rate_limiter.reset()
    dev_sms_provider.clear()
    dev_email_provider.clear()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limiter.reset()
        dev_sms_provider.clear()
        dev_email_provider.clear()


# ---- helpers (objects exist only inside the rolled-back test transaction) ----

def _hash() -> str:
    return get_password_hash(secrets.token_urlsafe(16))


@pytest.fixture()
def make_customer(db):
    def _make(**overrides) -> Customer:
        data = dict(
            full_name="Test Customer",
            email=f"customer-{uuid.uuid4().hex[:10]}@example.test",
            password_hash=_hash(),
        )
        data.update(overrides)
        customer = Customer(**data)
        db.add(customer)
        db.flush()
        return customer

    return _make


@pytest.fixture()
def make_admin(db):
    def _make(**overrides) -> Admin:
        suffix = uuid.uuid4().hex[:10]
        data = dict(username=f"admin_{suffix}", email=f"admin-{suffix}@example.test", password_hash=_hash())
        data.update(overrides)
        admin = Admin(**data)
        db.add(admin)
        db.flush()
        return admin

    return _make


@pytest.fixture()
def make_category(db):
    def _make(**overrides) -> Category:
        suffix = uuid.uuid4().hex[:10]
        data = dict(name=f"Test Category {suffix}", slug=f"test-category-{suffix}")
        data.update(overrides)
        category = Category(**data)
        db.add(category)
        db.flush()
        return category

    return _make


@pytest.fixture()
def make_product(db, make_category):
    def _make(category: Category | None = None, **overrides) -> Product:
        category = category or make_category()
        suffix = uuid.uuid4().hex[:10]
        data = dict(
            name=f"Test Product {suffix}",
            slug=f"test-product-{suffix}",
            category_id=category.id,
            original_price=Decimal("499.00"),
        )
        data.update(overrides)
        product = Product(**data)
        db.add(product)
        db.flush()
        return product

    return _make


@pytest.fixture()
def make_order(db):
    def _make(customer: Customer, **overrides) -> Order:
        data = dict(
            customer_id=customer.id,
            order_number=f"TEST-{uuid.uuid4().hex[:12].upper()}",
            total_amount=Decimal("499.00"),
        )
        data.update(overrides)
        order = Order(**data)
        db.add(order)
        db.flush()
        return order

    return _make
