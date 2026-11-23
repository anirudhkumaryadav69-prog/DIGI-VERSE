"""Comprehensive test suite for demo catalog seeding against isolated digiverse_test DB."""
from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.catalog import Category, Product, ProductImage
from app.models.customer import Customer
from app.models.enums import ProductApprovalStatus, SellerApplicationStatus
from app.models.order import Order, Payment
from app.models.seller import SellerProfile
from app.services.catalog_service import _FORBIDDEN_PUBLIC_META_FRAGMENTS
from app.services.payment_gateway import MockPaymentProvider
from scripts.seed_demo_catalog import (
    DEMO_CATEGORIES,
    DEMO_DISCLAIMER,
    DEMO_PRODUCTS,
    DEMO_SELLERS,
    build_demo_asset_bytes,
    build_product_png,
    seed_demo_catalog,
    verify_seed_target,
)


@pytest.fixture(autouse=True)
def _isolated_demo_image_storage(monkeypatch, tmp_path_factory):
    """Isolate uploaded demo PNG images in a temporary directory per test."""
    img_dir = tmp_path_factory.mktemp("digiverse_test_demo_images")
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(img_dir))
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    return img_dir


def _csrf(client) -> dict[str, str]:
    tok = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: tok} if tok else {}


def _register_and_login_buyer(client) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": "Demo Test Buyer",
            "email": f"buyer-{suffix}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "BuyerPassword#2026!",
        },
    )
    assert r.status_code == 201
    return _csrf(client)


def test_seed_safety_rejects_production_and_unsafe_targets(db, monkeypatch):
    # Test mode only permits digiverse_test/digiverse_local when explicitly authorized
    assert verify_seed_target(db, allow_test_db=True) == "digiverse_test"

    # CLI mode (allow_test_db=False) must reject test DB / test environment
    with pytest.raises(RuntimeError):
        verify_seed_target(db, allow_test_db=False)

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="not permitted"):
        verify_seed_target(db, allow_test_db=True)

    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    with pytest.raises(RuntimeError, match="not permitted"):
        verify_seed_target(db, allow_test_db=True)

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Simulate remote host rejection
    fake_bind = type("FakeBind", (), {"url": "postgresql+psycopg://u:p@db.remote.example:5432/digiverse_local"})()
    with patch.object(db, "get_bind", return_value=fake_bind):
        with pytest.raises(RuntimeError, match="localhost"):
            verify_seed_target(db, allow_test_db=False)

    # Simulate forbidden database name 'digiverse'
    with patch.object(db, "scalar", return_value="digiverse"):
        with pytest.raises(RuntimeError, match="protected and forbidden"):
            verify_seed_target(db, allow_test_db=False)

    # Unknown DB name rejected
    with patch.object(db, "scalar", return_value="some_other_db"):
        with pytest.raises(RuntimeError, match="not in allowed targets"):
            verify_seed_target(db, allow_test_db=False)


def test_demo_catalog_seed_counts_idempotency_and_customer_preservation(
    db, make_customer, _isolated_demo_image_storage
):
    existing_customer = make_customer(
        full_name="Existing Dev User",
        email=f"existing-{uuid.uuid4().hex[:6]}@example.test",
    )
    existing_id = existing_customer.id
    existing_email = existing_customer.email

    stats1 = seed_demo_catalog(db, allow_test_db=True)
    assert stats1.sellers_created == 4
    assert stats1.categories_created == 8
    assert stats1.products_created == 32
    assert stats1.assets_uploaded == 32
    assert stats1.images_uploaded == 96
    assert len(stats1.image_hashes) == 96

    # Re-run must be strictly idempotent without duplicating records or images
    stats2 = seed_demo_catalog(db, allow_test_db=True)
    assert stats2.sellers_created == 0
    assert stats2.sellers_existing == 4
    assert stats2.categories_created == 0
    assert stats2.categories_existing == 8
    assert stats2.products_created == 0
    assert stats2.assets_uploaded == 0
    assert stats2.assets_skipped == 32
    assert stats2.images_uploaded == 0
    assert stats2.images_skipped == 96

    # Verify exact DB totals & preservation of existing customer
    assert db.scalar(select(func.count(SellerProfile.id))) == 4
    assert db.scalar(select(func.count(Category.id))) == 8
    assert db.scalar(select(func.count(Product.id))) == 32
    assert db.scalar(select(func.count(ProductImage.id))) == 96
    assert db.scalar(select(func.count(Order.id))) == 0
    assert db.scalar(select(func.count(Payment.id))) == 0
    assert db.scalar(select(func.count(AuditLog.id))) == 0

    preserved = db.get(Customer, existing_id)
    assert preserved is not None
    assert preserved.email == existing_email
    assert preserved.full_name == "Existing Dev User"


