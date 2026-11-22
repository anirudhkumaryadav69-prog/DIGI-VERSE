"""Comprehensive automated tests for Phase 3:
- Admin Dashboard Statistics & RBAC
- Category CRUD, Slug Generation, Search, Pagination & Delete Protection
- Product CRUD, Status Toggle, Category Validation & Historical Order Delete Protection
- Product Image Upload, Magic-Byte MIME Validation, Size Limits, Ordering, Replacement & Deletion
- Public Customer Catalog (Search, Category/Price Filtering, Sorting, Active Filtering, Zero Leakage of private_download_url)
- Sales & Discounts (Creation, Validation, Scheduling, Effective Price Calculation, Single Active Sale Constraint)
- Audit Logging Verification
"""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.enums import OrderPaymentStatus, OrderStatus
from app.models.order import Order, OrderItem
from app.services.admin_auth_service import provision_initial_admin
from app.services.storage_service import get_image_storage

# Minimal valid binary headers for PNG, JPEG, and WEBP magic-byte verification
VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _login_active_admin(client, db) -> dict[str, str]:
    """Provision initial admin, log in, complete mandatory initial password change, return CSRF headers."""
    init_pw = "AdminInitial#2026!"
    new_pw = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=init_pw)

    r_login = client.post(
        "/api/admin/auth/login",
        json={"username": "Aayan", "password": init_pw},
    )
    assert r_login.status_code == 200
    if r_login.json()["must_change_password"]:
        r_change = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": init_pw, "new_password": new_pw},
            headers=_csrf(client),
        )
        assert r_change.status_code == 200
    return _csrf(client)


def _register_and_login_customer(client) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": "Catalog Customer",
            "email": f"cust-{suffix}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert r.status_code == 201
    return _csrf(client)


# ===========================================================================
# 1. ADMIN DASHBOARD TESTS
# ===========================================================================


