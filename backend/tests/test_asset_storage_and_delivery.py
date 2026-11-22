"""Phase 8.1 Comprehensive Tests: Private Asset Storage & Binary Digital Product Delivery."""
import hashlib
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from jose import jwt as jose_jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.enums import DownloadStatus
from app.models.order import DownloadRecord
from app.services.admin_auth_service import provision_initial_admin
from app.services.asset_storage_service import (
    AssetNotFoundError,
    AssetStorageError,
    LocalPrivateAssetStorageProvider,
    S3PrivateAssetStorageProvider,
    get_asset_storage,
)
from app.services.payment_gateway import MockPaymentProvider


@pytest.fixture(autouse=True)
def _mock_payments_for_phase8(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MAX_DOWNLOADS_PER_ORDER_ITEM", 3)


def _csrf(client) -> dict[str, str]:
    tok = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: tok} if tok else {}


def _login_admin(client, db) -> dict[str, str]:
    init_pw = "AdminInitial#2026!"
    new_pw = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=init_pw)
    r = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": init_pw})
    if r.status_code == 401:
        r = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": new_pw})
    assert r.status_code == 200
    if r.json()["must_change_password"]:
        r2 = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": init_pw, "new_password": new_pw},
            headers=_csrf(client),
        )
        assert r2.status_code == 200
    return _csrf(client)


def _register_customer(client, name: str = "Asset Buyer") -> tuple[dict[str, str], dict]:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"buyer-{suffix}@example.test",
            "phone_number": f"+9197{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert r.status_code == 201
    return _csrf(client), r.json()["customer"]


def _make_zip_bytes(filename: str = "kit.txt", content: bytes = b"Real binary content 123") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _make_pdf_bytes(title: str = "DIGI-VERSE Guide") -> bytes:
    return (
        f"%PDF-1.4\n1 0 obj << /Type /Catalog /Title ({title}) >> endobj\n%%EOF\n"
    ).encode("ascii")


def _buy_product(client, headers: dict[str, str], product_id: uuid.UUID) -> tuple[str, str]:
    r_cart = client.post(
        "/api/cart/items",
        json={"product_id": str(product_id), "quantity": 1},
        headers=headers,
    )
    assert r_cart.status_code in (200, 201)
    chk = client.post("/api/checkout", headers=headers)
    assert chk.status_code == 201
    order_id = chk.json()["order_id"]
    gw_order_id = chk.json()["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_p8_{uuid.uuid4().hex[:10]}"
    sig = MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id)
    r_ver = client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": sig,
        },
        headers=headers,
    )
    assert r_ver.status_code == 200
    return order_id, r_ver.json()["items"][0]["id"]


