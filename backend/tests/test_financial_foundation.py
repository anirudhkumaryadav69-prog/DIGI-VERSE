import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.models.customer import Customer
from app.models.enums import (
    OrderPaymentStatus,
    OrderStatus,
    PaymentStatus,
    SellerApplicationStatus,
)
from app.models.financial import (
    CommissionConfiguration,
    FinancialLedgerEntry,
    FinancialTransaction,
    SellerCommissionOverride,
)
from app.models.order import Order, OrderItem, Payment
from app.models.seller import SellerProfile
from app.services.financial_service import (
    get_seller_financial_summary,
    post_payment_capture,
    post_refund_reversal,
    snapshot_order_commissions,
)


def _seller(db, make_customer):
    customer = make_customer(full_name="Seller Customer")
    seller = SellerProfile(
        customer_id=customer.id,
        store_name="Test Store",
        store_slug=f"test-store-{uuid.uuid4().hex[:8]}",
        seller_display_name="Test Seller",
        contact_email=f"seller-{uuid.uuid4().hex[:8]}@example.test",
        country="India",
        business_type="individual",
        application_status=SellerApplicationStatus.APPROVED,
    )
    db.add(seller)
    db.flush()
    return seller


def _order_payment(db, make_customer, make_category, make_product, seller=None, amount="499.00"):
    customer = make_customer(full_name="Buyer")
    category = make_category()
    product = make_product(category=category, seller_id=seller.id if seller else None)
    order = Order(
        customer_id=customer.id,
        order_number=f"DV-FIN-{uuid.uuid4().hex[:10]}",
        subtotal_amount=Decimal(amount),
        discount_amount=Decimal("0.00"),
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
        seller_id=seller.id if seller else None,
        seller_store_name_snapshot=seller.store_name if seller else "DIGI-VERSE Official",
        seller_store_slug_snapshot=seller.store_slug if seller else None,
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
        customer_id=customer.id,
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
    return order, item, payment


def test_global_commission_snapshot_and_duplicate_capture(db, make_customer, make_category, make_product):
    seller = _seller(db, make_customer)
    config = db.scalar(select(CommissionConfiguration).where(CommissionConfiguration.singleton_key == "default"))
    config.default_rate = Decimal("10")
    db.flush()

    order, item, payment = _order_payment(
        db, make_customer, make_category, make_product, seller=seller, amount="100.00"
    )
    snapshot_order_commissions(db, order)

    assert item.commission_rate_snapshot == Decimal("10")
    assert item.commission_amount_snapshot == Decimal("10.00")
    assert item.gross_amount_snapshot == Decimal("100.00")
    assert item.net_amount_snapshot == Decimal("90.00")
    assert item.commission_source_snapshot == "global_default"

    tx1 = post_payment_capture(db, order, payment)
    tx2 = post_payment_capture(db, order, payment)
    assert tx1.id == tx2.id
    assert tx1.debit_total == tx1.credit_total == Decimal("100.00")
    count = db.scalar(
        select(func.count(FinancialTransaction.id)).where(
            FinancialTransaction.idempotency_key == f"capture:{payment.id}"
        )
    )
    assert count == 1


def test_seller_override_and_platform_owned(db, make_customer, make_category, make_product):
    seller = _seller(db, make_customer)
    db.add(SellerCommissionOverride(seller_id=seller.id, rate=Decimal("25"), updated_by_admin_id=None))
    db.flush()
    order, item, _ = _order_payment(
        db, make_customer, make_category, make_product, seller=seller, amount="10.05"
    )
    snapshot_order_commissions(db, order)
    assert item.commission_amount_snapshot == Decimal("2.51")
    assert item.net_amount_snapshot == Decimal("7.54")
    assert item.commission_source_snapshot == "seller_override"

    platform_order, platform_item, platform_payment = _order_payment(
        db, make_customer, make_category, make_product, seller=None, amount="49.99"
    )
    snapshot_order_commissions(db, platform_order)
    assert platform_item.commission_amount_snapshot == Decimal("0")
    assert platform_item.net_amount_snapshot == Decimal("49.99")
    assert platform_item.commission_source_snapshot == "platform_owned"
    tx = post_payment_capture(db, platform_order, platform_payment)
    platform_revenue = db.scalars(
        select(FinancialLedgerEntry).where(
            FinancialLedgerEntry.transaction_id == tx.id,
            FinancialLedgerEntry.entry_type == "platform_product_revenue",
        )
    ).all()
    assert sum((x.amount for x in platform_revenue), Decimal("0")) == Decimal("49.99")


def test_mixed_seller_capture_and_partial_refund(db, make_customer, make_category, make_product):
    seller_a = _seller(db, make_customer)
    seller_b = _seller(db, make_customer)
    config = db.scalar(select(CommissionConfiguration).where(CommissionConfiguration.singleton_key == "default"))
    config.default_rate = Decimal("20")

    order, item_a, payment = _order_payment(
        db, make_customer, make_category, make_product, seller=seller_a, amount="80.00"
    )
    category = make_category()
    product_b = make_product(category=category, seller_id=seller_b.id)
    item_b = OrderItem(
        order_id=order.id,
        product_id=product_b.id,
        seller_id=seller_b.id,
        seller_store_name_snapshot=seller_b.store_name,
        seller_store_slug_snapshot=seller_b.store_slug,
        product_name_snapshot=product_b.name,
        original_price_snapshot=Decimal("20.00"),
        purchase_price=Decimal("20.00"),
        quantity=1,
    )
    db.add(item_b)
    db.flush()
    order.items.append(item_b)
    order.total_amount = Decimal("100.00")
    snapshot_order_commissions(db, order)
    tx = post_payment_capture(db, order, payment)
    assert tx.debit_total == tx.credit_total == Decimal("100.00")

    refund, refund_tx = post_refund_reversal(
        db, order, payment, "rfnd_partial_test", Decimal("50.00"), "evt_partial_test"
    )
    assert refund.status == "processed"
    assert refund_tx.debit_total == refund_tx.credit_total == Decimal("50.00")
    reversals = db.scalars(
        select(FinancialLedgerEntry).where(
            FinancialLedgerEntry.refund_record_id == refund.id,
            FinancialLedgerEntry.entry_type == "commission_reversal",
        )
    ).all()
    assert sum((x.amount for x in reversals), Decimal("0")) == Decimal("10.00")

    duplicate_refund, duplicate_tx = post_refund_reversal(
        db, order, payment, "rfnd_partial_test", Decimal("50.00"), "evt_partial_test"
    )
    assert duplicate_refund.status == "processed"
    assert duplicate_tx is not None


def test_full_refund_limit_and_ledger_immutability(db, make_customer, make_category, make_product):
    seller = _seller(db, make_customer)
    order, item, payment = _order_payment(
        db, make_customer, make_category, make_product, seller=seller, amount="123.45"
    )
    snapshot_order_commissions(db, order)
    post_payment_capture(db, order, payment)
    post_refund_reversal(db, order, payment, "rfnd_full_test", Decimal("123.45"), "evt_full_test")

    with pytest.raises(DBAPIError):
        entry = db.scalar(select(FinancialLedgerEntry).limit(1))
        entry.description = "tampered"
        db.flush()

    db.rollback()
    order, item, payment = _order_payment(
        db, make_customer, make_category, make_product, seller=None, amount="10.00"
    )
    snapshot_order_commissions(db, order)
    post_payment_capture(db, order, payment)
    with pytest.raises(Exception):
        post_refund_reversal(db, order, payment, "rfnd_too_large", Decimal("10.01"))


def test_seller_summary_and_cross_seller_isolation(db, make_customer, make_category, make_product):
    seller_a = _seller(db, make_customer)
    seller_b = _seller(db, make_customer)
    config = db.scalar(select(CommissionConfiguration).where(CommissionConfiguration.singleton_key == "default"))
    config.default_rate = Decimal("10")

    order_a, _, payment_a = _order_payment(
        db, make_customer, make_category, make_product, seller=seller_a, amount="100.00"
    )
    snapshot_order_commissions(db, order_a)
    post_payment_capture(db, order_a, payment_a)
    post_refund_reversal(db, order_a, payment_a, "rfnd_summary_test", Decimal("20.00"), "evt_summary_test")

    summary_a = get_seller_financial_summary(db, seller_a)
    summary_b = get_seller_financial_summary(db, seller_b)
    assert summary_a["gross_sales"] == Decimal("80.00")
    assert summary_a["platform_commission"] == Decimal("8.00")
    assert summary_a["net_earnings"] == Decimal("72.00")
    assert summary_a["refunded_amount"] == Decimal("20.00")
    assert summary_a["available_earnings"] == Decimal("72.00")
    assert summary_b["gross_sales"] == Decimal("0")
    assert summary_b["net_earnings"] == Decimal("0")