def test_sellers_categories_ownership_and_image_sync(db, _isolated_demo_image_storage):
    seed_demo_catalog(db, allow_test_db=True)

    sellers = db.scalars(select(SellerProfile)).all()
    assert {s.store_slug for s in sellers} == {spec.store_slug for spec in DEMO_SELLERS}
    for s in sellers:
        assert s.application_status == SellerApplicationStatus.APPROVED
        assert s.approved_by_admin_id is None
        assert s.contact_email.endswith("@demo.digiverse.local")
        assert DEMO_DISCLAIMER in (s.store_description or "")
        assert s.customer.is_phone_verified is True

    # Ownership: 24 seller products (6 each) + 8 official platform products
    seller_owned = db.scalar(select(func.count(Product.id)).where(Product.seller_id.is_not(None)))
    official_owned = db.scalar(select(func.count(Product.id)).where(Product.seller_id.is_(None)))
    assert seller_owned == 24
    assert official_owned == 8

    for s in sellers:
        cnt = db.scalar(select(func.count(Product.id)).where(Product.seller_id == s.id))
        assert cnt == 6

    # Verify 8 unique categories with 4 products each & valid gallery/primary image sync
    categories = db.scalars(select(Category)).all()
    assert len(categories) == 8
    assert len({c.slug for c in categories}) == 8
    for c in categories:
        cnt = db.scalar(select(func.count(Product.id)).where(Product.category_id == c.id))
        assert cnt == 4

    products = db.scalars(select(Product)).all()
    assert len({p.slug for p in products}) == 32
    stored_hashes = set()
    for p in products:
        assert p.approval_status == ProductApprovalStatus.PUBLISHED
        assert p.is_active is True
        assert p.asset_storage_key
        assert p.private_download_url == "asset://managed"
        assert len(p.images) == 3
        primaries = [img for img in p.images if img.is_primary]
        assert len(primaries) == 1
        assert p.image_url == primaries[0].image_url
        filename = p.image_url.rsplit("/", 1)[-1]
        img_file = _isolated_demo_image_storage / filename
        assert img_file.is_file()
        raw = img_file.read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        stored_hashes.add(hashlib.sha256(raw).hexdigest())

    # Confirm all 96 generated PNG files on disk are distinct
    png_files = list(_isolated_demo_image_storage.glob("*.png"))
    assert len(png_files) == 96
    assert len({hashlib.sha256(f.read_bytes()).hexdigest() for f in png_files}) == 96


def test_generated_assets_and_images_are_valid_binaries():
    category_map = {c.slug: c for c in DEMO_CATEGORIES}
    seen_png_hashes = set()

    for idx, p_spec in enumerate(DEMO_PRODUCTS):
        filename, payload, mime = build_demo_asset_bytes(p_spec, idx)
        assert len(payload) > 32
        if filename.endswith(".pdf"):
            assert payload.startswith(b"%PDF-1.4")
            assert b"DEMO SAMPLE - FOR PREVIEW AND TESTING ONLY" in payload
        elif filename.endswith(".zip"):
            assert payload.startswith(b"PK\x03\x04")
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                assert "README.md" in zf.namelist()
                assert DEMO_DISCLAIMER.encode("utf-8") in zf.read("README.md")
        elif filename.endswith(".wav"):
            assert payload[:4] == b"RIFF" and payload[8:12] == b"WAVE"
        elif filename.endswith((".csv", ".json", ".md")):
            text_body = payload.decode("utf-8")
            assert DEMO_DISCLAIMER in text_body

        for slide in range(3):
            png_bytes = build_product_png(p_spec, category_map[p_spec.category_slug], idx, slide)
            assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            seen_png_hashes.add(hashlib.sha256(png_bytes).hexdigest())

    assert len(seen_png_hashes) == 96