def test_admin_asset_upload_validation_magic_bytes_and_security(
    api_client, db, make_category, make_product, monkeypatch
):
    admin_headers = _login_admin(api_client, db)
    cat = make_category(name="UI Kits", slug="ui-kits-p8", is_active=True)
    prod = make_product(category=cat, name="Nordic UI Bundle", slug="nordic-ui-bundle", is_active=True)

    # 1. Unauthorized upload rejected (401 when unauthenticated, 403 for customer)
    api_client.cookies.clear()
    zip_data = _make_zip_bytes("readme.txt", b"Hello Nordic")
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("kit.zip", io.BytesIO(zip_data), "application/zip")},
        ).status_code
        == 401
    )

    cust_headers, _ = _register_customer(api_client, "Not An Admin")
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("kit.zip", io.BytesIO(zip_data), "application/zip")},
            headers=cust_headers,
        ).status_code
        == 403
    )

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)

    # 2. Empty file rejected (400)
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("empty.zip", io.BytesIO(b""), "application/zip")},
            headers=admin_headers,
        ).status_code
        == 400
    )

    # 3. Oversized file rejected (413)
    monkeypatch.setattr(settings, "MAX_ASSET_UPLOAD_BYTES", 64)
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("big.zip", io.BytesIO(zip_data), "application/zip")},
            headers=admin_headers,
        ).status_code
        == 413
    )
    monkeypatch.setattr(settings, "MAX_ASSET_UPLOAD_BYTES", 10 * 1024 * 1024)

    # 4. Forbidden/unsupported extensions rejected (400)
    for bad_name, bad_bytes, bad_mime in [
        ("payload.exe", b"MZ\x90\x00executable", "application/x-msdownload"),
        ("shell.sh", b"#!/bin/sh\nrm -rf /", "application/x-sh"),
        ("xss.html", b"<!doctype html><script>alert(1)</script>", "text/html"),
        ("vector.svg", b"<svg onload=alert(1)></svg>", "image/svg+xml"),
    ]:
        r_ext = api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": (bad_name, io.BytesIO(bad_bytes), bad_mime)},
            headers=admin_headers,
        )
        assert r_ext.status_code == 400

    # 5. Executable / HTML magic bytes spoofed with allowed extensions rejected (400)
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("trojan.zip", io.BytesIO(b"MZ\x90\x00fakepayload"), "application/zip")},
            headers=admin_headers,
        ).status_code
        == 400
    )
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("spoof.pdf", io.BytesIO(zip_data), "application/pdf")},
            headers=admin_headers,
        ).status_code
        == 400
    )
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("badhtml.txt", io.BytesIO(b"<script>alert(1)</script>"), "text/plain")},
            headers=admin_headers,
        ).status_code
        == 400
    )

    # 6. MIME mismatch rejected (ZIP bytes claiming image/png) -> 400
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("mismatch.zip", io.BytesIO(zip_data), "image/png")},
            headers=admin_headers,
        ).status_code
        == 400
    )

    # 7. Path traversal filenames rejected -> 400
    for traversal_name in ("../../evil.zip", "..\\evil.zip", "%2e%2e/evil.zip"):
        assert (
            api_client.post(
                f"/api/admin/products/{prod.id}/asset",
                files={"file": (traversal_name, io.BytesIO(zip_data), "application/zip")},
                headers=admin_headers,
            ).status_code
            == 400
        )

    # 8. Valid authorized upload succeeds -> stores privately, sanitizes metadata, zero storage path leaks
    r_ok = api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("Nordic UI Kit (v2)!.zip", io.BytesIO(zip_data), "application/zip")},
        headers=admin_headers,
    )
    assert r_ok.status_code == 201
    admin_prod = r_ok.json()
    assert admin_prod["asset"]["has_asset"] is True
    assert admin_prod["asset"]["filename"].endswith(".zip")
    assert admin_prod["asset"]["content_type"] == "application/zip"
    assert admin_prod["asset"]["size_bytes"] == len(zip_data)
    assert admin_prod["asset"]["sha256"] == hashlib.sha256(zip_data).hexdigest()
    assert admin_prod["asset"]["storage_backend"] == "local"
    assert "storage_key" not in json.dumps(admin_prod)

    db.refresh(prod)
    storage_key = prod.asset_storage_key
    assert storage_key is not None
    assert "Nordic UI" not in storage_key  # Opaque random server key, never user filename
    private_root = Path(settings.ASSET_STORAGE_LOCAL_ROOT).resolve()
    assert (private_root / storage_key).is_file()
    assert "frontend" not in str(private_root).lower()

    # Public product endpoint NEVER exposes private asset fields or storage key
    r_pub = api_client.get(f"/api/products/{prod.slug}")
    assert r_pub.status_code == 200
    pub_raw = r_pub.text
    assert "private_download_url" not in pub_raw
    assert storage_key not in pub_raw
    assert str(private_root) not in pub_raw

    # Audit log never records storage_key
    logs = db.scalars(select(AuditLog).where(AuditLog.entity_id == str(prod.id))).all()
    assert any(l.action == "product.asset_uploaded" for l in logs)
    for l in logs:
        assert storage_key not in json.dumps(l.details or {})