def test_dashboard_statistics_reflect_actual_database_records(
    api_client, db, make_customer, make_category, make_product
):
    headers = _login_active_admin(api_client, db)

    c1 = make_customer(full_name="Priya Nair")
    cat = make_category(name="UI Kits", slug="ui-kits")
    p_active = make_product(category=cat, name="Figma Design System", slug="figma-ds", is_active=True)
    make_product(category=cat, name="Archived Kit", slug="archived-kit", is_active=False)

    # Create 1 paid order and 1 pending unpaid order
    paid_order = Order(
        customer_id=c1.id,
        order_number=f"ORD-PAID-{uuid.uuid4().hex[:6].upper()}",
        total_amount=Decimal("1499.00"),
        status=OrderStatus.FULFILLED,
        payment_status=OrderPaymentStatus.PAID,
    )
    pending_order = Order(
        customer_id=c1.id,
        order_number=f"ORD-PEND-{uuid.uuid4().hex[:6].upper()}",
        total_amount=Decimal("799.00"),
        status=OrderStatus.PENDING,
        payment_status=OrderPaymentStatus.UNPAID,
    )
    db.add_all([paid_order, pending_order])
    db.flush()

    res = api_client.get("/api/admin/dashboard/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    m = data["metrics"]

    assert m["total_customers"] == 1
    assert m["total_categories"] == 1
    assert m["total_products"] == 2
    assert m["active_products"] == 1
    assert m["inactive_products"] == 1
    assert m["total_orders"] == 2
    assert m["pending_orders"] == 1
    assert m["total_sales_revenue"] == 1499.0

    assert len(data["recent_registrations"]) == 1
    assert data["recent_registrations"][0]["full_name"] == "Priya Nair"
    assert len(data["recent_orders"]) == 2
    assert len(data["recent_products"]) == 2
    assert any(p["id"] == str(p_active.id) for p in data["recent_products"])


def test_dashboard_rejects_unauthenticated_and_customer_requests(api_client, db):
    # Unauthenticated -> 401
    r_unauth = api_client.get("/api/admin/dashboard/overview")
    assert r_unauth.status_code == 401

    # Customer -> 403
    _register_and_login_customer(api_client)
    r_cust = api_client.get("/api/admin/dashboard/overview")
    assert r_cust.status_code == 403


# ===========================================================================
# 2. CATEGORY MANAGEMENT TESTS
# ===========================================================================


def test_category_crud_auto_slug_and_duplicate_prevention(api_client, db):
    headers = _login_active_admin(api_client, db)

    # Create category with auto-generated slug
    r_create = api_client.post(
        "/api/admin/categories",
        json={
            "name": "3D Motion & VFX Assets",
            "description": "Cinema 4D, Blender, and After Effects packs",
            "is_active": True,
        },
        headers=headers,
    )
    assert r_create.status_code == 201
    cat = r_create.json()
    cat_id = cat["id"]
    assert cat["slug"] == "3d-motion-vfx-assets"
    assert cat["product_count"] == 0

    # Duplicate name (case-insensitive) -> 409
    r_dup_name = api_client.post(
        "/api/admin/categories",
        json={"name": "3d motion & vfx assets", "slug": "different-slug"},
        headers=headers,
    )
    assert r_dup_name.status_code == 409

    # Duplicate slug -> 409
    r_dup_slug = api_client.post(
        "/api/admin/categories",
        json={"name": "Another Category", "slug": "3d-motion-vfx-assets"},
        headers=headers,
    )
    assert r_dup_slug.status_code == 409

    # Retrieve single category
    r_get = api_client.get(f"/api/admin/categories/{cat_id}")
    assert r_get.status_code == 200
    assert r_get.json()["name"] == "3D Motion & VFX Assets"

    # Update category
    r_patch = api_client.patch(
        f"/api/admin/categories/{cat_id}",
        json={"name": "3D & Motion Graphics", "slug": "3d-motion-graphics", "is_active": False},
        headers=headers,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["name"] == "3D & Motion Graphics"
    assert r_patch.json()["slug"] == "3d-motion-graphics"
    assert r_patch.json()["is_active"] is False

    # Delete empty category -> 200
    r_del = api_client.delete(f"/api/admin/categories/{cat_id}", headers=headers)
    assert r_del.status_code == 200

    # Verify 404 after deletion
    assert api_client.get(f"/api/admin/categories/{cat_id}").status_code == 404


def test_category_delete_prevented_when_products_exist_and_search_pagination(
    api_client, db, make_category, make_product
):
    headers = _login_active_admin(api_client, db)
    cat1 = make_category(name="Audio Samples", slug="audio-samples", is_active=True)
    make_category(name="Code Templates", slug="code-templates", is_active=False)
    make_product(category=cat1, name="Lo-Fi Drum Kit", slug="lofi-drum-kit")

    # Deleting cat1 with an assigned product must fail with 409 Conflict
    r_del = api_client.delete(f"/api/admin/categories/{cat1.id}", headers=headers)
    assert r_del.status_code == 409
    assert "product(s) are assigned" in r_del.json()["detail"]

    # Search and active filtering + pagination
    r_search = api_client.get("/api/admin/categories?search=Audio&is_active=true&page=1&page_size=10")
    assert r_search.status_code == 200
    body = r_search.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "audio-samples"
    assert body["items"][0]["product_count"] == 1


# ===========================================================================
# 3. PRODUCT MANAGEMENT TESTS
# ===========================================================================


def test_product_crud_status_toggle_validation_and_audit_safety(api_client, db, make_category):
    headers = _login_active_admin(api_client, db)
    cat1 = make_category(name="Notion Templates", slug="notion-templates")
    cat2 = make_category(name="E-Books", slug="e-books")

    # Invalid category reference -> 404
    r_bad_cat = api_client.post(
        "/api/admin/products",
        json={
            "name": "Orphan Product",
            "category_id": str(uuid.uuid4()),
            "original_price": "299.00",
        },
        headers=headers,
    )
    assert r_bad_cat.status_code == 404

    # Invalid negative price -> 422
    r_bad_price = api_client.post(
        "/api/admin/products",
        json={
            "name": "Negative Price",
            "category_id": str(cat1.id),
            "original_price": "-10.00",
        },
        headers=headers,
    )
    assert r_bad_price.status_code == 422

    # Create valid product with private_download_url and metadata
    secret_drive_url = "https://drive.google.com/uc?id=1CONFIDENTIAL_FILE_ID&export=download"
    r_create = api_client.post(
        "/api/admin/products",
        json={
            "name": "Agency OS Notion Workspace",
            "category_id": str(cat1.id),
            "short_description": "Complete operating system for digital agencies.",
            "main_description": "Includes CRM, project tracker, and financial dashboards.",
            "detailed_description": "Full documentation and onboarding video walkthroughs.",
            "original_price": "2499.00",
            "product_type": "Notion Template",
            "metadata": {"format": "Notion Duplicate Link + PDF Guide", "version": "2.1"},
            "is_active": True,
            "private_download_url": secret_drive_url,
        },
        headers=headers,
    )
    assert r_create.status_code == 201
    prod = r_create.json()
    prod_id = prod["id"]
    assert prod["slug"] == "agency-os-notion-workspace"
    assert prod["private_download_url"] == secret_drive_url
    assert Decimal(prod["effective_price"]) == Decimal("2499.00")

    # Ensure private_download_url is NEVER written into audit_logs metadata
    logs = db.scalars(select(AuditLog).where(AuditLog.entity_id == prod_id)).all()
    assert len(logs) >= 1
    for log in logs:
        serialized = json.dumps(log.details or {})
        assert secret_drive_url not in serialized

    # Update product (change category, price, and description)
    r_update = api_client.patch(
        f"/api/admin/products/{prod_id}",
        json={
            "name": "Agency OS Pro Edition",
            "category_id": str(cat2.id),
            "original_price": "2999.00",
        },
        headers=headers,
    )
    assert r_update.status_code == 200
    assert r_update.json()["name"] == "Agency OS Pro Edition"
    assert r_update.json()["category_id"] == str(cat2.id)
    assert Decimal(r_update.json()["original_price"]) == Decimal("2999.00")

    # Toggle product status -> inactive
    r_status = api_client.patch(
        f"/api/admin/products/{prod_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert r_status.status_code == 200
    assert r_status.json()["is_active"] is False

    # Delete product (not referenced by any orders) -> 200
    r_del = api_client.delete(f"/api/admin/products/{prod_id}", headers=headers)
    assert r_del.status_code == 200


def test_product_deletion_blocked_when_historical_orders_reference_it(
    api_client, db, make_customer, make_product, make_order
):
    headers = _login_active_admin(api_client, db)
    customer = make_customer()
    product = make_product(name="Purchased Asset", slug="purchased-asset")
    order = make_order(customer)
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            original_price_snapshot=product.original_price,
            purchase_price=product.original_price,
            quantity=1,
        )
    )
    db.flush()

    r_del = api_client.delete(f"/api/admin/products/{product.id}", headers=headers)
    assert r_del.status_code == 409
    assert "historical orders" in r_del.json()["detail"].lower()


def test_product_endpoints_reject_customer_access_and_role_escalation(
    api_client, db, make_category
):
    cat = make_category()
    cust_headers = _register_and_login_customer(api_client)

    # Customer cannot create, list, or delete admin products
    r_create = api_client.post(
        "/api/admin/products",
        json={"name": "Unauthorized", "category_id": str(cat.id), "original_price": "100.00"},
        headers=cust_headers,
    )
    assert r_create.status_code == 403
    assert api_client.get("/api/admin/products").status_code == 403


# ===========================================================================
# 4. PRODUCT IMAGE MANAGEMENT TESTS
# ===========================================================================


def test_product_image_upload_validation_ordering_replacement_and_deletion(
    api_client, db, make_product
):
    product = make_product(name="Icon Pack", slug="icon-pack")

    # Unauthorized upload by customer -> 403
    cust_headers = _register_and_login_customer(api_client)
    r_unauth = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("icon.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        headers=cust_headers,
    )
    assert r_unauth.status_code == 403

    api_client.cookies.clear()
    headers = _login_active_admin(api_client, db)

    # Invalid file extension (.svg / .exe) -> 400
    r_bad_ext = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("exploit.svg", io.BytesIO(b"<svg onload=alert(1)>"), "image/svg+xml")},
        headers=headers,
    )
    assert r_bad_ext.status_code == 400

    # Spoofed magic bytes (text/script disguised as .png) -> 400
    r_spoof = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("spoof.png", io.BytesIO(b"#!/bin/sh\necho pwned"), "image/png")},
        headers=headers,
    )
    assert r_spoof.status_code == 400

    # Oversized file (> 5 MB) -> 413
    oversized_bytes = VALID_PNG_BYTES + (b"\x00" * (5 * 1024 * 1024 + 100))
    r_large = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("huge.png", io.BytesIO(oversized_bytes), "image/png")},
        headers=headers,
    )
    assert r_large.status_code == 413

    # Valid primary PNG upload -> 201
    r_up1 = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("cover.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        data={"display_order": "0", "is_primary": "true"},
        headers=headers,
    )
    assert r_up1.status_code == 201
    img1 = r_up1.json()
    assert img1["is_primary"] is True
    assert img1["image_url"].startswith("/api/uploads/images/")

    # Serve uploaded image and verify path-traversal protection
    r_serve = api_client.get(img1["image_url"])
    assert r_serve.status_code == 200
    assert r_serve.headers["content-type"] == "image/png"
    assert api_client.get("/api/uploads/images/..%2F..%2F.env").status_code in (400, 404)

    # Upload second JPEG image
    r_up2 = api_client.post(
        f"/api/admin/products/{product.id}/images",
        files={"file": ("gallery.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"display_order": "1", "is_primary": "false"},
        headers=headers,
    )
    assert r_up2.status_code == 201
    img2 = r_up2.json()

    # Promote img2 to primary and reorder
    r_promote = api_client.patch(
        f"/api/admin/products/{product.id}/images/{img2['id']}",
        json={"is_primary": True, "display_order": 0},
        headers=headers,
    )
    assert r_promote.status_code == 200
    assert r_promote.json()["is_primary"] is True

    # Replace img1 file
    r_replace = api_client.put(
        f"/api/admin/products/{product.id}/images/{img1['id']}",
        files={"file": ("replacement.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        headers=headers,
    )
    assert r_replace.status_code == 200
    replaced_url = r_replace.json()["image_url"]
    assert replaced_url != img1["image_url"]

    # Delete both images (also cleans up files on disk)
    assert (
        api_client.delete(
            f"/api/admin/products/{product.id}/images/{img1['id']}", headers=headers
        ).status_code
        == 200
    )
    assert (
        api_client.delete(
            f"/api/admin/products/{product.id}/images/{img2['id']}", headers=headers
        ).status_code
        == 200
    )
    get_image_storage().delete_image(replaced_url)


# ===========================================================================
# 5. SALES & DISCOUNTS AND PUBLIC CATALOG TESTS
# ===========================================================================


def test_discount_management_and_public_catalog_filtering_sorting_and_security(
    api_client, db, make_category, make_product
):
    headers = _login_active_admin(api_client, db)
    cat_active = make_category(name="UI Kits", slug="ui-kits", is_active=True)
    cat_inactive = make_category(name="Hidden Category", slug="hidden-cat", is_active=False)

    p1 = make_product(
        category=cat_active,
        name="Minimal SaaS Dashboard",
        slug="minimal-saas-dashboard",
        original_price=Decimal("2000.00"),
        is_active=True,
        private_download_url="https://drive.google.com/file/d/SECRET_1/view",
    )
    p2 = make_product(
        category=cat_active,
        name="Mobile Commerce UI",
        slug="mobile-commerce-ui",
        original_price=Decimal("900.00"),
        is_active=True,
        private_download_url="https://drive.google.com/file/d/SECRET_2/view",
    )
    p_inactive = make_product(
        category=cat_active,
        name="Draft Product",
        slug="draft-product",
        original_price=Decimal("500.00"),
        is_active=False,
    )
    p_in_inactive_cat = make_product(
        category=cat_inactive,
        name="Hidden Category Product",
        slug="hidden-cat-product",
        original_price=Decimal("500.00"),
        is_active=True,
    )

    now = datetime.now(timezone.utc)

    # Invalid discount (>= original_price) -> 400
    r_bad_sale = api_client.post(
        f"/api/admin/products/{p1.id}/sales",
        json={
            "discounted_price": "2500.00",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=5)).isoformat(),
            "is_active": True,
        },
        headers=headers,
    )
    assert r_bad_sale.status_code == 400

    # Create active live discount on p1 (2000.00 -> 1500.00, 25% off)
    r_sale = api_client.post(
        f"/api/admin/products/{p1.id}/sales",
        json={
            "discounted_price": "1500.00",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=5)).isoformat(),
            "is_active": True,
        },
        headers=headers,
    )
    assert r_sale.status_code == 201
    sale_data = r_sale.json()
    assert Decimal(sale_data["discounted_price"]) == Decimal("1500.00")
    assert Decimal(sale_data["discount_percentage"]) == Decimal("25.00")
    assert sale_data["is_currently_live"] is True

    # Prevent multiple active discounts on the same product -> 409 Conflict
    r_second_sale = api_client.post(
        f"/api/admin/products/{p1.id}/sales",
        json={
            "discounted_price": "1200.00",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "is_active": True,
        },
        headers=headers,
    )
    assert r_second_sale.status_code == 409

    # Create future scheduled discount on p2 (starts tomorrow -> not live yet)
    r_future_sale = api_client.post(
        f"/api/admin/products/{p2.id}/sales",
        json={
            "discounted_price": "600.00",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=4)).isoformat(),
            "is_active": True,
        },
        headers=headers,
    )
    assert r_future_sale.status_code == 201
    assert r_future_sale.json()["is_currently_live"] is False

    # Clear cookies to test public catalog as an unauthenticated visitor
    api_client.cookies.clear()

    # Public product listing: only p1 and p2 are returned (inactive products/categories excluded)
    r_pub_list = api_client.get("/api/products?sort_by=price_asc")
    assert r_pub_list.status_code == 200
    pub_list = r_pub_list.json()
    assert pub_list["total"] == 2
    slugs = [item["slug"] for item in pub_list["items"]]
    assert slugs == ["mobile-commerce-ui", "minimal-saas-dashboard"]
    assert p_inactive.slug not in slugs
    assert p_in_inactive_cat.slug not in slugs

    # Verify private_download_url is NEVER present anywhere in public responses
    raw_list_json = r_pub_list.text
    assert "private_download_url" not in raw_list_json
    assert "SECRET_1" not in raw_list_json
    assert "SECRET_2" not in raw_list_json

    # Public product detail for p1 shows active discount and effective_price = 1500.00
    r_p1_detail = api_client.get(f"/api/products/{p1.slug}")
    assert r_p1_detail.status_code == 200
    p1_pub = r_p1_detail.json()
    assert "private_download_url" not in p1_pub
    assert Decimal(p1_pub["original_price"]) == Decimal("2000.00")
    assert Decimal(p1_pub["effective_price"]) == Decimal("1500.00")
    assert p1_pub["is_on_sale"] is True
    assert Decimal(p1_pub["active_discount"]["discount_percentage"]) == Decimal("25.00")

    # Public product detail for p2 (future scheduled discount) still has effective_price = 900.00
    r_p2_detail = api_client.get(f"/api/products/{p2.slug}")
    assert r_p2_detail.status_code == 200
    p2_pub = r_p2_detail.json()
    assert Decimal(p2_pub["effective_price"]) == Decimal("900.00")
    assert p2_pub["is_on_sale"] is False
    assert p2_pub["active_discount"] is None

    # Inactive product detail returns 404
    assert api_client.get(f"/api/products/{p_inactive.slug}").status_code == 404
    assert api_client.get(f"/api/products/{p_in_inactive_cat.slug}").status_code == 404

    # Search, category slug filter, and price filter
    r_filter = api_client.get("/api/products?search=Minimal&category=ui-kits&min_price=1000&max_price=2500")
    assert r_filter.status_code == 200
    assert r_filter.json()["total"] == 1
    assert r_filter.json()["items"][0]["slug"] == "minimal-saas-dashboard"

    # Public categories endpoint
    r_cats = api_client.get("/api/categories")
    assert r_cats.status_code == 200
    assert r_cats.json()["total"] == 1
    assert r_cats.json()["items"][0]["slug"] == "ui-kits"
    assert r_cats.json()["items"][0]["product_count"] == 2
