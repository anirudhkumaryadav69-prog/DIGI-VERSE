import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.catalog import Category, Product
from app.models.enums import (
    OrderPaymentStatus,
    OrderStatus,
    PaymentStatus,
)
from app.models.financial import CommissionConfiguration
from app.models.order import Order, OrderItem, Payment
from app.models.seller import SellerProfile
from app.services.admin_auth_service import provision_initial_admin
from app.services.financial_service import post_payment_capture, snapshot_order_commissions


def _csrf(client):
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _login_admin(client, db):
    initial = "AdminInitial#2026!"
    active = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=initial)
    response = client.post(
        "/api/admin/auth/login",
        json={"username": "Aayan", "password": initial},
    )
    if response.status_code == 401:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "Aayan", "password": active},
        )
    assert response.status_code == 200
    if response.json()["must_change_password"]:
        response = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": initial, "new_password": active},
            headers=_csrf(client),
        )
        assert response.status_code == 200
    return _csrf(client)


def _register_customer(client, name):
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"{suffix}@example.test",
            "phone_number": f"+9197{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert response.status_code == 201
    return response.json()["customer"]


def _approve_seller(client, db, name, store_name, store_slug):
    client.cookies.clear()
    customer = _register_customer(client, name)
    headers = _csrf(client)
    application = client.post(
        "/api/seller/application",
        json={
            "store_name": store_name,
            "store_slug": store_slug,
            "seller_display_name": name,
            "application_description": "A verified digital products seller.",
            "contact_email": customer["email"],
            "country": "India",
            "business_type": "Independent",
            "product_categories": ["Digital"],
        },
        headers=headers,
    )
    assert application.status_code == 201
    seller_id = application.json()["id"]
    customer_cookies = dict(client.cookies)

    client.cookies.clear()
    admin_headers = _login_admin(client, db)
    review = client.post(
        f"/api/admin/sellers/{seller_id}/review",
        json={"action": "approve"},
        headers=admin_headers,
    )
    assert review.status_code == 200
    client.cookies.clear()
    client.cookies.update(customer_cookies)
    seller = db.get(SellerProfile, seller_id)
    return seller, _csrf(client), customer


def _post_capture(db, make_category, make_product, customer, seller, amount):
    category = make_category()
    product = make_product(category=category, seller_id=seller.id)
    order = Order(
        customer_id=uuid.UUID(customer["id"]) if isinstance(customer, dict) else customer.id,
        order_number=f"DV-API-{uuid.uuid4().hex[:10]}",
        subtotal_amount=Decimal(amount),
        discount_amount=Decimal("0"),
        total_amount=Decimal(amount),
        currency="INR",
        status=OrderStatus.FULFILLED,
        payment_status=OrderPaymentStatus.PAID,
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        seller_id=seller.id,
        seller_store_name_snapshot=seller.store_name,
        seller_store_slug_snapshot=seller.store_slug,
        product_name_snapshot=product.name,
        original_price_snapshot=Decimal(amount),
        purchase_price=Decimal(amount),
        quantity=1,
    )
    db.add(item)
    db.flush()
    order.items = [item]
    payment = Payment(
        order_id=order.id,
        customer_id=order.customer_id,
        gateway_name="mock",
        gateway_order_id=f"mock_order_{uuid.uuid4().hex}",
        gateway_payment_id=f"mock_pay_{uuid.uuid4().hex}",
        amount=Decimal(amount),
        currency="INR",
        status=PaymentStatus.CAPTURED,
        is_signature_verified=True,
    )
    db.add(payment)
    db.flush()
    snapshot_order_commissions(db, order)
    post_payment_capture(db, order, payment)
    db.flush()
    return order, item, payment