def test_end_to_end_binary_download_byte_exact_and_security_controls(
    api_client, db, make_category, make_product
):
    admin_headers = _login_admin(api_client, db)
    cat = make_category(name="eBooks & Code", slug="ebooks-code-p8", is_active=True)
    prod = make_product(
        category=cat,
        name="Multi-Chunk Digital Archive",
        slug="multi-chunk-archive",
        original_price=Decimal("799.00"),
        is_active=True,
    )

    # Generate incompressible pseudo-random bytes larger than 64 KB chunk size (~210 KB)
    payload_bytes = os.urandom(210_000)
    archive_bytes = _make_zip_bytes("bundle/model.bin", payload_bytes)
    r_up = api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("Multi Chunk Pack!.zip", io.BytesIO(archive_bytes), "application/zip")},
        headers=admin_headers,
    )
    assert r_up.status_code == 201

    # Customer A purchases, Customer B is a bystander
    api_client.cookies.clear()
    headers_a, cust_a = _register_customer(api_client, "Buyer Binary")
    order_id, order_item_id = _buy_product(api_client, headers_a, prod.id)

    # Overview exposes safe filename & byte size, never storage_key
    r_overview = api_client.get("/api/downloads")
    assert r_overview.status_code == 200
    item_info = r_overview.json()["eligible_items"][0]
    assert item_info["asset_filename"].endswith(".zip")
    assert item_info["asset_size_bytes"] == len(archive_bytes)
    assert "storage_key" not in r_overview.text

    # Request single-use grant and stream actual binary file
    r_grant = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
    assert r_grant.status_code == 201
    grant = r_grant.json()

    r_stream = api_client.get(grant["download_url"])
    assert r_stream.status_code == 200
    assert r_stream.content == archive_bytes
    assert r_stream.headers.get("content-type", "").startswith("application/zip")
    assert r_stream.headers.get("x-content-type-options") == "nosniff"
    assert "no-store" in (r_stream.headers.get("cache-control") or "")
    assert r_stream.headers.get("content-length") == str(len(archive_bytes))
    assert "attachment; filename=" in (r_stream.headers.get("content-disposition") or "")

    # Reused single-use token is rejected -> 403
    assert api_client.get(grant["download_url"]).status_code == 403

    # Request a second grant to test oiid mismatch and revocation
    r_grant2 = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
    assert r_grant2.status_code == 201
    grant2 = r_grant2.json()

    wrong_oiid_token = jose_jwt.encode(
        {
            "iss": "digiverse",
            "aud": "digiverse:download",
            "sub": cust_a["id"],
            "did": grant2["download_id"],
            "oiid": str(uuid.uuid4()),
            "type": "signed_download",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=2),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert (
        api_client.get(f"/api/downloads/{grant2['download_id']}/file?token={wrong_oiid_token}").status_code
        == 403
    )

    # Customer B cannot access Customer A's download stream -> 403/404
    cust_a_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    _register_customer(api_client, "Unauthorized B")
    assert api_client.get(grant2["download_url"]).status_code in (403, 404)

    # Unauthenticated request rejected -> 401
    api_client.cookies.clear()
    assert api_client.get(grant2["download_url"]).status_code == 401

    # Admin revokes via order refund -> Customer A's active token rejected -> 403
    admin_headers = _login_admin(api_client, db)
    r_ref = api_client.patch(
        f"/api/admin/orders/{order_id}/status",
        json={"status": "refunded"},
        headers=admin_headers,
    )
    assert r_ref.status_code == 200

    api_client.cookies.clear()
    for k, v in cust_a_cookies.items():
        api_client.cookies.set(k, v)
    r_revoked = api_client.get(grant2["download_url"])
    assert r_revoked.status_code == 403


def test_asset_replacement_preserves_paid_access_and_blocks_paid_deletion(
    api_client, db, make_category, make_product
):
    admin_headers = _login_admin(api_client, db)
    cat = make_category(name="Replacement", slug="replacement-p8", is_active=True)
    prod = make_product(category=cat, name="Evolving Kit", slug="evolving-kit", is_active=True)

    pdf_v1 = _make_pdf_bytes("Version 1 Manual")
    r_up1 = api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("manual-v1.pdf", io.BytesIO(pdf_v1), "application/pdf")},
        headers=admin_headers,
    )
    assert r_up1.status_code == 201
    db.refresh(prod)
    key_v1 = prod.asset_storage_key

    # Customer purchases and receives an active download grant BEFORE admin replaces asset
    api_client.cookies.clear()
    cust_headers, _ = _register_customer(api_client, "Early Purchaser")
    _, order_item_id = _buy_product(api_client, cust_headers, prod.id)
    grant_before_replace = api_client.post(
        f"/api/downloads/{order_item_id}", headers=cust_headers
    ).json()
    cust_cookies = dict(api_client.cookies)

    # Admin tries invalid replacement (disguised exe) -> rejected 400, v1 preserved
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("manual-v2.pdf", io.BytesIO(b"MZbadfile"), "application/pdf")},
            headers=admin_headers,
        ).status_code
        == 400
    )
    assert get_asset_storage("local").exists(key_v1)

    # Admin deletes asset on paid product -> blocked 409 Conflict
    assert api_client.delete(f"/api/admin/products/{prod.id}/asset", headers=admin_headers).status_code == 409

    # Admin replaces with valid v2 PDF -> v1 removed, v2 stored
    pdf_v2 = _make_pdf_bytes("Version 2 Revised Manual")
    r_up2 = api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("manual-v2.pdf", io.BytesIO(pdf_v2), "application/pdf")},
        headers=admin_headers,
    )
    assert r_up2.status_code == 201
    db.refresh(prod)
    key_v2 = prod.asset_storage_key
    assert key_v2 != key_v1
    assert not get_asset_storage("local").exists(key_v1)
    assert get_asset_storage("local").exists(key_v2)

    # Paid customer's pending grant STILL succeeds and delivers v2 binary PDF cleanly!
    api_client.cookies.clear()
    for k, v in cust_cookies.items():
        api_client.cookies.set(k, v)
    r_dl = api_client.get(grant_before_replace["download_url"])
    assert r_dl.status_code == 200
    assert r_dl.content == pdf_v2
    assert r_dl.headers.get("content-type", "").startswith("application/pdf")

    # Deleting asset on an UNPURCHASED product is permitted and deletes file from disk
    prod_unpaid = make_product(category=cat, name="Unpaid Asset", slug="unpaid-asset-p8", is_active=True)
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    api_client.post(
        f"/api/admin/products/{prod_unpaid.id}/asset",
        files={"file": ("draft.pdf", io.BytesIO(pdf_v1), "application/pdf")},
        headers=admin_headers,
    )
    db.refresh(prod_unpaid)
    unpaid_key = prod_unpaid.asset_storage_key
    r_del = api_client.delete(f"/api/admin/products/{prod_unpaid.id}/asset", headers=admin_headers)
    assert r_del.status_code == 200
    assert r_del.json()["asset"]["has_asset"] is False
    assert not get_asset_storage("local").exists(unpaid_key)


