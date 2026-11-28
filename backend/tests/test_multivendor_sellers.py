"""Phase 9 Comprehensive Tests: Multi-Vendor Sellers, IDOR Isolation, Storefronts & Mixed-Seller Orders."""
from __future__ import annotations

import io
import uuid
import zipfile
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.enums import ProductApprovalStatus, SellerApplicationStatus
from app.services.admin_auth_service import provision_initial_admin
from app.services.payment_gateway import MockPaymentProvider


@pytest.fixture(autouse=True)
def _mock_payment_mode(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")


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


def _register_customer(client, name: str = "Creator User") -> tuple[dict[str, str], dict, dict[str, str]]:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"user-{suffix}@example.test",
            "phone_number": f"+9197{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert r.status_code == 201
    return _csrf(client), r.json()["customer"], dict(client.cookies)


def _make_zip_bytes(filename: str = "kit.txt", content: bytes = b"Authentic Creator Zip") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _make_pdf_bytes(title: str = "Creator PDF") -> bytes:
    return f"%PDF-1.4\n1 0 obj << /Type /Catalog /Title ({title}) >> endobj\n%%EOF\n".encode("ascii")


def _apply_and_approve_seller(
    client,
    db,
    *,
    name: str,
    store_name: str,
    store_slug: str,
) -> tuple[dict[str, str], dict[str, str], dict]:
    client.cookies.clear()
    headers, cust, cust_cookies = _register_customer(client, name=name)
    r_app = client.post(
        "/api/seller/application",
        json={
            "store_name": store_name,
            "store_slug": store_slug,
            "seller_display_name": name,
            "store_description": f"Digital assets by {store_name}",
            "application_description": f"Selling curated UI kits and digital tools via {store_name}.",
            "contact_email": cust["email"],
            "country": "India",
            "business_type": "Design Studio",
            "product_categories": ["UI Kits", "Templates"],
        },
        headers=headers,
    )
    assert r_app.status_code == 201
    seller_profile = r_app.json()
    assert seller_profile["application_status"] == "pending"

    # Pending seller blocked from seller studio
    assert client.get("/api/seller/overview").status_code == 403

    # Admin approves seller
    client.cookies.clear()
    admin_headers = _login_admin(client, db)
    r_rev = client.post(
        f"/api/admin/sellers/{seller_profile['id']}/review",
        json={"action": "approve"},
        headers=admin_headers,
    )
    assert r_rev.status_code == 200
    assert r_rev.json()["application_status"] == "approved"

    # Restore seller session
    client.cookies.clear()
    client.cookies.update(cust_cookies)
    return headers, cust_cookies, r_rev.json()


# ===========================================================================
# 1. ONBOARDING LIFECYCLE, REJECTION, RESUBMISSION & ROLE PRESERVATION
# ===========================================================================


def test_seller_onboarding_rejection_resubmission_and_duplicate_guards(api_client, db):
    cust_headers, cust, cust_cookies = _register_customer(api_client, name="Maya Creator")

    # Apply for seller store
    r_app = api_client.post(
        "/api/seller/application",
        json={
            "store_name": "Maya Studio",
            "store_slug": "maya-studio",
            "seller_display_name": "Maya",
            "store_description": "Design templates",
            "application_description": "I build Figma UI kits and React templates for teams.",
            "contact_email": cust["email"],
            "country": "India",
            "business_type": "Independent Creator",
            "product_categories": ["UI Kits"],
        },
        headers=cust_headers,
    )
    assert r_app.status_code == 201
    seller_id = r_app.json()["id"]

    # Duplicate application while PENDING rejected (409)
    r_dup = api_client.post(
        "/api/seller/application",
        json={
            "store_name": "Maya Studio 2",
            "store_slug": "maya-studio-2",
            "seller_display_name": "Maya",
            "application_description": "Duplicate attempt while pending review.",
            "contact_email": cust["email"],
            "country": "India",
            "business_type": "Independent Creator",
            "product_categories": [],
        },
        headers=cust_headers,
    )
    assert r_dup.status_code == 409

    # Pending seller cannot access seller endpoints
    assert api_client.get("/api/seller/products").status_code == 403
    assert api_client.post("/api/seller/products", json={}, headers=cust_headers).status_code in (403, 422)

    # Admin rejects with reason -> customer can read rejection reason and resubmit
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/sellers/{seller_id}/review",
            json={"action": "reject", "reason": "Portfolio sample links needed in description."},
            headers=admin_headers,
        ).status_code
        == 200
    )

    api_client.cookies.clear()
    api_client.cookies.update(cust_cookies)
    r_status = api_client.get("/api/seller/application")
    assert r_status.status_code == 200
    assert r_status.json()["application_status"] == "rejected"
    assert "Portfolio sample" in r_status.json()["rejection_reason"]

    # Update & resubmit
    r_resub = api_client.post(
        "/api/seller/application",
        json={
            "store_name": "Maya Studio",
            "store_slug": "maya-studio",
            "seller_display_name": "Maya",
            "store_description": "Verified Figma & React toolkits",
            "application_description": "Updated portfolio with 12 templates and complete docs.",
            "contact_email": cust["email"],
            "country": "India",
            "business_type": "Design Studio",
            "product_categories": ["UI Kits"],
        },
        headers=cust_headers,
    )
    assert r_resub.status_code == 201
    assert r_resub.json()["application_status"] == "pending"
    assert r_resub.json()["rejection_reason"] is None

    # Admin approves -> verify audit log + retained customer capabilities
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/sellers/{seller_id}/review",
            json={"action": "approve"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    audits = db.scalars(
        select(AuditLog).where(AuditLog.entity_id == str(seller_id))
    ).all()
    actions = {a.action for a in audits}
    assert {"seller.rejected", "seller.approved"}.issubset(actions)

    api_client.cookies.clear()
    api_client.cookies.update(cust_cookies)
    me = api_client.get("/api/auth/me").json()
    assert me["is_seller"] is True
    assert me["seller_status"] == "approved"
    # Existing customer shopping routes still accessible
    assert api_client.get("/api/cart").status_code == 200
    assert api_client.get("/api/wishlist").status_code == 200
    assert api_client.get("/api/orders").status_code == 200


# ===========================================================================
# 2. CROSS-SELLER AUTHORIZATION, IDOR GUARDS & PRODUCT MODERATION
# ===========================================================================


def test_cross_seller_idor_isolation_and_first_time_moderation(
    api_client, db, make_category, make_product
):
    cat = make_category(name="UI Systems", slug="ui-systems-p9", is_active=True)
    platform_prod = make_product(
        category=cat,
        name="Official DIGI Kit",
        slug="official-digi-kit-p9",
        original_price=Decimal("200.00"),
        is_active=True,
    )

    h_a, cookies_a, seller_a = _apply_and_approve_seller(
        api_client, db, name="Seller Alpha", store_name="Alpha Works", store_slug="alpha-works"
    )
    h_b, cookies_b, seller_b = _apply_and_approve_seller(
        api_client, db, name="Seller Beta", store_name="Beta Forge", store_slug="beta-forge"
    )

    # Seller A creates a draft product; forged seller_id is rejected by StrictRequestModel (422)
    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    assert (
        api_client.post(
            "/api/seller/products",
            json={
                "name": "Spoofed Owner",
                "category_id": str(cat.id),
                "original_price": "100.00",
                "seller_id": seller_b["id"],
            },
            headers=h_a,
        ).status_code
        == 422
    )

    r_create = api_client.post(
        "/api/seller/products",
        json={
            "name": "Alpha Dashboard Kit",
            "slug": "alpha-dashboard-kit",
            "category_id": str(cat.id),
            "original_price": "499.00",
            "short_description": "High-craft dashboard UI",
            "submit_for_review": False,
        },
        headers=h_a,
    )
    assert r_create.status_code == 201
    prod_a_id = r_create.json()["id"]
    assert r_create.json()["approval_status"] == "draft"
    assert r_create.json()["is_active"] is False

    # First-time seller cannot bypass admin review via /status -> publish (400)
    assert (
        api_client.patch(
            f"/api/seller/products/{prod_a_id}/status",
            json={"action": "publish"},
            headers=h_a,
        ).status_code
        == 400
    )

    # Seller A uploads private ZIP asset & submits for admin review
    zip_a = _make_zip_bytes("alpha.txt", b"Alpha Private Source")
    assert (
        api_client.post(
            f"/api/seller/products/{prod_a_id}/asset",
            files={"file": ("alpha-kit.zip", io.BytesIO(zip_a), "application/zip")},
            headers=h_a,
        ).status_code
        == 201
    )
    r_sub = api_client.patch(
        f"/api/seller/products/{prod_a_id}/status",
        json={"action": "submit_for_review"},
        headers=h_a,
    )
    assert r_sub.status_code == 200
    assert r_sub.json()["approval_status"] == "pending_review"

    # Pending product must NEVER appear publicly
    assert api_client.get("/api/products/alpha-dashboard-kit").status_code == 404

    # Cross-seller IDOR checks: Seller B must be rejected (403) on every endpoint targeting Seller A or Platform product
    api_client.cookies.clear()
    api_client.cookies.update(cookies_b)
    for target_id in (prod_a_id, str(platform_prod.id)):
        assert api_client.get(f"/api/seller/products/{target_id}").status_code == 403
        assert (
            api_client.patch(
                f"/api/seller/products/{target_id}",
                json={"name": "Hijacked Name"},
                headers=h_b,
            ).status_code
            == 403
        )
        assert api_client.delete(f"/api/seller/products/{target_id}", headers=h_b).status_code == 403
        assert (
            api_client.patch(
                f"/api/seller/products/{target_id}/status",
                json={"action": "archive"},
                headers=h_b,
            ).status_code
            == 403
        )
        assert (
            api_client.post(
                f"/api/seller/products/{target_id}/asset",
                files={"file": ("evil.zip", io.BytesIO(zip_a), "application/zip")},
                headers=h_b,
            ).status_code
            == 403
        )

    # Seller B's product list never contains Seller A's product
    assert api_client.get("/api/seller/products").json()["total"] == 0

    # Admin approves Seller A's product -> now visible on catalog & storefront
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    r_mod = api_client.post(
        f"/api/admin/products/{prod_a_id}/moderate",
        json={"action": "approve"},
        headers=admin_headers,
    )
    assert r_mod.status_code == 200
    assert r_mod.json()["approval_status"] == "published"
    assert r_mod.json()["is_active"] is True

    # Storefront & public filtering verification
    api_client.cookies.clear()
    r_pub = api_client.get("/api/products/alpha-dashboard-kit")
    assert r_pub.status_code == 200
    assert r_pub.json()["seller"]["store_slug"] == "alpha-works"
    assert r_pub.json()["is_platform_product"] is False

    r_store = api_client.get("/api/stores/alpha-works")
    assert r_store.status_code == 200
    assert r_store.json()["products"]["total"] == 1

    assert api_client.get("/api/products", params={"owner_type": "platform"}).json()["total"] >= 1
    assert api_client.get("/api/products", params={"seller": "alpha-works"}).json()["total"] == 1


# ===========================================================================
# 3. MIXED-SELLER ORDERS, ATTRIBUTION SNAPSHOTS, RETENTION & REFUNDS
# ===========================================================================


def test_mixed_seller_checkout_isolation_retention_and_refund_safety(
    api_client, db, make_category, make_product
):
    cat = make_category(name="Multi-Vendor Bundles", slug="mv-bundles-p9", is_active=True)

    # 1. Platform official product + private ZIP
    plat_prod = make_product(
        category=cat,
        name="Platform Base Kit",
        slug="platform-base-kit-p9",
        original_price=Decimal("200.00"),
        is_active=True,
    )
    admin_headers = _login_admin(api_client, db)
    plat_zip = _make_zip_bytes("platform.txt", b"Platform Asset")
    assert (
        api_client.post(
            f"/api/admin/products/{plat_prod.id}/asset",
            files={"file": ("platform.zip", io.BytesIO(plat_zip), "application/zip")},
            headers=admin_headers,
        ).status_code
        == 201
    )

    # 2. Seller A & Seller B setup + 1 approved product each with real binaries
    h_a, cookies_a, seller_a = _apply_and_approve_seller(
        api_client, db, name="Creator A", store_name="Studio One", store_slug="studio-one"
    )
    h_b, cookies_b, seller_b = _apply_and_approve_seller(
        api_client, db, name="Creator B", store_name="Studio Two", store_slug="studio-two"
    )

    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    p_a = api_client.post(
        "/api/seller/products",
        json={
            "name": "One Icons Pack",
            "slug": "one-icons-pack",
            "category_id": str(cat.id),
            "original_price": "500.00",
            "submit_for_review": True,
        },
        headers=h_a,
    ).json()
    zip_a = _make_zip_bytes("icons.txt", b"Studio One Icons Binary")
    assert (
        api_client.post(
            f"/api/seller/products/{p_a['id']}/asset",
            files={"file": ("one-icons.zip", io.BytesIO(zip_a), "application/zip")},
            headers=h_a,
        ).status_code
        == 201
    )

    api_client.cookies.clear()
    api_client.cookies.update(cookies_b)
    p_b = api_client.post(
        "/api/seller/products",
        json={
            "name": "Two Handbook PDF",
            "slug": "two-handbook-pdf",
            "category_id": str(cat.id),
            "original_price": "300.00",
            "submit_for_review": True,
        },
        headers=h_b,
    ).json()
    pdf_b = _make_pdf_bytes("Studio Two Handbook")
    assert (
        api_client.post(
            f"/api/seller/products/{p_b['id']}/asset",
            files={"file": ("handbook.pdf", io.BytesIO(pdf_b), "application/pdf")},
            headers=h_b,
        ).status_code
        == 201
    )

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/products/{p_a['id']}/moderate",
            json={"action": "approve"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/api/admin/products/{p_b['id']}/moderate",
            json={"action": "approve"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    # 3. Customer adds all 3 items (Platform + Seller A + Seller B) into single cart -> single checkout
    api_client.cookies.clear()
    cust_headers, cust, cust_cookies = _register_customer(api_client, name="Mixed Cart Buyer")
    for pid in (plat_prod.id, p_a["id"], p_b["id"]):
        assert (
            api_client.post(
                "/api/cart/items",
                json={"product_id": str(pid), "quantity": 1},
                headers=cust_headers,
            ).status_code
            in (200, 201)
        )

    r_chk = api_client.post("/api/checkout", headers=cust_headers)
    assert r_chk.status_code == 201
    chk = r_chk.json()
    assert Decimal(str(chk["total_amount"])) == Decimal("1000.00")

    pay_id = f"pay_mv_{uuid.uuid4().hex[:8]}"
    sig = MockPaymentProvider.sign_payment(chk["payment"]["gateway_order_id"], pay_id)
    r_ver = api_client.post(
        "/api/payments/verify",
        json={
            "order_id": chk["order_id"],
            "gateway_order_id": chk["payment"]["gateway_order_id"],
            "gateway_payment_id": pay_id,
            "gateway_signature": sig,
        },
        headers=cust_headers,
    )
    assert r_ver.status_code == 200
    order_data = r_ver.json()
    assert len(order_data["items"]) == 3
    snapshots = {it["seller_store_name_snapshot"] for it in order_data["items"]}
    assert snapshots == {"DIGI-VERSE Official", "Studio One", "Studio Two"}
    item_a_id = next(it["id"] for it in order_data["items"] if it["product_id"] == p_a["id"])
    item_b_id = next(it["id"] for it in order_data["items"] if it["product_id"] == p_b["id"])

    # Customer downloads Seller A's item once before suspension
    r_dl_a1 = api_client.post(f"/api/downloads/{item_a_id}", headers=cust_headers)
    assert r_dl_a1.status_code == 201
    assert api_client.get(r_dl_a1.json()["download_url"]).content == zip_a

    # 4. Verify Seller A & Seller B order isolation & privacy (no customer PII, no other seller items, no payment secrets)
    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    r_ord_a = api_client.get(f"/api/seller/orders/{chk['order_id']}")
    assert r_ord_a.status_code == 200
    ord_a = r_ord_a.json()
    assert len(ord_a["items"]) == 1
    assert ord_a["items"][0]["product_name_snapshot"] == "One Icons Pack"
    assert Decimal(str(ord_a["seller_items_subtotal"])) == Decimal("500.00")
    assert ord_a["download_fulfilment_status"] == "downloaded"
    assert cust["email"] not in r_ord_a.text
    assert pay_id not in r_ord_a.text
    assert "Platform Base Kit" not in r_ord_a.text
    assert "Two Handbook PDF" not in r_ord_a.text

    r_ov_a = api_client.get("/api/seller/overview").json()
    assert Decimal(str(r_ov_a["gross_product_sales"])) == Decimal("500.00")
    assert "net_payout" not in r_ov_a
    assert "commission" not in r_ov_a

    # Seller A cannot independently refund customer's order (admin-only route -> 403)
    assert (
        api_client.patch(
            f"/api/admin/orders/{chk['order_id']}/status",
            json={"status": "refunded"},
            headers=h_a,
        ).status_code
        == 403
    )

    api_client.cookies.clear()
    api_client.cookies.update(cookies_b)
    r_ord_b = api_client.get(f"/api/seller/orders/{chk['order_id']}")
    assert r_ord_b.status_code == 200
    ord_b = r_ord_b.json()
    assert len(ord_b["items"]) == 1
    assert ord_b["items"][0]["product_name_snapshot"] == "Two Handbook PDF"
    assert Decimal(str(ord_b["seller_items_subtotal"])) == Decimal("300.00")
    assert ord_b["download_fulfilment_status"] == "ready"

    # 5. Requirement 2 & 4: Suspending Seller A & archiving Seller B's product must NOT revoke existing purchases!
    # Also Seller A renames store beforehand to verify historical snapshot immutability.
    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    assert (
        api_client.patch(
            "/api/seller/profile",
            json={"store_name": "Studio One Renamed"},
            headers=h_a,
        ).status_code
        == 200
    )

    api_client.cookies.clear()
    api_client.cookies.update(cookies_b)
    assert (
        api_client.patch(
            f"/api/seller/products/{p_b['id']}/status",
            json={"action": "archive"},
            headers=h_b,
        ).status_code
        == 200
    )

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/sellers/{seller_a['id']}/review",
            json={"action": "suspend", "reason": "Policy review hold"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    # Storefront of suspended Seller A is hidden & seller endpoints blocked
    assert api_client.get("/api/stores/studio-one").status_code == 404
    assert api_client.get("/api/products/one-icons-pack").status_code == 404
    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    assert api_client.get("/api/seller/overview").status_code == 403

    # Existing Customer STILL has full order snapshot ("Studio One") AND can download BOTH Seller A & archived Seller B binaries!
    api_client.cookies.clear()
    api_client.cookies.update(cust_cookies)
    r_cust_ord = api_client.get(f"/api/orders/{chk['order_id']}").json()
    snap_a = next(it for it in r_cust_ord["items"] if it["id"] == item_a_id)
    assert snap_a["seller_store_name_snapshot"] == "Studio One"

    r_dl_a2 = api_client.post(f"/api/downloads/{item_a_id}", headers=cust_headers)
    assert r_dl_a2.status_code == 201
    assert api_client.get(r_dl_a2.json()["download_url"]).content == zip_a

    r_dl_b1 = api_client.post(f"/api/downloads/{item_b_id}", headers=cust_headers)
    assert r_dl_b1.status_code == 201
    assert api_client.get(r_dl_b1.json()["download_url"]).content == pdf_b

    # New buyer CANNOT add suspended Seller A's product to cart (400)
    assert (
        api_client.post(
            "/api/cart/items",
            json={"product_id": str(p_a["id"]), "quantity": 1},
            headers=cust_headers,
        ).status_code
        == 400
    )

    # 6. Refund revokes downloads and removes sales from seller gross analytics upon reinstatement
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.patch(
            f"/api/admin/orders/{chk['order_id']}/status",
            json={"status": "refunded"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/api/admin/sellers/{seller_a['id']}/review",
            json={"action": "reinstate"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    api_client.cookies.clear()
    api_client.cookies.update(cust_cookies)
    assert api_client.post(f"/api/downloads/{item_a_id}", headers=cust_headers).status_code == 403

    api_client.cookies.clear()
    api_client.cookies.update(cookies_a)
    r_ov_after_refund = api_client.get("/api/seller/overview").json()
    assert Decimal(str(r_ov_after_refund["gross_product_sales"])) == Decimal("0.00")


def test_wishlist_visibility_respects_moderation_and_seller_suspension(api_client, db, make_category):
    from app.models.catalog import Product

    cat = make_category(name="Wishlist Vis Cat", slug="wishlist-vis-cat", is_active=True)
    headers_s, cookies_s, seller = _apply_and_approve_seller(
        api_client,
        db,
        name="Vis Seller",
        store_name="Vis Studio",
        store_slug="vis-studio",
    )

    api_client.cookies.clear()
    api_client.cookies.update(cookies_s)
    r_prod = api_client.post(
        "/api/seller/products",
        json={
            "name": "Vis Icon Set",
            "slug": "vis-icon-set",
            "category_id": str(cat.id),
            "original_price": "299.00",
        },
        headers=headers_s,
    )
    assert r_prod.status_code == 201
    prod_id = uuid.UUID(r_prod.json()["id"])

    # Upload private asset, submit for review & approve product so buyer can wishlist it
    vis_zip = _make_zip_bytes("vis-kit.txt", b"Visibility Private Asset")
    assert (
        api_client.post(
            f"/api/seller/products/{prod_id}/asset",
            files={"file": ("vis-kit.zip", io.BytesIO(vis_zip), "application/zip")},
            headers=headers_s,
        ).status_code
        == 201
    )
    assert (
        api_client.patch(
            f"/api/seller/products/{prod_id}/status",
            json={"action": "submit_for_review"},
            headers=headers_s,
        ).status_code
        == 200
    )
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/products/{prod_id}/moderate",
            json={"action": "approve"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    # Buyer wishlists approved product -> is_available True
    api_client.cookies.clear()
    buyer_headers, _, buyer_cookies = _register_customer(api_client, name="Wishlist Buyer")
    r_w_add = api_client.post(f"/api/wishlist/{prod_id}", headers=buyer_headers)
    assert r_w_add.status_code == 201
    assert r_w_add.json()["items"][0]["is_available"] is True

    # Unapprove / set product to pending_review -> wishlist shows is_available False
    prod_row = db.get(Product, prod_id)
    prod_row.approval_status = ProductApprovalStatus.PENDING_REVIEW
    db.flush()
    r_w_unapproved = api_client.get("/api/wishlist")
    assert r_w_unapproved.status_code == 200
    assert r_w_unapproved.json()["items"][0]["is_available"] is False

    # Re-publish product, then suspend seller -> wishlist shows is_available False
    prod_row.approval_status = ProductApprovalStatus.PUBLISHED
    db.flush()
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    assert (
        api_client.post(
            f"/api/admin/sellers/{seller['id']}/review",
            json={"action": "suspend", "reason": "Audit review"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    api_client.cookies.clear()
    api_client.cookies.update(buyer_cookies)
    r_w_suspended = api_client.get("/api/wishlist")
    assert r_w_suspended.status_code == 200
    assert r_w_suspended.json()["items"][0]["is_available"] is False


def test_seller_branding_image_upload_per_customer_rate_limit(api_client):
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    # Unauthenticated upload -> 401
    assert (
        api_client.post(
            "/api/seller/branding-image",
            files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
        ).status_code
        == 401
    )

    h1, _, _ = _register_customer(api_client, name="Brand Uploader 1")
    for _ in range(10):
        r_ok = api_client.post(
            "/api/seller/branding-image",
            files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
            headers=h1,
        )
        assert r_ok.status_code == 200

    r_limited = api_client.post(
        "/api/seller/branding-image",
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
        headers=h1,
    )
    assert r_limited.status_code == 429

    # A second customer retains their own quota
    api_client.cookies.clear()
    h2, _, _ = _register_customer(api_client, name="Brand Uploader 2")
    r_other = api_client.post(
        "/api/seller/branding-image",
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
        headers=h2,
    )
    assert r_other.status_code == 200
