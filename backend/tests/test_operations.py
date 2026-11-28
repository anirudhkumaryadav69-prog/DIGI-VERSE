"""Comprehensive automated tests for Phase 5:
- Advanced Admin Dashboard Overview & SQL Analytics (Live PostgreSQL stats, date-range sales trends, best-selling products, top categories, most downloaded products, customer activity)
- Admin Customer Management (Search, filters, order & revenue aggregations, status suspension with immediate active session revocation, reactivation)
- Promotional Banners Management & Public Display (CRUD, active/scheduled date window filtering, display priority ordering)
- Advertisement Videos Management & Public Display (CRUD, display position filtering, active-only public visibility)
- Marketing Automation: Message Templates, Email Campaigns & WhatsApp Campaigns (Template CRUD, channel validation, strict opt-in customer consent enforcement, email dispatch, re-launch protection)
- Store Settings & Audit Logs (Settings CRUD, batch updates, public `store.*` filtering, secret-key & protected-system-key guardrails, audit log pagination & filtering)
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.customer import CustomerActivity
from app.models.enums import (
    ActivityType,
    DownloadStatus,
    OrderPaymentStatus,
    OrderStatus,
    PaymentStatus,
)
from app.models.order import DownloadRecord, Order, OrderItem, Payment
from app.services.admin_auth_service import provision_initial_admin
from app.services.email_service import dev_email_provider


def _csrf(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _register_customer(
    client,
    name: str = "Ananya Verma",
    email_consent: bool = False,
    whatsapp_consent: bool = False,
) -> tuple[dict[str, str], dict]:
    suffix = uuid.uuid4().hex[:8]
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"cust-{suffix}@example.test",
            "phone_number": f"+9197{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
            "email_marketing_consent": email_consent,
            "whatsapp_marketing_consent": whatsapp_consent,
        },
    )
    assert res.status_code == 201
    return _csrf(client), res.json()["customer"]


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


# ===========================================================================
# 1. ADVANCED DASHBOARD OVERVIEW & SQL ANALYTICS
# ===========================================================================


def test_advanced_dashboard_overview_and_sql_analytics(
    api_client, db, make_category, make_product, make_customer
):
    cat = make_category(name="UI Kits", slug="ui-kits", is_active=True)
    prod = make_product(
        category=cat,
        name="Fintech SaaS Dashboard Kit",
        slug="fintech-saas-dashboard-kit",
        original_price=Decimal("2500.00"),
        is_active=True,
    )
    customer = make_customer(email="buyer-analytics@example.test")

    # Seed a paid order, payment, download record, and customer activity
    order = Order(
        order_number=f"DV-ANL-{uuid.uuid4().hex[:6].upper()}",
        customer_id=customer.id,
        subtotal_amount=Decimal("2500.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("2500.00"),
        currency="INR",
        status=OrderStatus.FULFILLED,
        payment_status=OrderPaymentStatus.PAID,
        fulfilled_at=datetime.now(timezone.utc),
    )
    db.add(order)
    db.flush()

    order_item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_name_snapshot=prod.name,
        original_price_snapshot=Decimal("2500.00"),
        purchase_price=Decimal("2500.00"),
        quantity=2,
    )
    db.add(order_item)
    db.flush()

    payment = Payment(
        order_id=order.id,
        customer_id=customer.id,
        gateway_name="razorpay",
        gateway_order_id=f"order_{uuid.uuid4().hex[:10]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:10]}",
        amount=Decimal("5000.00"),
        currency="INR",
        status=PaymentStatus.CAPTURED,
        is_signature_verified=True,
    )
    db.add(payment)

    dl = DownloadRecord(
        customer_id=customer.id,
        order_id=order.id,
        order_item_id=order_item.id,
        product_id=prod.id,
        status=DownloadStatus.COMPLETED,
        ip_address="127.0.0.1",
    )
    db.add(dl)

    act = CustomerActivity(
        customer_id=customer.id,
        activity_type=ActivityType.PRODUCT_VIEW,
        product_id=prod.id,
        category_id=cat.id,
        details={"source": "homepage"},
    )
    db.add(act)
    db.commit()

    admin_headers = _login_admin(api_client, db)

    # 1. Verify Overview Metrics
    r_ov = api_client.get("/api/admin/dashboard/overview", headers=admin_headers)
    assert r_ov.status_code == 200
    metrics = r_ov.json()["metrics"]
    assert metrics["total_customers"] >= 1
    assert metrics["new_customers"] >= 1
    assert metrics["total_products"] >= 1
    assert metrics["total_orders"] >= 1
    assert metrics["total_sales_revenue"] >= 2500.0
    assert metrics["total_captured_revenue"] >= 5000.0
    assert metrics["average_order_value"] >= 2500.0
    assert metrics["total_downloads"] >= 1
    assert "active_promotional_campaigns" in metrics

    # 2. Verify SQL Analytics Endpoint
    r_anl = api_client.get("/api/admin/dashboard/analytics", headers=admin_headers)
    assert r_anl.status_code == 200
    anl = r_anl.json()
    assert len(anl["daily_sales"]) >= 1
    assert len(anl["weekly_sales"]) >= 1
    assert len(anl["monthly_sales"]) >= 1
    assert any(p["product_slug"] == "fintech-saas-dashboard-kit" for p in anl["best_selling_products"])
    assert any(c["category_slug"] == "ui-kits" for c in anl["top_categories"])
    assert any(d["product_slug"] == "fintech-saas-dashboard-kit" for d in anl["most_downloaded_products"])
    assert len(anl["recent_customer_activity"]) >= 1


# ===========================================================================
# 2. ADMIN CUSTOMER MANAGEMENT & SESSION REVOCATION
# ===========================================================================


def test_admin_customer_management_and_suspension_session_revocation(api_client, db):
    cust_headers, cust = _register_customer(api_client, name="Suspended Target User")
    customer_id = cust["id"]

    # Confirm customer is currently authenticated
    assert api_client.get("/api/auth/me").status_code == 200

    # Log in as admin on a separate cookie context or after saving customer cookies
    customer_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)

    # List & search customers
    r_list = api_client.get(
        "/api/admin/customers?search=Suspended%20Target",
        headers=admin_headers,
    )
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1
    assert r_list.json()["items"][0]["id"] == customer_id
    assert r_list.json()["items"][0]["account_status"] == "active"

    # Suspend customer account
    r_susp = api_client.patch(
        f"/api/admin/customers/{customer_id}/status",
        json={"account_status": "suspended"},
        headers=admin_headers,
    )
    assert r_susp.status_code == 200
    assert r_susp.json()["account_status"] == "suspended"

    # Restore customer cookies and confirm active session was immediately revoked
    admin_cookies = dict(api_client.cookies)
    api_client.cookies.clear()
    for k, v in customer_cookies.items():
        api_client.cookies.set(k, v)

    r_me = api_client.get("/api/auth/me")
    assert r_me.status_code in (401, 403)

    # Reactivate customer account as admin
    api_client.cookies.clear()
    for k, v in admin_cookies.items():
        api_client.cookies.set(k, v)
    r_react = api_client.patch(
        f"/api/admin/customers/{customer_id}/status",
        json={"account_status": "active"},
        headers=admin_headers,
    )
    assert r_react.status_code == 200
    assert r_react.json()["account_status"] == "active"


# ===========================================================================
# 3. PROMOTIONAL BANNERS & ADVERTISEMENT VIDEOS
# ===========================================================================


def test_promotional_banners_and_advertisement_videos_lifecycle(api_client, db):
    admin_headers = _login_admin(api_client, db)
    now = datetime.now(timezone.utc)

    # 1. Create active high-priority banner
    r_b1 = api_client.post(
        "/api/admin/banners",
        json={
            "heading": "Mega Creators Week — 50% Off",
            "subtitle": "All 3D Kits, UI Bundles & Notion Templates",
            "promotional_text": "Limited-time annual creator sale",
            "image_url": "https://images.example.test/banners/creators-week.jpg",
            "cta_text": "Explore Deals",
            "cta_destination": "/?sort=popularity",
            "display_priority": 100,
            "starts_at": (now - timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=7)).isoformat(),
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert r_b1.status_code == 201
    b1_id = r_b1.json()["id"]

    # 2. Create expired banner (should not appear in public /api/banners)
    r_b2 = api_client.post(
        "/api/admin/banners",
        json={
            "heading": "Expired Flash Sale",
            "image_url": "https://images.example.test/banners/expired.jpg",
            "display_priority": 50,
            "starts_at": (now - timedelta(days=10)).isoformat(),
            "ends_at": (now - timedelta(days=2)).isoformat(),
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert r_b2.status_code == 201
    b2_id = r_b2.json()["id"]

    # Public banners endpoint returns only active, currently scheduled banner
    r_pub_banners = api_client.get("/api/banners")
    assert r_pub_banners.status_code == 200
    pub_ids = [b["id"] for b in r_pub_banners.json()]
    assert b1_id in pub_ids
    assert b2_id not in pub_ids

    # Update banner & delete expired banner
    r_upd_b = api_client.patch(
        f"/api/admin/banners/{b1_id}",
        json={"heading": "Mega Creators Week — 60% Off"},
        headers=admin_headers,
    )
    assert r_upd_b.status_code == 200
    assert r_upd_b.json()["heading"] == "Mega Creators Week — 60% Off"

    assert api_client.delete(f"/api/admin/banners/{b2_id}", headers=admin_headers).status_code == 200

    # 3. Advertisement Videos CRUD & Public Display
    r_v1 = api_client.post(
        "/api/admin/videos",
        json={
            "title": "DIGI-VERSE 2026 Marketplace Showcase",
            "description": "Tour our instant digital delivery and creator toolkits.",
            "video_url": "https://cdn.example.test/videos/showcase.mp4",
            "thumbnail_url": "https://cdn.example.test/videos/showcase-thumb.jpg",
            "destination_url": "/",
            "display_position": "home_hero",
            "display_priority": 90,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert r_v1.status_code == 201
    v1_id = r_v1.json()["id"]

    r_v2 = api_client.post(
        "/api/admin/videos",
        json={
            "title": "Draft Sidebar Promo",
            "video_url": "https://cdn.example.test/videos/sidebar.mp4",
            "display_position": "sidebar",
            "display_priority": 10,
            "is_active": False,
        },
        headers=admin_headers,
    )
    assert r_v2.status_code == 201
    v2_id = r_v2.json()["id"]

    r_pub_v = api_client.get("/api/videos?position=home_hero")
    assert r_pub_v.status_code == 200
    assert any(v["id"] == v1_id for v in r_pub_v.json())
    assert all(v["id"] != v2_id for v in r_pub_v.json())

    # Update & delete video
    r_upd_v = api_client.patch(
        f"/api/admin/videos/{v1_id}",
        json={"display_priority": 95},
        headers=admin_headers,
    )
    assert r_upd_v.status_code == 200
    assert r_upd_v.json()["display_priority"] == 95
    assert api_client.delete(f"/api/admin/videos/{v2_id}", headers=admin_headers).status_code == 200


# ===========================================================================
# 4. MARKETING AUTOMATION: TEMPLATES, EMAIL & WHATSAPP CAMPAIGNS (CONSENT)
# ===========================================================================


def test_marketing_templates_and_campaign_consent_enforcement(api_client, db):
    dev_email_provider.clear()

    # Register Customer 1 WITH email & WhatsApp marketing consent
    _, cust_consented = _register_customer(
        api_client,
        name="Consented Subscriber",
        email_consent=True,
        whatsapp_consent=True,
    )
    api_client.cookies.clear()

    # Register Customer 2 WITHOUT marketing consent
    _, cust_opted_out = _register_customer(
        api_client,
        name="Opted Out Customer",
        email_consent=False,
        whatsapp_consent=False,
    )
    api_client.cookies.clear()

    admin_headers = _login_admin(api_client, db)

    # 1. Create Email & WhatsApp Templates
    r_tpl_email = api_client.post(
        "/api/admin/templates",
        json={
            "name": "Monthly Creator Digest",
            "channel": "email",
            "subject": "New Digital Assets on DIGI-VERSE!",
            "content": "Hi Creator, check out our newest UI kits and code templates.",
        },
        headers=admin_headers,
    )
    assert r_tpl_email.status_code == 201
    email_tpl_id = r_tpl_email.json()["id"]

    r_tpl_wa = api_client.post(
        "/api/admin/templates",
        json={
            "name": "Flash Drop Alert",
            "channel": "whatsapp",
            "content": "DIGI-VERSE Flash Drop: 40% off all Figma kits today!",
        },
        headers=admin_headers,
    )
    assert r_tpl_wa.status_code == 201
    wa_tpl_id = r_tpl_wa.json()["id"]

    # Update template
    r_tpl_upd = api_client.patch(
        f"/api/admin/templates/{email_tpl_id}",
        json={"subject": "Updated: New Digital Assets on DIGI-VERSE!"},
        headers=admin_headers,
    )
    assert r_tpl_upd.status_code == 200

    # 2. Create & Launch Email Campaign -> Only consented customer must receive it
    r_ec = api_client.post(
        "/api/admin/campaigns/email",
        json={
            "name": "November Product Launch Blast",
            "subject": "Exclusive Launch: Pro Design System 2026",
            "content": "Explore the new Pro Design System on DIGI-VERSE.",
            "template_id": email_tpl_id,
        },
        headers=admin_headers,
    )
    assert r_ec.status_code == 201
    ec_id = r_ec.json()["id"]

    dev_email_provider.clear()
    r_ec_launch = api_client.post(
        f"/api/admin/campaigns/email/{ec_id}/launch",
        headers=admin_headers,
    )
    assert r_ec_launch.status_code == 200
    launch_data = r_ec_launch.json()
    # Provider accepted dispatch; campaign stays in `processing` until webhook confirms delivery
    assert launch_data["status"] == "processing"
    assert launch_data["targeted_recipients"] == 1
    assert launch_data["sent_count"] == 1
    assert launch_data["accepted_count"] == 1

    # Confirm email was sent ONLY to cust_consented and NOT to cust_opted_out
    sent_recipients = [m["email"] for m in dev_email_provider.sent_notifications]
    assert cust_consented["email"] in sent_recipients
    assert cust_opted_out["email"] not in sent_recipients

    # Re-launching a completed campaign is rejected -> 409
    assert (
        api_client.post(f"/api/admin/campaigns/email/{ec_id}/launch", headers=admin_headers).status_code
        == 409
    )

    # 3. Create & Launch WhatsApp Campaign -> Only consented customer must receive it
    r_wc = api_client.post(
        "/api/admin/campaigns/whatsapp",
        json={
            "name": "VIP WhatsApp Flash Alert",
            "content": "40% off all Figma kits today!",
            "approved_template_name": "digiverse_flash_sale_v1",
            "template_id": wa_tpl_id,
        },
        headers=admin_headers,
    )
    assert r_wc.status_code == 201
    wc_id = r_wc.json()["id"]

    r_wc_launch = api_client.post(
        f"/api/admin/campaigns/whatsapp/{wc_id}/launch",
        headers=admin_headers,
    )
    assert r_wc_launch.status_code == 200
    assert r_wc_launch.json()["targeted_recipients"] == 1
    assert r_wc_launch.json()["sent_count"] == 1


# ===========================================================================
# 5. STORE SETTINGS GUARDRAILS & AUDIT LOGS
# ===========================================================================


def test_store_settings_security_guardrails_and_audit_logs(api_client, db):
    admin_headers = _login_admin(api_client, db)

    # 1. Upsert valid public & internal store settings
    r_s1 = api_client.put(
        "/api/admin/settings",
        json={"key": "store.name", "value": "DIGI-VERSE Creator Marketplace"},
        headers=admin_headers,
    )
    assert r_s1.status_code == 200
    assert r_s1.json()["value"] == "DIGI-VERSE Creator Marketplace"

    r_batch = api_client.patch(
        "/api/admin/settings/batch",
        json={
            "settings": {
                "store.contact_email": "support@digiverse.test",
                "store.Announcement_Text": "Instant digital downloads on every order!",
                "checkout.invoice_footer": "Thank you for shopping at DIGI-VERSE.",
            }
        },
        headers=admin_headers,
    )
    assert r_batch.status_code == 200

    # Public settings endpoint returns only `store.*` keys
    r_pub = api_client.get("/api/settings/public")
    assert r_pub.status_code == 200
    pub_settings = r_pub.json()
    assert pub_settings.get("store.name") == "DIGI-VERSE Creator Marketplace"
    assert pub_settings.get("store.contact_email") == "support@digiverse.test"
    assert "checkout.invoice_footer" not in pub_settings
    assert "system.initial_admin_provisioned" not in pub_settings

    # 2. Security guardrails: reject secret-like keys and protected system keys -> 422
    for forbidden_key in (
        "razorpay.api_key",
        "jwt.secret_key",
        "smtp.password",
        "supabase.service_role",
        "system.initial_admin_provisioned",
    ):
        r_bad = api_client.put(
            "/api/admin/settings",
            json={"key": forbidden_key, "value": "should-not-be-allowed"},
            headers=admin_headers,
        )
        assert r_bad.status_code in (400, 422), f"Expected 400/422 for forbidden key {forbidden_key}"

    # 3. Verify Audit Logs endpoint
    r_logs = api_client.get(
        "/api/admin/audit-logs?entity_type=store_setting",
        headers=admin_headers,
    )
    assert r_logs.status_code == 200
    logs_data = r_logs.json()
    assert logs_data["total"] >= 2
    assert any(item["action"] in ("settings.updated", "settings.batch_updated") for item in logs_data["items"])


def test_dashboard_overview_counts_only_active_campaign_statuses(api_client, db):
    from app.models.campaign import EmailCampaign, WhatsAppCampaign
    from app.models.enums import CampaignStatus

    for idx, st in enumerate(CampaignStatus):
        db.add(
            EmailCampaign(
                name=f"Email {st.value} {idx}",
                subject="Sub",
                content="Body",
                status=st,
            )
        )
        db.add(
            WhatsAppCampaign(
                name=f"WA {st.value} {idx}",
                content="Body",
                approved_template_name="tpl_v1",
                status=st,
            )
        )
    db.flush()

    admin_headers = _login_admin(api_client, db)
    r_ov = api_client.get("/api/admin/dashboard/overview", headers=admin_headers)
    assert r_ov.status_code == 200
    # 4 active email (SCHEDULED, QUEUED, SENDING, PROCESSING) + 4 active WA = 8
    assert r_ov.json()["metrics"]["active_promotional_campaigns"] == 8