def test_missing_storage_file_does_not_burn_token_and_rollback_cleans_orphan(
    api_client, db, make_category, make_product, monkeypatch
):
    admin_headers = _login_admin(api_client, db)
    cat = make_category(name="Reliability", slug="reliability-p8", is_active=True)
    prod = make_product(category=cat, name="Resilient Pack", slug="resilient-pack", is_active=True)

    # Failed DB flush after storage.save must delete newly saved orphan file
    from app.services import catalog_service

    original_record_audit = catalog_service.record_admin_audit

    def _boom(*args, **kwargs):
        raise RuntimeError("Simulated DB failure after file save")

    monkeypatch.setattr(catalog_service, "record_admin_audit", _boom)
    with pytest.raises(RuntimeError):
        api_client.post(
            f"/api/admin/products/{prod.id}/asset",
            files={"file": ("pack.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        )
    monkeypatch.setattr(catalog_service, "record_admin_audit", original_record_audit)
    private_root = Path(settings.ASSET_STORAGE_LOCAL_ROOT).resolve()
    stored_files = [p for p in private_root.rglob("*") if p.is_file()]
    assert stored_files == []

    # Upload properly, buy product, obtain grant, then simulate deleted file on storage
    pdf_bytes = _make_pdf_bytes("Resilient")
    api_client.post(
        f"/api/admin/products/{prod.id}/asset",
        files={"file": ("resilient.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=admin_headers,
    )
    db.refresh(prod)
    storage_key = prod.asset_storage_key

    api_client.cookies.clear()
    cust_headers, _ = _register_customer(api_client, "Missing File Buyer")
    _, order_item_id = _buy_product(api_client, cust_headers, prod.id)
    grant = api_client.post(f"/api/downloads/{order_item_id}", headers=cust_headers).json()

    # Delete backing file from private storage manually
    get_asset_storage("local").delete(storage_key)

    r_missing = api_client.get(grant["download_url"])
    assert r_missing.status_code == 404
    # Single-use record remains GRANTED (not burned as COMPLETED) because stream failed to open
    rec = db.get(DownloadRecord, uuid.UUID(grant["download_id"]))
    assert rec.status == DownloadStatus.GRANTED


def test_local_and_mocked_s3_storage_providers(tmp_path):
    # 1. LocalPrivateAssetStorageProvider lifecycle & traversal protection
    local = LocalPrivateAssetStorageProvider(base_dir=tmp_path / "private_assets")
    sample = b"binary-stream-check-" * 5000
    key = f"products/{uuid.uuid4()}/{uuid.uuid4().hex}.zip"
    meta = local.save(io.BytesIO(sample), key, "application/zip", len(sample))
    assert meta.size_bytes == len(sample)
    assert local.exists(key) is True
    assert local.get_metadata(key).size_bytes == len(sample)

    handle = local.open(key, chunk_size=4096)
    downloaded = b"".join(handle.iter_chunks())
    assert downloaded == sample

    with pytest.raises(Exception):
        local.open("../escape.zip")
    local.delete(key)
    assert local.exists(key) is False
    with pytest.raises(AssetNotFoundError):
        local.open(key)

    # 2. S3PrivateAssetStorageProvider with httpx.MockTransport (no real cloud credentials needed)
    bucket_store: dict[str, tuple[bytes, str]] = {}
    captured_requests: list[dict[str, str]] = []

    def _s3_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization", "")
        captured_requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "auth": auth,
                "acl": request.headers.get("x-amz-acl", ""),
            }
        )
        assert auth.startswith("AWS4-HMAC-SHA256 ")
        assert "Credential=test_access_key/" in auth
        assert "x-amz-acl" not in {k.lower() for k in request.headers.keys()}

        obj_path = request.url.path
        if request.method == "PUT":
            body = request.read()
            bucket_store[obj_path] = (body, request.headers.get("content-type", "application/octet-stream"))
            return httpx.Response(200, headers={"ETag": '"mock-etag-1"'})
        if request.method == "HEAD":
            if obj_path not in bucket_store:
                return httpx.Response(404)
            data, ctype = bucket_store[obj_path]
            return httpx.Response(
                200,
                headers={"Content-Length": str(len(data)), "Content-Type": ctype, "ETag": '"mock-etag-1"'},
            )
        if request.method == "GET":
            if obj_path not in bucket_store:
                return httpx.Response(404)
            data, ctype = bucket_store[obj_path]
            return httpx.Response(
                200,
                content=data,
                headers={"Content-Length": str(len(data)), "Content-Type": ctype},
            )
        if request.method == "DELETE":
            bucket_store.pop(obj_path, None)
            return httpx.Response(204)
        return httpx.Response(405)

    s3 = S3PrivateAssetStorageProvider(
        bucket="private-digiverse-bucket",
        region="ap-south-1",
        endpoint_url="https://s3-mock.internal",
        access_key="test_access_key",
        secret_key="test_secret_key",
        use_path_style=True,
        transport=httpx.MockTransport(_s3_handler),
    )

    s3_key = f"products/{uuid.uuid4()}/{uuid.uuid4().hex}.pdf"
    pdf_payload = _make_pdf_bytes("S3 Object Check")
    sha = hashlib.sha256(pdf_payload).hexdigest()
    s3_meta = s3.save(io.BytesIO(pdf_payload), s3_key, "application/pdf", len(pdf_payload), sha256_hex=sha)
    assert s3_meta.storage_backend == "s3"
    assert s3_meta.etag == "mock-etag-1"
    assert s3.exists(s3_key) is True
    assert s3.get_metadata(s3_key).size_bytes == len(pdf_payload)

    s3_handle = s3.open(s3_key, chunk_size=16)
    s3_streamed = b"".join(s3_handle.iter_chunks())
    assert s3_streamed == pdf_payload

    s3.delete(s3_key)
    assert s3.exists(s3_key) is False
    with pytest.raises(AssetNotFoundError):
        s3.open(s3_key)

    # Error path must never leak endpoint, bucket, or keys in exception message
    failing_s3 = S3PrivateAssetStorageProvider(
        bucket="secret-bucket-name",
        region="us-east-1",
        endpoint_url="https://secret-endpoint.internal",
        access_key="SENSITIVE_ACCESS_KEY",
        secret_key="SENSITIVE_SECRET_KEY",
        transport=httpx.MockTransport(lambda req: httpx.Response(500, text="Internal S3 Failure")),
    )
    with pytest.raises(AssetStorageError) as exc_info:
        failing_s3.open(s3_key)
    err_msg = str(exc_info.value)
    assert "SENSITIVE_ACCESS_KEY" not in err_msg
    assert "SENSITIVE_SECRET_KEY" not in err_msg
    assert "secret-bucket-name" not in err_msg
    assert "secret-endpoint.internal" not in err_msg
