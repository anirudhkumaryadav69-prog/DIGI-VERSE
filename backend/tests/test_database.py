"""Database integration tests (run against TEST_DATABASE_URL, all changes rolled back)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import (
    Base,
    CampaignRecipient,
    Customer,
    EmailCampaign,
    Order,
    OrderItem,
    Payment,
    Product,
    Sale,
    WhatsAppCampaign,
    Wishlist,
)
from app.models.enums import MessageChannel, PaymentStatus


def expect_integrity_error(db, *objects):
    """Flush inside a SAVEPOINT so the outer test transaction survives the failure."""
    with pytest.raises((IntegrityError, DBAPIError)):
        with db.begin_nested():
            db.add_all(objects)
            db.flush()


# ---------------------------------------------------------------- connection / schema

def test_database_connection(db):
    assert db.execute(text("SELECT 1")).scalar_one() == 1
    assert "test" in db.execute(text("SELECT current_database()")).scalar_one()


def test_all_tables_created_by_alembic(engine):
    existing = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= existing
    assert "alembic_version" in existing


def test_foreign_keys_present(engine):
    insp = inspect(engine)
    fks = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in insp.get_foreign_keys("orders")}
    assert ("customers", ("customer_id",)) in fks
    pay_fks = {fk["referred_table"] for fk in insp.get_foreign_keys("payments")}
    assert {"orders", "customers"} <= pay_fks


# ---------------------------------------------------------------- creation

def test_admin_creation(db, make_admin):
    admin = make_admin()
    assert admin.id is not None and admin.is_active is True
    assert admin.password_hash.startswith("$2")  # bcrypt hash, never plaintext


def test_customer_creation_defaults(db, make_customer):
    customer = make_customer()
    db.refresh(customer)
    assert customer.account_status.value == "active"
    assert customer.email_marketing_consent is False
    assert customer.whatsapp_marketing_consent is False
    assert customer.created_at is not None


def test_category_and_product_creation(db, make_category, make_product):
    category = make_category()
    product = make_product(category=category)
    db.refresh(category)
    assert product.category.id == category.id
    assert product in category.products


# ---------------------------------------------------------------- relationships

def test_customer_order_relationship(db, make_customer, make_order):
    customer = make_customer()
    o1, o2 = make_order(customer), make_order(customer)
    db.refresh(customer)
    assert {o.id for o in customer.orders} == {o1.id, o2.id}
    assert o1.customer.id == customer.id


def test_order_item_relationship(db, make_customer, make_order, make_product):
    order = make_order(make_customer())
    product = make_product()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name_snapshot=product.name,
        original_price_snapshot=product.original_price,
        purchase_price=Decimal("399.00"),
    )
    db.add(item)
    db.flush()
    db.refresh(order)
    assert order.items == [item]
    assert item.order.id == order.id


def test_payment_order_relationship(db, make_customer, make_order):
    customer = make_customer()
    order = make_order(customer)
    payment = Payment(
        order_id=order.id, customer_id=customer.id, gateway_order_id=f"order_{uuid.uuid4().hex}", amount=order.total_amount
    )
    db.add(payment)
    db.flush()
    db.refresh(order)
    assert order.payments == [payment]
    assert payment.status == PaymentStatus.CREATED


# ---------------------------------------------------------------- constraints

def test_duplicate_customer_email_rejected_case_insensitive(db, make_customer):
    make_customer(email="duplicate.check@example.test")
    dup = Customer(full_name="Other", email="Duplicate.Check@EXAMPLE.test", password_hash="$2b$12$x")
    expect_integrity_error(db, dup)


def test_foreign_key_constraint_enforced(db):
    orphan = Product(name="Orphan", slug="orphan-product", category_id=uuid.uuid4(), original_price=Decimal("1.00"))
    expect_integrity_error(db, orphan)


def test_duplicate_wishlist_entry_rejected(db, make_customer, make_product):
    customer, product = make_customer(), make_product()
    db.add(Wishlist(customer_id=customer.id, product_id=product.id))
    db.flush()
    expect_integrity_error(db, Wishlist(customer_id=customer.id, product_id=product.id))


def test_duplicate_fulfilment_prevented(db, make_customer, make_order):
    customer = make_customer()
    order = make_order(customer)

    def captured(pid):
        return Payment(
            order_id=order.id,
            customer_id=customer.id,
            gateway_order_id=f"order_{uuid.uuid4().hex}",
            gateway_payment_id=pid,
            amount=order.total_amount,
            status=PaymentStatus.CAPTURED,
            is_signature_verified=True,
        )

    db.add(captured("pay_first"))
    db.flush()
    expect_integrity_error(db, captured("pay_second"))  # second capture for the same order


def test_captured_payment_requires_signature_verification(db, make_customer, make_order):
    customer = make_customer()
    order = make_order(customer)
    unverified = Payment(
        order_id=order.id,
        customer_id=customer.id,
        gateway_order_id=f"order_{uuid.uuid4().hex}",
        amount=order.total_amount,
        status=PaymentStatus.CAPTURED,
        is_signature_verified=False,
    )
    expect_integrity_error(db, unverified)


def test_sale_discount_must_be_below_original(db, make_product):
    product = make_product()
    now = datetime.now(timezone.utc)
    bad = Sale(
        product_id=product.id,
        original_price_snapshot=Decimal("100.00"),
        discounted_price=Decimal("150.00"),
        starts_at=now,
        expires_at=now + timedelta(days=1),
    )
    expect_integrity_error(db, bad)


def test_customer_with_orders_cannot_be_deleted(db, make_customer, make_order):
    customer = make_customer()
    make_order(customer)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer.id})


# ---------------------------------------------------------------- consent enforcement

def test_campaign_recipient_requires_email_consent(db, make_customer):
    no_consent = make_customer()
    consented = make_customer(email_marketing_consent=True)
    campaign = EmailCampaign(name="Consent check", subject="Subject", content="Body")
    db.add(campaign)
    db.flush()

    expect_integrity_error(
        db, CampaignRecipient(channel=MessageChannel.EMAIL, email_campaign_id=campaign.id, customer_id=no_consent.id)
    )
    ok = CampaignRecipient(channel=MessageChannel.EMAIL, email_campaign_id=campaign.id, customer_id=consented.id)
    db.add(ok)
    db.flush()
    assert ok.id is not None


def test_campaign_recipient_requires_whatsapp_consent(db, make_customer):
    email_only = make_customer(email_marketing_consent=True, phone_number="+919800000001")
    campaign = WhatsAppCampaign(name="WA check", content="Body", approved_template_name="tpl")
    db.add(campaign)
    db.flush()
    expect_integrity_error(
        db,
        CampaignRecipient(channel=MessageChannel.WHATSAPP, whatsapp_campaign_id=campaign.id, customer_id=email_only.id),
    )


def test_whatsapp_consent_requires_phone_number(db):
    bad = Customer(full_name="No Phone", email="nophone@example.test", password_hash="$2b$12$x", whatsapp_marketing_consent=True)
    expect_integrity_error(db, bad)


# ---------------------------------------------------------------- transactions

def test_transaction_rollback(db, make_category):
    category = make_category()
    savepoint = db.begin_nested()
    order_less_customer = Customer(full_name="Rollback", email="rollback@example.test", password_hash="$2b$12$x")
    db.add(order_less_customer)
    db.flush()
    assert db.scalar(select(Customer).where(Customer.email == "rollback@example.test")) is not None
    savepoint.rollback()
    assert db.scalar(select(Customer).where(Customer.email == "rollback@example.test")) is None
    # Work done before the savepoint is untouched.
    assert db.get(type(category), category.id) is not None


def test_order_delete_cascades_to_items(db, make_customer, make_order, make_product):
    order = make_order(make_customer())
    product = make_product()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            original_price_snapshot=product.original_price,
            purchase_price=product.original_price,
        )
    )
    db.flush()
    db.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order.id})
    remaining = db.execute(text("SELECT count(*) FROM order_items WHERE order_id = :id"), {"id": order.id}).scalar_one()
    assert remaining == 0
    assert db.get(Order, order.id, populate_existing=True) is None
