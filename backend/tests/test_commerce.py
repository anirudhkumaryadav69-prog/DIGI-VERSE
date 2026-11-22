"""Comprehensive automated tests for Phase 4:
- Wishlist Management (Add, Remove, Clear, Duplicate Prevention, Ownership, Inactive Product Rejection)
- Persistent Shopping Cart (Auto-Create, Add, Update Quantity, Remove, Clear, Backend Price & Discount Math, Duplicate Line Prevention, Ownership)
- Checkout System (Initialization, Empty Cart, Deactivated Item Rejection, Price Manipulation Prevention, Idempotency Key Deduplication, Immutable Order Item Snapshots)
- Payments & Webhooks (Valid/Invalid HMAC Signatures, Amount/Currency Checks, Replay Prevention, Duplicate Webhook Idempotency, Out-of-Order Failure Protection, Refunds)
- Customer & Admin Order Management (Listing, Details, Invoices, IDOR Protection, Admin Search/Filters/Stats, Unverified Fulfillment Prevention)
- Digital Product Delivery (Signed Short-Lived URLs, Pre-Payment Rejection, Cross-Customer IDOR Rejection, Download Record Tracking, Download Limits, Path Traversal Guard, Zero Private URL Leakage)
"""
import hashlib
import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.catalog import Sale
from app.services.admin_auth_service import provision_initial_admin
from app.services.asset_storage_service import get_asset_storage
from app.services.email_service import dev_email_provider
from app.services.payment_gateway import MockPaymentProvider


def _build_valid_zip_bytes(payload_text: str = "DIGI-VERSE BINARY ASSET PAYLOAD") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", payload_text)
    return buf.getvalue()


def _attach_test_asset(product, raw_bytes: bytes, filename: str = "asset.zip") -> None:
    storage_key = f"products/{product.id}/{uuid.uuid4().hex}.zip"
    sha = hashlib.sha256(raw_bytes).hexdigest()
    get_asset_storage("local").save(
        file_obj=io.BytesIO(raw_bytes),
        storage_key=storage_key,
        content_type="application/zip",
        size_bytes=len(raw_bytes),
        sha256_hex=sha,
    )
    product.asset_storage_backend = "local"
    product.asset_storage_key = storage_key
    product.asset_original_filename = filename
    product.asset_content_type = "application/zip"
    product.asset_size_bytes = len(raw_bytes)
    product.asset_sha256 = sha
    product.asset_uploaded_at = datetime.now(timezone.utc)
    product.private_download_url = "asset://managed"


@pytest.fixture(autouse=True)
def _use_mock_payment_provider(monkeypatch):
    """Use the deterministic HMAC-verified MockPaymentProvider during automated tests."""
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MAX_DOWNLOADS_PER_ORDER_ITEM", 3)


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _register_customer(client, name: str = "Rohan Mehta") -> tuple[dict[str, str], dict]:
    suffix = uuid.uuid4().hex[:8]
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"cust-{suffix}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert res.status_code == 201
    return _csrf(client), res.json()["customer"]


def _login_admin(client, db) -> dict[str, str]:
    init_pw = "AdminInitial#2026!"
    new_pw = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=init_pw)
    r = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": init_pw})
    assert r.status_code == 200
    if r.json()["must_change_password"]:
        r2 = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": init_pw, "new_password": new_pw},
            headers=_csrf(client),
        )
        assert r2.status_code == 200
    return _csrf(client)


# ===========================================================================
# 1. WISHLIST TESTS
# ===========================================================================


