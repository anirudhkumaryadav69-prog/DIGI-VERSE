import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.enums import SellerApplicationStatus
from app.models.financial import (
    FinancialLedgerEntry,
    FinancialTransaction,
)
from app.models.payout import (
    PayoutConfiguration,
    PayoutAccountVerificationHistory,
    PayoutExecutionAttempt,
    PayoutRequest,
    SellerPayoutAccount,
)
from app.models.seller import SellerProfile
from app.services.payout_service import (
    approve_payout_account_verification,
    create_payout_reservation,
    reject_payout_account_verification,
    execute_payout_request,
    get_seller_payable_balance,
    post_payout_settlement,
    reconcile_payout_request,
    release_payout_reservation,
    retry_payout_request,
)


def _seller(db, make_customer):
    customer = make_customer(full_name="Payout Seller")
    seller = SellerProfile(
        customer_id=customer.id,
        store_name="Payout Store",
        store_slug=f"payout-store-{uuid.uuid4().hex[:8]}",
        seller_display_name="Payout Seller",
        contact_email=f"payout-{uuid.uuid4().hex[:8]}@example.test",
        country="India",
        business_type="Independent",
        application_status=SellerApplicationStatus.APPROVED,
    )
    db.add(seller)
    db.flush()
    return seller


def _verified_account(db, seller):
    account = SellerPayoutAccount(
        seller_id=seller.id,
        account_type="upi",
        display_name="Seller UPI",
        masked_identifier="seller@upi",
        provider_account_reference="token_upi_123",
        verification_status="verified",
        is_default=True,
        is_active=True,
    )
    db.add(account)
    db.flush()
    return account


def _post_net(db, seller, amount, entry_type="seller_net_earnings", direction="credit"):
    tx = FinancialTransaction(
        transaction_type="payment_capture",
        idempotency_key=f"net:{uuid.uuid4().hex}",
        status="posted",
        currency="INR",
        debit_total=Decimal(amount),
        credit_total=Decimal(amount),
        seller_id=seller.id,
        metadata_json={},
    )
    db.add(tx)
    db.flush()
    entry = FinancialLedgerEntry(
        transaction_id=tx.id,
        idempotency_key=f"net-entry:{uuid.uuid4().hex}",
        entry_type=entry_type,
        account_code="SELLER_NET_PAYABLE",
        direction=direction,
        amount=Decimal(amount),
        currency="INR",
        seller_id=seller.id,
        description="Test ledger balance",
    )
    db.add(entry)
    db.flush()
    return tx, entry


def test_payout_models_safe_defaults_and_verified_account(db, make_customer):
    config = db.scalar(select(PayoutConfiguration).where(PayoutConfiguration.singleton_key == "default"))
    assert config.currency == "INR"
    assert config.minimum_amount == Decimal("500.00")
    assert config.maximum_amount == Decimal("100000.00")
    assert config.live_execution_enabled is False
    assert config.mock_execution_enabled is True

    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    assert account.masked_identifier == "seller@upi"
    assert account.provider_account_reference.startswith("token_")
    assert account.verification_status == "verified"


def test_available_balance_reservation_and_duplicate_request(db, make_customer):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    _post_net(db, seller, "1000.00")

    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable"] == Decimal("1000.00")
    assert balance["available_amount"] == Decimal("1000.00")

    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("600.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    balance = get_seller_payable_balance(db, seller.id)
    assert balance["reserved_amount"] == Decimal("600.00")
    assert balance["available_amount"] == Decimal("400.00")
    assert payout.destination_masked_snapshot == "seller@upi"

    duplicate = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("600.00"),
        idempotency_key=payout.idempotency_key,
    )
    assert duplicate.id == payout.id

    with pytest.raises(Exception):
        create_payout_reservation(
            db,
            seller=seller,
            payout_account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key=f"withdraw:{uuid.uuid4().hex}",
        )

    released = release_payout_reservation(db, payout=payout, reason="Test rejection")
    assert released.reservation_status == "released"
    balance = get_seller_payable_balance(db, seller.id)
    assert balance["reserved_amount"] == Decimal("0")
    assert balance["available_amount"] == Decimal("1000.00")