def test_public_catalog_filters_metadata_cart_wishlist_and_download_flow(
    api_client, db, _isolated_demo_image_storage
):
    seed_demo_catalog(db, allow_test_db=True)

    # Categories endpoint returns 8 categories with 4 products each
    cats_resp = api_client.get("/api/categories?page_size=50")
    assert cats_resp.status_code == 200
    cats_data = cats_resp.json()
    assert cats_data["total"] == 8
    assert all(item["product_count"] == 4 for item in cats_data["items"])

    # Products endpoint returns all 32 visible products and exposes zero private fields
    prods_resp = api_client.get("/api/products?page_size=60")
    assert prods_resp.status_code == 200
    prods_data = prods_resp.json()
    assert prods_data["total"] == 32
    for item in prods_data["items"]:
        assert "private_download_url" not in item
        assert "asset_storage_key" not in item
        meta = item.get("metadata") or {}
        for k in meta:
            assert not any(bad in k.lower() for bad in _FORBIDDEN_PUBLIC_META_FRAGMENTS)

    # Category filter
    cat_filter = api_client.get("/api/products?category=design-and-graphics&page_size=20")
    assert cat_filter.status_code == 200
    assert cat_filter.json()["total"] == 4

    # Seller filter & official filter
    seller_filter = api_client.get("/api/products?seller=demo-codeforge-labs&page_size=20")
    assert seller_filter.status_code == 200
    assert seller_filter.json()["total"] == 6

    official_filter = api_client.get("/api/products?owner_type=platform&page_size=20")
    assert official_filter.status_code == 200
    assert official_filter.json()["total"] == 8

    # Search functionality
    search_resp = api_client.get("/api/products?search=Python")
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 2

    # Active deals filter
    deals_resp = api_client.get("/api/products?on_sale=true&page_size=20")
    assert deals_resp.status_code == 200
    deals = deals_resp.json()["items"]
    assert len(deals) == 8
    assert all(Decimal(d["effective_price"]) < Decimal(d["original_price"]) for d in deals)

    # Image route serves PNG successfully
    sample_product = prods_data["items"][0]
    img_resp = api_client.get(sample_product["image_url"])
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/png"

    # Cart + Wishlist + Authorized Purchase + Signed Binary Download Stream
    headers = _register_and_login_buyer(api_client)
    prod_id = sample_product["id"]

    wish_resp = api_client.post(f"/api/wishlist/{prod_id}", headers=headers)
    assert wish_resp.status_code == 201
    assert len(wish_resp.json()["items"]) == 1

    cart_resp = api_client.post("/api/cart/items", json={"product_id": prod_id, "quantity": 1}, headers=headers)
    assert cart_resp.status_code in (200, 201)
    assert len(cart_resp.json()["items"]) == 1

    checkout = api_client.post(
        "/api/checkout",
        json={"idempotency_key": f"demo-dl-{uuid.uuid4().hex}"},
        headers=headers,
    )
    assert checkout.status_code == 201
    order_data = checkout.json()
    order_id = order_data["order_id"]
    gateway_order_id = order_data["payment"]["gateway_order_id"]
    gateway_payment_id = f"pay_mock_{uuid.uuid4().hex[:10]}"

    verify = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gateway_order_id,
            "gateway_payment_id": gateway_payment_id,
            "gateway_signature": MockPaymentProvider.sign_payment(gateway_order_id, gateway_payment_id),
            "payment_method": "upi",
        },
        headers=headers,
    )
    assert verify.status_code == 200
    item_id = verify.json()["items"][0]["id"]

    # Unauthenticated grant request must be rejected (401)
    saved_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    unauth_grant = api_client.post(f"/api/downloads/{item_id}")
    assert unauth_grant.status_code in (401, 403)
    for cname, cval in saved_cookies.items():
        api_client.cookies.set(cname, cval)

    grant = api_client.post(f"/api/downloads/{item_id}", headers=headers)
    assert grant.status_code == 201
    dl_url = grant.json()["download_url"]

    stream = api_client.get(dl_url)
    assert stream.status_code == 200
    assert len(stream.content) > 0
    db_prod = db.get(Product, uuid.UUID(prod_id))
    assert hashlib.sha256(stream.content).hexdigest() == db_prod.asset_sha256