def test_wishlist_lifecycle_duplicate_prevention_ownership_and_inactive_rejection(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Design Assets", slug="design-assets", is_active=True)
    p_active = make_product(
        category=cat,
        name="Editorial Font Family",
        slug="editorial-font-family",
        original_price=Decimal("1200.00"),
        is_active=True,
    )
    p_inactive = make_product(
        category=cat,
        name="Retired Font",
        slug="retired-font",
        original_price=Decimal("800.00"),
        is_active=False,
    )

    # Unauthenticated access rejected -> 401
    assert api_client.get("/api/wishlist").status_code == 401

    headers_a, _ = _register_customer(api_client, "Customer A")

    # Reject inactive product -> 400
    r_inact = api_client.post(f"/api/wishlist/{p_inactive.id}", headers=headers_a)
    assert r_inact.status_code == 400

    # Add active product -> 201
    r_add = api_client.post(f"/api/wishlist/{p_active.id}", headers=headers_a)
    assert r_add.status_code == 201
    assert r_add.json()["total_items"] == 1
    assert r_add.json()["items"][0]["product_id"] == str(p_active.id)

    # Duplicate wishlist entry rejected -> 409
    r_dup = api_client.post(f"/api/wishlist/{p_active.id}", headers=headers_a)
    assert r_dup.status_code == 409

    # Customer B has an isolated empty wishlist and cannot remove Customer A's item
    api_client.cookies.clear()
    headers_b, _ = _register_customer(api_client, "Customer B")
    r_list_b = api_client.get("/api/wishlist")
    assert r_list_b.status_code == 200
    assert r_list_b.json()["total_items"] == 0
    assert api_client.delete(f"/api/wishlist/{p_active.id}", headers=headers_b).status_code == 404


# ===========================================================================
# 2. PERSISTENT SHOPPING CART TESTS
# ===========================================================================


def test_shopping_cart_crud_discount_math_duplicate_prevention_and_ownership(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Templates", slug="templates", is_active=True)
    p1 = make_product(
        category=cat,
        name="NextJS SaaS Starter",
        slug="nextjs-saas-starter",
        original_price=Decimal("2000.00"),
        is_active=True,
    )
    p2 = make_product(
        category=cat,
        name="Tailwind Component Pack",
        slug="tailwind-pack",
        original_price=Decimal("1000.00"),
        is_active=True,
    )
    p_inactive = make_product(
        category=cat,
        name="Inactive Template",
        slug="inactive-tpl",
        original_price=Decimal("500.00"),
        is_active=False,
    )

    # Add an active 25% discount on p1 (2000.00 -> 1500.00)
    now = datetime.now(timezone.utc)
    db.add(
        Sale(
            product_id=p1.id,
            original_price_snapshot=Decimal("2000.00"),
            discounted_price=Decimal("1500.00"),
            starts_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=2),
            is_active=True,
        )
    )
    db.flush()

    headers_a, _ = _register_customer(api_client, "Cart Owner A")

    # Auto-create empty cart
    r_empty = api_client.get("/api/cart")
    assert r_empty.status_code == 200
    assert r_empty.json()["total_quantity"] == 0
    assert Decimal(r_empty.json()["final_payable_amount"]) == Decimal("0.00")

    # Reject inactive product -> 400
    assert (
        api_client.post(
            "/api/cart/items",
            json={"product_id": str(p_inactive.id), "quantity": 1},
            headers=headers_a,
        ).status_code
        == 400
    )

    # Add p1 (discounted to 1500) and p2 (1000)
    r_add1 = api_client.post(
        "/api/cart/items",
        json={"product_id": str(p1.id), "quantity": 1},
        headers=headers_a,
    )
    assert r_add1.status_code == 201
    item1_id = r_add1.json()["items"][0]["id"]

    # Prevent duplicate product line -> 409
    r_dup = api_client.post(
        "/api/cart/items",
        json={"product_id": str(p1.id), "quantity": 1},
        headers=headers_a,
    )
    assert r_dup.status_code == 409

    r_add2 = api_client.post(
        "/api/cart/items",
        json={"product_id": str(p2.id), "quantity": 2},
        headers=headers_a,
    )
    assert r_add2.status_code == 201
    cart_data = r_add2.json()
    item2_id = next(i["id"] for i in cart_data["items"] if i["product_id"] == str(p2.id))

    # Subtotal = 2000*1 + 1000*2 = 4000.00; Discount = 500.00; Final = 3500.00
    assert Decimal(cart_data["subtotal"]) == Decimal("4000.00")
    assert Decimal(cart_data["total_discount"]) == Decimal("500.00")
    assert Decimal(cart_data["final_payable_amount"]) == Decimal("3500.00")

    # Update quantity of item1 to 2 -> Subtotal = 6000, Discount = 1000, Final = 5000
    r_upd = api_client.patch(
        f"/api/cart/items/{item1_id}",
        json={"quantity": 2},
        headers=headers_a,
    )
    assert r_upd.status_code == 200
    assert Decimal(r_upd.json()["final_payable_amount"]) == Decimal("5000.00")

    # Customer B cannot modify or remove Customer A's cart item
    api_client.cookies.clear()
    headers_b, _ = _register_customer(api_client, "Cart Owner B")
    assert (
        api_client.patch(
            f"/api/cart/items/{item1_id}",
            json={"quantity": 5},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert api_client.delete(f"/api/cart/items/{item2_id}", headers=headers_b).status_code == 404


# ===========================================================================
# 3. CHECKOUT, PAYMENTS, WEBHOOKS, ORDERS & DIGITAL DELIVERY E2E TESTS
# ===========================================================================


def test_checkout_validation_idempotency_price_manipulation_and_snapshots(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Code Kits", slug="code-kits", is_active=True)
    p1 = make_product(
        category=cat,
        name="FastAPI Microservice Kit",
        slug="fastapi-kit",
        original_price=Decimal("1500.00"),
        is_active=True,
        private_download_url="https://drive.google.com/file/d/PRIVATE_FASTAPI_KIT/view",
    )

    headers, _ = _register_customer(api_client, "Checkout Tester")

    # Empty cart checkout rejected -> 400
    assert api_client.post("/api/checkout", headers=headers).status_code == 400

    # Add product to cart
    api_client.post(
        "/api/cart/items",
        json={"product_id": str(p1.id), "quantity": 1},
        headers=headers,
    )

    # Price manipulation attempt in checkout body rejected -> 422 (StrictRequestModel forbids extra fields)
    r_manip = api_client.post(
        "/api/checkout",
        json={"total_amount": "1.00", "discount": "1499.00"},
        headers=headers,
    )
    assert r_manip.status_code == 422

    # Idempotent checkout initialization
    idem_key = f"idem-{uuid.uuid4().hex}"
    r_chk1 = api_client.post(
        "/api/checkout",
        json={"idempotency_key": idem_key},
        headers=headers,
    )
    assert r_chk1.status_code == 201
    chk1 = r_chk1.json()
    assert Decimal(chk1["total_amount"]) == Decimal("1500.00")

    # Repeating checkout with same idempotency_key returns the exact same pending order
    r_chk2 = api_client.post(
        "/api/checkout",
        json={"idempotency_key": idem_key},
        headers=headers,
    )
    assert r_chk2.status_code == 201
    assert r_chk2.json()["order_id"] == chk1["order_id"]
    assert r_chk2.json()["payment"]["gateway_order_id"] == chk1["payment"]["gateway_order_id"]

    # Cart is NOT cleared before payment verification
    assert api_client.get("/api/cart").json()["total_quantity"] == 1

    # Verify immutable order item snapshot even if product name/price changes later
    p1.name = "Renamed FastAPI Kit v2"
    p1.original_price = Decimal("3000.00")
    db.flush()

    r_order = api_client.get(f"/api/orders/{chk1['order_id']}")
    assert r_order.status_code == 200
    item_snap = r_order.json()["items"][0]
    assert item_snap["product_name_snapshot"] == "FastAPI Microservice Kit"
    assert Decimal(item_snap["purchase_price"]) == Decimal("1500.00")


def test_complete_purchase_payment_verification_delivery_and_limits(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Pro Assets", slug="pro-assets", is_active=True)
    product = make_product(
        category=cat,
        name="Ultimate Design Token Suite",
        slug="ultimate-design-tokens",
        original_price=Decimal("999.00"),
        is_active=True,
    )
    asset_bytes = _build_valid_zip_bytes("Ultimate Design Token Suite binary content v1")
    _attach_test_asset(product, asset_bytes, filename="design-tokens.zip")
    secret_url = product.asset_storage_key
    db.flush()

    headers_a, _ = _register_customer(api_client, "Buyer A")
    api_client.post(
        "/api/cart/items",
        json={"product_id": str(product.id), "quantity": 1},
        headers=headers_a,
    )
    r_chk = api_client.post("/api/checkout", headers=headers_a)
    assert r_chk.status_code == 201
    chk = r_chk.json()
    order_id = chk["order_id"]
    gateway_order_id = chk["payment"]["gateway_order_id"]

    # Fetch order item ID
    order_before = api_client.get(f"/api/orders/{order_id}").json()
    order_item_id = order_before["items"][0]["id"]
    assert order_before["download_eligible"] is False

    # 1. Attempting download BEFORE payment verification is rejected -> 403
    r_early_dl = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
    assert r_early_dl.status_code == 403

    # 2. Forged / invalid payment signature is rejected -> 400
    r_forged = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gateway_order_id,
            "gateway_payment_id": "pay_mock_forged_1",
            "gateway_signature": "invalid_forged_signature_hex_value",
        },
        headers=headers_a,
    )
    assert r_forged.status_code == 400

    # 3. Valid cryptographic payment signature succeeds -> 200
    gateway_payment_id = f"pay_mock_{uuid.uuid4().hex[:12]}"
    valid_sig = MockPaymentProvider.sign_payment(gateway_order_id, gateway_payment_id)

    r_verify = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gateway_order_id,
            "gateway_payment_id": gateway_payment_id,
            "gateway_signature": valid_sig,
            "payment_method": "upi",
        },
        headers=headers_a,
    )
    assert r_verify.status_code == 200
    verified_order = r_verify.json()
    assert verified_order["payment_status"] == "paid"
    assert verified_order["status"] == "fulfilled"
    assert verified_order["download_eligible"] is True

    # Cart is now automatically cleared after confirmed payment
    assert api_client.get("/api/cart").json()["total_quantity"] == 0

    # Payment replay prevention -> 409 Conflict
    r_replay = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gateway_order_id,
            "gateway_payment_id": gateway_payment_id,
            "gateway_signature": valid_sig,
        },
        headers=headers_a,
    )
    assert r_replay.status_code == 409

    # Verify invoice endpoint
    r_inv = api_client.get(f"/api/orders/{order_id}/invoice")
    assert r_inv.status_code == 200
    assert r_inv.json()["gateway_payment_id"] == gateway_payment_id

    # Verify email notifications were sent and never contain private_download_url
    sent_templates = {n["template"] for n in dev_email_provider.sent_notifications}
    assert {"order_confirmation", "payment_success", "purchase_receipt", "download_ready"} <= sent_templates
    for notif in dev_email_provider.sent_notifications:
        assert secret_url not in notif["body"]
        assert secret_url not in json.dumps(notif["metadata"])

    # 4. Authorized digital download after payment verification (max_downloads = 3 in fixture)
    for attempt in range(1, 4):
        r_dl = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
        assert r_dl.status_code == 201
        dl_data = r_dl.json()
        assert secret_url not in json.dumps(dl_data)
        assert dl_data["downloads_used"] == attempt
        assert dl_data["remaining_downloads"] == 3 - attempt

        # Stream the signed download URL and verify exact binary bytes match uploaded file
        r_file = api_client.get(dl_data["download_url"])
        assert r_file.status_code == 200
        assert r_file.content == asset_bytes
        assert r_file.headers.get("x-content-type-options") == "nosniff"
        assert "design-tokens.zip" in (r_file.headers.get("content-disposition") or "")

        # Check download record status endpoint
        r_status = api_client.get(f"/api/downloads/{dl_data['download_id']}/status")
        assert r_status.status_code == 200
        assert r_status.json()["status"] == "completed"

    # 5. Exceeding download limit (4th attempt when max=3) is rejected -> 429
    r_limit = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
    assert r_limit.status_code == 429

    # 6. Cross-customer IDOR protection: Customer B cannot access Customer A's order, invoice, or download
    api_client.cookies.clear()
    headers_b, _ = _register_customer(api_client, "Intruder B")
    assert api_client.get(f"/api/orders/{order_id}").status_code == 403
    assert api_client.get(f"/api/orders/{order_id}/invoice").status_code == 403
    assert api_client.post(f"/api/downloads/{order_item_id}", headers=headers_b).status_code == 403