def test_seller_financial_authorization_isolation_and_pagination(api_client, db, make_category, make_product):
    seller_a, headers_a, customer_a = _approve_seller(
        api_client, db, "Seller A", "Seller Alpha", "seller-alpha"
    )
    order_a, _, _ = _post_capture(
        db, make_category, make_product, customer_a, seller_a, "100.00"
    )

    summary = api_client.get("/api/seller/financial/summary", headers=headers_a)
    assert summary.status_code == 200
    assert Decimal(summary.json()["gross_sales"]) == Decimal("100.00")
    assert Decimal(summary.json()["net_earnings"]) == Decimal("100.00")

    transactions = api_client.get(
        "/api/seller/financial/transactions?page=1&page_size=10",
        headers=headers_a,
    )
    assert transactions.status_code == 200
    assert transactions.json()["total"] >= 1
    assert transactions.json()["items"][0]["order_id"] == str(order_a.id)

    orders = api_client.get(
        "/api/seller/financial/orders?page=1&page_size=10",
        headers=headers_a,
    )
    assert orders.status_code == 200
    assert orders.json()["items"][0]["order_id"] == str(order_a.id)

    items = api_client.get(
        "/api/seller/financial/order-items?page=1&page_size=10",
        headers=headers_a,
    )
    assert items.status_code == 200
    assert items.json()["items"][0]["commission_source"] == "global_default"

    seller_b, headers_b, customer_b = _approve_seller(
        api_client, db, "Seller B", "Seller Beta", "seller-beta"
    )
    seller_b_summary = api_client.get("/api/seller/financial/summary", headers=headers_b)
    assert seller_b_summary.status_code == 200
    assert Decimal(seller_b_summary.json()["gross_sales"]) == Decimal("0")

    api_client.cookies.clear()
    unauthorized = api_client.get("/api/seller/financial/summary")
    assert unauthorized.status_code == 401


def test_admin_commission_config_override_audit_and_ledger(api_client, db):
    admin_headers = _login_admin(api_client, db)
    global_config = api_client.get("/api/admin/financial/commission", headers=admin_headers)
    assert global_config.status_code == 200

    update = api_client.put(
        "/api/admin/financial/commission",
        json={"default_rate": "12.500000", "reason": "Stage 2 test"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert Decimal(update.json()["default_rate"]) == Decimal("12.500000")

    invalid = api_client.put(
        "/api/admin/financial/commission",
        json={"default_rate": "-1"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    seller, _, _ = _approve_seller(
        api_client, db, "Commission Seller", "Commission Store", "commission-store"
    )
    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    set_override = api_client.put(
        f"/api/admin/financial/sellers/{seller.id}/commission",
        json={"rate": "7.250000", "reason": "Creator launch rate"},
        headers=admin_headers,
    )
    assert set_override.status_code == 200
    assert Decimal(set_override.json()["effective_rate"]) == Decimal("7.250000")

    seller_config = api_client.get(
        f"/api/admin/financial/sellers/{seller.id}/commission",
        headers=admin_headers,
    )
    assert seller_config.status_code == 200
    assert Decimal(seller_config.json()["override_rate"]) == Decimal("7.250000")

    remove = api_client.delete(
        f"/api/admin/financial/sellers/{seller.id}/commission?reason=restore-default",
        headers=admin_headers,
    )
    assert remove.status_code == 200
    removed = api_client.get(
        f"/api/admin/financial/sellers/{seller.id}/commission",
        headers=admin_headers,
    )
    assert Decimal(removed.json()["effective_rate"]) == Decimal("12.500000")

    ledger = api_client.get(
        "/api/admin/financial/ledger?page=1&page_size=20",
        headers=admin_headers,
    )
    assert ledger.status_code == 200
    report = api_client.get(
        "/api/admin/financial/commission/report",
        headers=admin_headers,
    )
    assert report.status_code == 200
    audit_actions = [
        row.action
        for row in db.scalars(
            select(AuditLog).where(AuditLog.action.like("commission.%"))
        ).all()
    ]
    assert "commission.global.update" in audit_actions
    assert "commission.seller.override.set" in audit_actions
    assert "commission.seller.override.remove" in audit_actions


def test_admin_financial_endpoints_reject_customer_token(api_client):
    response = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "Plain Customer",
            "email": f"plain-{uuid.uuid4().hex[:8]}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert response.status_code == 201
    forbidden = api_client.get("/api/admin/financial/commission")
    assert forbidden.status_code == 403
