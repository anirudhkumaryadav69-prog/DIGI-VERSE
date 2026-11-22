"""Phase 6 Automated End-to-End Customer Storefront Journey Tests:
Verifies all 14 required customer journeys against the live `digiverse_test` PostgreSQL database:
1. Browse products (including homepage sections: banners, videos, public settings, featured/newest/discounted).
2. Search and filter products (search, category slug, min/max effective price, `on_sale=true`, sort_by).
3. Open a product detail page (verifying sanitized public metadata and zero private URL exposure).
4. Add and remove wishlist items.
5. Add and remove cart items.
6. Update cart quantities.
7. Proceed to checkout (idempotent order creation, cart preserved before payment verification).
8. Handle payment failure (invalid signature marks payment/order failed; cart remains intact; retry payment re-initializes without duplicate order).
9. Handle verified payment success (HMAC-SHA256 verified capture, order fulfilled, cart cleared).
10. View order history.
11. Open an invoice.
12. Access an eligible digital download (signed short-lived token + file stream).
13. Handle an expired/revoked session (401 on protected customer endpoints).
14. Attempt to access an unauthorized customer route / another customer's order or invoice (401/403/404 IDOR protection).
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.catalog import Sale
from app.services.payment_gateway import MockPaymentProvider


@pytest.fixture(autouse=True)
def _use_mock_payment_gateway(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MAX_DOWNLOADS_PER_ORDER_ITEM", 3)


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _register_customer(client, name: str = "Kavya Nair") -> tuple[dict[str, str], dict]:
    suffix = uuid.uuid4().hex[:8]
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"journey-{suffix}@example.test",
            "phone_number": f"+9196{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert res.status_code == 201
    return _csrf(client), res.json()["customer"]


def test_complete_phase6_customer_storefront_journeys(
    api_client, db, make_category, make_product
):
    now = datetime.now(timezone.utc)
    cat_ui = make_category(name="Design Systems", slug="design-systems", is_active=True)
    cat_code = make_category(name="Starter Kits", slug="starter-kits", is_active=True)

    p_discounted = make_product(
        category=cat_ui,
        name="Enterprise Design System Pro",
        slug="enterprise-design-system-pro",
        original_price=Decimal("3000.00"),
        is_active=True,
    )
    # Attach both safe public metadata and sensitive keys to verify sanitization
    p_discounted.product_type = "Figma + React"
    p_discounted.product_metadata = {
        "format": "Figma & React 19",
        "license": "Commercial Unlimited",
        "components_count": 240,
        "internal_secret_key": "MUST_NOT_LEAK",
        "private_storage_path": "s3://bucket/secret.zip",
    }
    import hashlib
    import io
    import zipfile
    from app.services.asset_storage_service import get_asset_storage

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("design-system.txt", "Enterprise Design System Pro Binary Package")
    expected_asset_bytes = zbuf.getvalue()
    ds_key = f"products/{p_discounted.id}/{uuid.uuid4().hex}.zip"
    get_asset_storage("local").save(
        io.BytesIO(expected_asset_bytes),
        storage_key=ds_key,
        content_type="application/zip",
        size_bytes=len(expected_asset_bytes),
        sha256_hex=hashlib.sha256(expected_asset_bytes).hexdigest(),
    )
    p_discounted.asset_storage_backend = "local"
    p_discounted.asset_storage_key = ds_key
    p_discounted.asset_original_filename = "design-system-pro.zip"
    p_discounted.asset_content_type = "application/zip"
    p_discounted.asset_size_bytes = len(expected_asset_bytes)
    p_discounted.private_download_url = "asset://managed"

    sale = Sale(
        product_id=p_discounted.id,
        original_price_snapshot=Decimal("3000.00"),
        discounted_price=Decimal("2100.00"),
        starts_at=now - timedelta(hours=2),
        expires_at=now + timedelta(days=5),
        is_active=True,
    )
    db.add(sale)
    p_discounted.is_on_sale = True

    p_regular = make_product(
        category=cat_code,
        name="FastAPI SaaS Boilerplate",
        slug="fastapi-saas-boilerplate",
        original_price=Decimal("1800.00"),
        is_active=True,
    )
    p_regular.product_type = "Python + React"
    p_regular.private_download_url = "https://storage.example.test/private/fastapi-saas.zip"
    db.commit()

    # -----------------------------------------------------------------------
    # Journey 14 (Part A): Unauthenticated access to protected customer routes
    # -----------------------------------------------------------------------
    for protected_path in ("/api/wishlist", "/api/cart", "/api/orders", "/api/downloads", "/api/auth/me"):
        assert api_client.get(protected_path).status_code == 401

    # -----------------------------------------------------------------------
    # Journey 1: Browse products, categories, banners, videos, public settings
    # -----------------------------------------------------------------------
    r_browse = api_client.get("/api/products?page=1&page_size=12")
    assert r_browse.status_code == 200
    assert r_browse.json()["total"] == 2
    assert "private_download_url" not in r_browse.text
    assert "MUST_NOT_LEAK" not in r_browse.text

    assert api_client.get("/api/categories").status_code == 200
    assert api_client.get("/api/banners").status_code == 200
    assert api_client.get("/api/videos").status_code == 200
    assert api_client.get("/api/settings/public").status_code == 200

    # -----------------------------------------------------------------------
    # Journey 2: Search and filter products (including on_sale=true & effective price)
    # -----------------------------------------------------------------------
    r_sale_only = api_client.get("/api/products?on_sale=true")
    assert r_sale_only.status_code == 200
    assert r_sale_only.json()["total"] == 1
    assert r_sale_only.json()["items"][0]["slug"] == "enterprise-design-system-pro"

    r_price_filter = api_client.get("/api/products?min_price=2000&max_price=2200")
    assert r_price_filter.status_code == 200
    assert r_price_filter.json()["total"] == 1
    assert r_price_filter.json()["items"][0]["slug"] == "enterprise-design-system-pro"

    r_search = api_client.get("/api/products?search=FastAPI&category=starter-kits")
    assert r_search.status_code == 200
    assert r_search.json()["total"] == 1
    assert r_search.json()["items"][0]["slug"] == "fastapi-saas-boilerplate"

    # -----------------------------------------------------------------------
    # Journey 3: Open product detail page (verify metadata sanitization)
    # -----------------------------------------------------------------------
    r_detail = api_client.get(f"/api/products/{p_discounted.slug}")
    assert r_detail.status_code == 200
    detail_data = r_detail.json()
    assert Decimal(detail_data["effective_price"]) == Decimal("2100.00")
    assert Decimal(detail_data["original_price"]) == Decimal("3000.00")
    assert detail_data["is_on_sale"] is True
    assert detail_data["metadata"]["format"] == "Figma & React 19"
    assert detail_data["metadata"]["license"] == "Commercial Unlimited"
    assert "internal_secret_key" not in detail_data["metadata"]
    assert "private_storage_path" not in detail_data["metadata"]
    assert "private_download_url" not in r_detail.text

    # -----------------------------------------------------------------------
    # Journey 4: Add and remove wishlist items
    # -----------------------------------------------------------------------
    headers_a, _ = _register_customer(api_client, "Kavya Nair")

    r_w_add = api_client.post(f"/api/wishlist/{p_discounted.id}", headers=headers_a)
    assert r_w_add.status_code == 201
    assert r_w_add.json()["total_items"] == 1

    r_w_rem = api_client.delete(f"/api/wishlist/{p_discounted.id}", headers=headers_a)
    assert r_w_rem.status_code == 200
    assert r_w_rem.json()["total_items"] == 0

    # -----------------------------------------------------------------------
    # Journey 5 & 6: Add and remove cart items, and update cart quantities
    # -----------------------------------------------------------------------
    r_c_add1 = api_client.post(
        "/api/cart/items",
        json={"product_id": str(p_discounted.id), "quantity": 1},
        headers=headers_a,
    )
    assert r_c_add1.status_code == 201
    item1_id = r_c_add1.json()["items"][0]["id"]

    r_c_add2 = api_client.post(
        "/api/cart/items",
        json={"product_id": str(p_regular.id), "quantity": 1},
        headers=headers_a,
    )
    assert r_c_add2.status_code == 201
    item2_id = next(i["id"] for i in r_c_add2.json()["items"] if i["product_id"] == str(p_regular.id))

    # Remove second item
    r_c_rem = api_client.delete(f"/api/cart/items/{item2_id}", headers=headers_a)
    assert r_c_rem.status_code == 200
    assert len(r_c_rem.json()["items"]) == 1

    # Update quantity of first item to 2 (2 * 2100.00 = 4200.00 payable, 1800.00 discount)
    r_c_qty = api_client.patch(
        f"/api/cart/items/{item1_id}",
        json={"quantity": 2},
        headers=headers_a,
    )
    assert r_c_qty.status_code == 200
    assert r_c_qty.json()["total_quantity"] == 2
    assert Decimal(r_c_qty.json()["subtotal"]) == Decimal("6000.00")
    assert Decimal(r_c_qty.json()["total_discount"]) == Decimal("1800.00")
    assert Decimal(r_c_qty.json()["final_payable_amount"]) == Decimal("4200.00")

    # -----------------------------------------------------------------------
    # Journey 7: Proceed to checkout (idempotent, cart not cleared prematurely)
    # -----------------------------------------------------------------------
    idem_key = f"phase6-idem-{uuid.uuid4().hex[:10]}"
    r_chk = api_client.post(
        "/api/checkout",
        json={"idempotency_key": idem_key},
        headers=headers_a,
    )
    assert r_chk.status_code == 201
    chk_data = r_chk.json()
    order_id = chk_data["order_id"]
    first_gateway_order_id = chk_data["payment"]["gateway_order_id"]
    assert Decimal(chk_data["total_amount"]) == Decimal("4200.00")

    # Confirm cart is still intact prior to payment verification
    assert api_client.get("/api/cart").json()["total_quantity"] == 2

    # -----------------------------------------------------------------------
    # Journey 8: Handle payment failure & retry payment without duplicate order
    # -----------------------------------------------------------------------
    r_fail = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": first_gateway_order_id,
            "gateway_payment_id": f"pay_bad_{uuid.uuid4().hex[:10]}",
            "gateway_signature": "invalid_signature_0000000000",
            "payment_method": "upi",
        },
        headers=headers_a,
    )
    assert r_fail.status_code == 400

    # Order is marked failed and downloads remain locked
    r_ord_failed = api_client.get(f"/api/orders/{order_id}")
    assert r_ord_failed.status_code == 200
    assert r_ord_failed.json()["payment_status"] == "failed"
    assert r_ord_failed.json()["download_eligible"] is False

    # Retry payment on the same order -> returns new payment attempt for the SAME order_id
    r_retry = api_client.post(f"/api/orders/{order_id}/retry-payment", headers=headers_a)
    assert r_retry.status_code == 200
    retry_data = r_retry.json()
    assert retry_data["order_id"] == order_id
    retry_gateway_order_id = retry_data["payment"]["gateway_order_id"]

    # Confirm no duplicate order was created
    assert api_client.get("/api/orders").json()["total"] == 1

    # -----------------------------------------------------------------------
    # Journey 9: Handle verified payment success
    # -----------------------------------------------------------------------
    valid_payment_id = f"pay_ok_{uuid.uuid4().hex[:10]}"
    valid_sig = MockPaymentProvider.sign_payment(retry_gateway_order_id, valid_payment_id)

    r_verify = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": order_id,
            "gateway_order_id": retry_gateway_order_id,
            "gateway_payment_id": valid_payment_id,
            "gateway_signature": valid_sig,
            "payment_method": "upi",
        },
        headers=headers_a,
    )
    assert r_verify.status_code == 200
    verified_ord = r_verify.json()
    assert verified_ord["payment_status"] == "paid"
    assert verified_ord["status"] == "fulfilled"
    assert verified_ord["download_eligible"] is True

    # Cart is cleared after verified payment
    assert api_client.get("/api/cart").json()["total_quantity"] == 0

    # -----------------------------------------------------------------------
    # Journey 10 & 11: View order history and open an official invoice
    # -----------------------------------------------------------------------
    r_orders = api_client.get("/api/orders")
    assert r_orders.status_code == 200
    assert r_orders.json()["total"] == 1
    order_item_id = r_orders.json()["items"][0]["items"][0]["id"]

    r_inv = api_client.get(f"/api/orders/{order_id}/invoice")
    assert r_inv.status_code == 200
    inv_data = r_inv.json()
    assert inv_data["order_id"] == order_id
    assert Decimal(inv_data["total_amount"]) == Decimal("4200.00")
    assert inv_data["gateway_payment_id"] == valid_payment_id

    # -----------------------------------------------------------------------
    # Journey 12: Access an eligible digital download
    # -----------------------------------------------------------------------
    r_dl_list = api_client.get("/api/downloads")
    assert r_dl_list.status_code == 200
    assert len(r_dl_list.json()["eligible_items"]) == 1

    r_grant = api_client.post(f"/api/downloads/{order_item_id}", headers=headers_a)
    assert r_grant.status_code == 201
    grant_data = r_grant.json()
    # quantity=2 * MAX_DOWNLOADS_PER_ORDER_ITEM(3) = 6 total allowed; 1 used -> 5 remaining
    assert grant_data["remaining_downloads"] == 5
    assert "private_download_url" not in r_grant.text

    r_file = api_client.get(grant_data["download_url"])
    assert r_file.status_code == 200
    assert r_file.content == expected_asset_bytes
    assert ds_key not in r_grant.text

    # -----------------------------------------------------------------------
    # Journey 14 (Part B): Cross-customer IDOR attempt rejected
    # -----------------------------------------------------------------------
    customer_a_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    headers_b, _ = _register_customer(api_client, "Other Customer")
    assert api_client.get(f"/api/orders/{order_id}").status_code in (403, 404)
    assert api_client.get(f"/api/orders/{order_id}/invoice").status_code in (403, 404)
    assert api_client.post(f"/api/downloads/{order_item_id}", headers=headers_b).status_code in (
        403,
        404,
    )

    # -----------------------------------------------------------------------
    # Journey 13: Handle an expired / logged-out session
    # -----------------------------------------------------------------------
    api_client.cookies.clear()
    for k, v in customer_a_cookies.items():
        api_client.cookies.set(k, v)

    r_logout = api_client.post("/api/auth/logout", headers=headers_a)
    assert r_logout.status_code == 200
    assert api_client.get("/api/auth/me").status_code == 401
    assert api_client.get("/api/orders").status_code == 401