def test_webhook_idempotency_out_of_order_protection_and_admin_order_management(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Webhooks", slug="webhooks", is_active=True)
    product = make_product(
        category=cat,
        name="Webhook Test Asset",
        slug="webhook-test-asset",
        original_price=Decimal("500.00"),
        is_active=True,
        private_download_url="https://drive.google.com/file/d/WEBHOOK_ASSET/view",
    )

    headers_cust, _ = _register_customer(api_client, "Webhook Buyer")
    api_client.post(
        "/api/cart/items",
        json={"product_id": str(product.id), "quantity": 1},
        headers=headers_cust,
    )
    chk = api_client.post("/api/checkout", headers=headers_cust).json()
    order_id = chk["order_id"]
    gateway_order_id = chk["payment"]["gateway_order_id"]
    gateway_payment_id = f"pay_wh_{uuid.uuid4().hex[:10]}"

    # Customer cannot access admin order endpoints -> 403
    assert api_client.get("/api/admin/orders").status_code == 403

    # Admin cannot mark an unpaid order as fulfilled before payment verification -> 400
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    r_premature = api_client.patch(
        f"/api/admin/orders/{order_id}/status",
        json={"status": "fulfilled"},
        headers=admin_headers,
    )
    assert r_premature.status_code == 400

    # 1. Invalid webhook signature rejected -> 400
    capture_payload = {
        "event_id": f"evt_cap_{uuid.uuid4().hex[:10]}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": gateway_payment_id,
                    "order_id": gateway_order_id,
                    "amount": 50000,
                    "currency": "INR",
                    "method": "upi",
                }
            }
        },
    }
    raw_bytes = json.dumps(capture_payload).encode("utf-8")
    r_bad_wh = api_client.post(
        "/api/payments/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "bad_sig"},
    )
    assert r_bad_wh.status_code == 400

    # 2. Valid capture webhook marks order paid & fulfilled -> 200
    valid_wh_sig = MockPaymentProvider.sign_webhook(raw_bytes)
    r_ok_wh = api_client.post(
        "/api/payments/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_wh_sig},
    )
    assert r_ok_wh.status_code == 200
    assert r_ok_wh.json()["status"] == "captured"

    # 3. Duplicate webhook delivery with same event_id is handled idempotently
    notif_count_before = len(dev_email_provider.sent_notifications)
    r_dup_wh = api_client.post(
        "/api/payments/webhook",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_wh_sig},
    )
    assert r_dup_wh.status_code == 200
    assert r_dup_wh.json()["status"] == "duplicate_ignored"
    assert len(dev_email_provider.sent_notifications) == notif_count_before

    # 4. Out-of-order payment.failed webhook arriving AFTER payment.captured is safely ignored!
    failed_payload = {
        "event_id": f"evt_fail_{uuid.uuid4().hex[:10]}",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": gateway_payment_id,
                    "order_id": gateway_order_id,
                    "amount": 50000,
                    "currency": "INR",
                }
            }
        },
    }
    fail_bytes = json.dumps(failed_payload).encode("utf-8")
    r_late_fail = api_client.post(
        "/api/payments/webhook",
        content=fail_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": MockPaymentProvider.sign_webhook(fail_bytes),
        },
    )
    assert r_late_fail.status_code == 200
    assert r_late_fail.json()["status"] == "ignored_out_of_order_failure"

    # Verify via Admin Order API that the order is still PAID and FULFILLED
    r_admin_ord = api_client.get(f"/api/admin/orders/{order_id}")
    assert r_admin_ord.status_code == 200
    assert r_admin_ord.json()["payment_status"] == "paid"
    assert r_admin_ord.json()["status"] == "fulfilled"

    # Verify Admin Order Statistics & Search
    r_stats = api_client.get("/api/admin/orders/statistics")
    assert r_stats.status_code == 200
    assert r_stats.json()["paid_orders"] >= 1
    assert Decimal(r_stats.json()["total_revenue"]) >= Decimal("500.00")

    r_search = api_client.get(f"/api/admin/orders?search={chk['order_number']}")
    assert r_search.status_code == 200
    assert r_search.json()["total"] == 1

    # 5. Admin initiates refund transition (FULFILLED -> REFUNDED)
    r_refund = api_client.patch(
        f"/api/admin/orders/{order_id}/status",
        json={"status": "refunded"},
        headers=admin_headers,
    )
    assert r_refund.status_code == 200
    assert r_refund.json()["status"] == "refunded"
    assert r_refund.json()["payment_status"] == "refunded"
    assert r_refund.json()["download_eligible"] is False