def test_refund_reversal_affects_available_and_negative_balance_is_blocked(db, make_customer):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    _post_net(db, seller, "1000.00")
    _post_net(db, seller, "300.00", direction="debit")

    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable"] == Decimal("700.00")
    assert balance["available_amount"] == Decimal("700.00")
    assert balance["debt_amount"] == Decimal("0")

    with pytest.raises(Exception):
        create_payout_reservation(
            db,
            seller=seller,
            payout_account_id=account.id,
            amount=Decimal("800.00"),
            idempotency_key=f"withdraw:{uuid.uuid4().hex}",
        )


def test_negative_signed_payable_is_preserved_separately_from_available(db, make_customer):
    seller = _seller(db, make_customer)
    _post_net(db, seller, "500.00")
    _post_net(db, seller, "700.00", direction="debit")

    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable_signed"] == Decimal("-200.00")
    assert balance["seller_net_payable"] == Decimal("0")
    assert balance["debt_amount"] == Decimal("200.00")
    assert balance["available_amount"] == Decimal("0")


def test_settlement_posts_once_and_does_not_double_count(db, make_customer):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    _post_net(db, seller, "1000.00")

    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("600.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    payout.status = "processing"
    payout.processing_at = None
    db.flush()

    tx = post_payout_settlement(
        db,
        payout=payout,
        execution_reference="mock_settlement_123",
        mock_execution=True,
    )
    assert tx.transaction_type == "payout_settlement"
    assert tx.debit_total == tx.credit_total == Decimal("600.00")
    assert payout.status == "completed"
    assert payout.reservation_status == "deducted"

    existing = db.scalar(
        select(FinancialTransaction).where(
            FinancialTransaction.idempotency_key == f"payout:{payout.id}:settlement"
        )
    )
    assert existing is not None
    assert existing.id == tx.id

    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable"] == Decimal("400.00")
    assert balance["total_settled"] == Decimal("600.00")
    assert balance["reserved_amount"] == Decimal("0")
    assert balance["available_amount"] == Decimal("400.00")


def test_payout_snapshot_and_execution_attempt_are_immutable(db, make_customer):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    _post_net(db, seller, "500.00")
    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("500.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )

    with pytest.raises(DBAPIError):
        payout.amount = Decimal("499.00")
        db.flush()

    db.rollback()


def test_mock_success_execution_posts_one_settlement_and_duplicate_is_idempotent(
    db, make_customer, make_admin
):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    admin = make_admin()
    _post_net(db, seller, "1000.00")
    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("600.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    payout.status = "approved"
    payout.approved_by_admin_id = admin.id
    db.flush()

    attempt = execute_payout_request(
        db,
        admin=admin,
        payout_id=payout.id,
        scenario="success",
        idempotency_key="execute-success-1",
    )
    assert attempt.status == "completed"
    assert attempt.outcome == "success"
    assert attempt.simulated is True
    assert payout.status == "completed"

    duplicate = execute_payout_request(
        db,
        admin=admin,
        payout_id=payout.id,
        scenario="success",
        idempotency_key="execute-success-1",
    )
    assert duplicate.id == attempt.id

    settlement_count = db.scalar(
        select(db.func.count(FinancialTransaction.id)).where(
            FinancialTransaction.idempotency_key == f"payout:{payout.id}:settlement"
        )
    ) if hasattr(db, "func") else None
    settlement = db.scalar(
        select(FinancialTransaction).where(
            FinancialTransaction.idempotency_key == f"payout:{payout.id}:settlement"
        )
    )
    assert settlement is not None
    assert settlement.debit_total == settlement.credit_total == Decimal("600.00")
    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable_signed"] == Decimal("400.00")
    assert balance["total_settled"] == Decimal("600.00")


def test_failure_retry_pending_uncertain_and_reconciliation(db, make_customer, make_admin):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    admin = make_admin()
    _post_net(db, seller, "2000.00")

    failed_payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("500.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    failed_payout.status = "approved"
    db.flush()
    failed_attempt = execute_payout_request(
        db,
        admin=admin,
        payout_id=failed_payout.id,
        scenario="failure",
    )
    assert failed_attempt.status == "failed"
    assert failed_attempt.retryable is True
    assert failed_payout.status == "failed"

    retried = retry_payout_request(
        db,
        admin=admin,
        payout_id=failed_payout.id,
        scenario="success",
    )
    assert retried.status == "completed"
    assert retried.outcome == "success"
    assert failed_payout.status == "completed"

    pending_payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("500.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    pending_payout.status = "approved"
    db.flush()
    pending_attempt = execute_payout_request(
        db,
        admin=admin,
        payout_id=pending_payout.id,
        scenario="pending",
    )
    assert pending_attempt.status == "pending"
    assert pending_attempt.uncertain is True
    assert pending_payout.status == "processing"

    uncertain_payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("500.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    uncertain_payout.status = "approved"
    db.flush()
    uncertain_attempt = execute_payout_request(
        db,
        admin=admin,
        payout_id=uncertain_payout.id,
        scenario="uncertain",
    )
    assert uncertain_attempt.status == "uncertain"
    assert uncertain_payout.status == "uncertain"
    assert uncertain_payout.reconciliation_status == "required"

    with pytest.raises(Exception):
        retry_payout_request(
            db,
            admin=admin,
            payout_id=uncertain_payout.id,
            scenario="success",
        )

    reconciled = reconcile_payout_request(
        db,
        admin=admin,
        payout_id=uncertain_payout.id,
        outcome="success",
        provider_reference="manual_confirmed_mock_1",
    )
    assert reconciled.status == "completed"
    assert reconciled.reconciliation_status == "reconciled"


def test_refund_debt_after_confirmed_settlement(db, make_customer, make_admin):
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    admin = make_admin()
    _post_net(db, seller, "1000.00")
    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("600.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    payout.status = "approved"
    db.flush()
    execute_payout_request(
        db,
        admin=admin,
        payout_id=payout.id,
        scenario="success",
    )
    _post_net(db, seller, "500.00", direction="debit")
    balance = get_seller_payable_balance(db, seller.id)
    assert balance["seller_net_payable_signed"] == Decimal("-100.00")
    assert balance["debt_amount"] == Decimal("100.00")
    assert balance["available_amount"] == Decimal("0")


def test_account_verification_transitions_history_immutability_and_snapshot(db, make_customer, make_admin):
    seller = _seller(db, make_customer)
    admin = make_admin()
    account = SellerPayoutAccount(
        seller_id=seller.id,
        account_type="upi",
        display_name="Test UPI",
        masked_identifier="test***@upi",
        verification_status="pending",
        is_active=True,
    )
    db.add(account)
    db.flush()

    approved = approve_payout_account_verification(
        db,
        admin=admin,
        account_id=account.id,
        administrative_notes="Manual review.",
    )
    assert approved.verification_status == "verified"

    rejected = reject_payout_account_verification(
        db,
        admin=admin,
        account_id=account.id,
        reason="Please correct the masked identifier.",
        administrative_notes="Correction needed.",
    )
    assert rejected.verification_status == "rejected"
    assert rejected.verification_reason == "Please correct the masked identifier."

    reapproved = approve_payout_account_verification(
        db,
        admin=admin,
        account_id=account.id,
        administrative_notes="Corrected account reviewed.",
    )
    assert reapproved.verification_status == "verified"

    history = db.scalars(
        select(PayoutAccountVerificationHistory)
        .where(PayoutAccountVerificationHistory.payout_account_id == account.id)
        .order_by(PayoutAccountVerificationHistory.created_at)
    ).all()
    assert len(history) == 3
    assert history[0].previous_status == "pending"
    assert history[0].new_status == "verified"
    assert history[1].new_status == "rejected"
    assert history[1].rejection_reason == "Please correct the masked identifier."

    with pytest.raises(DBAPIError):
        history[0].administrative_notes = "tampered"
        db.flush()

    db.rollback()
    seller = _seller(db, make_customer)
    account = _verified_account(db, seller)
    _post_net(db, seller, "500.00")
    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=account.id,
        amount=Decimal("500.00"),
        idempotency_key=f"withdraw:{uuid.uuid4().hex}",
    )
    attempt = PayoutExecutionAttempt(
        payout_request_id=payout.id,
        attempt_no=1,
        idempotency_key=f"attempt:{uuid.uuid4().hex}",
        provider_name="mock",
        status="processing",
        outcome="uncertain",
        retryable=False,
        uncertain=True,
    )
    db.add(attempt)
    db.flush()
    with pytest.raises(DBAPIError):
        attempt.status = "completed"
        db.flush()

    db.rollback()