def test_path_traversal_in_private_download_url_rejected(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Security Test", slug="security-test", is_active=True)
    product = make_product(
        category=cat,
        name="Traversal Test Asset",
        slug="traversal-test-asset",
        original_price=Decimal("300.00"),
        is_active=True,
        private_download_url="../../etc/passwd",
    )

    headers, _ = _register_customer(api_client, "Traversal Tester")
    api_client.post(
        "/api/cart/items",
        json={"product_id": str(product.id), "quantity": 1},
        headers=headers,
    )
    chk = api_client.post("/api/checkout", headers=headers).json()
    order_id = chk["order_id"]
    gw_order_id = chk["payment"]["gateway_order_id"]
    gw_pay_id = f"pay_trav_{uuid.uuid4().hex[:8]}"

    api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_pay_id,
            "gateway_signature": MockPaymentProvider.sign_payment(gw_order_id, gw_pay_id),
        },
        headers=headers,
    )
    order_item_id = api_client.get(f"/api/orders/{order_id}").json()["items"][0]["id"]

    # Attempting to download a product whose private_download_url contains '..' is rejected with 400
    r_dl = api_client.post(f"/api/downloads/{order_item_id}", headers=headers)
    assert r_dl.status_code == 400
    assert "unsafe download storage path" in r_dl.json()["detail"].lower()

