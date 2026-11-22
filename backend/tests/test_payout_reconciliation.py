import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.models.admin import AuditLog
from app.models.financial import FinancialLedgerEntry, FinancialTransaction
from app.models.payout import (
    PayoutExecutionAttempt,
    PayoutReconciliationHistory,
    PayoutRequest,
    SellerPayoutAccount,
)
from app.models.seller import SellerProfile
from app.models.enums import SellerApplicationStatus
from app.services.payout_reconciliation_service import (
    classify_payout_reconciliation,
    inspect_payout_reconciliation,
    reconciliation_summary,
    resolve_payout_reconciliation,
)


def _seller(db, make_customer):
    customer = make_customer(full_name="Reconciliation Seller")
    seller = SellerProfile(
        customer_id=customer.id,
        store_name="Reconciliation Store",
        store_slug=f"reconciliation-store-{uuid.uuid4().hex[:8]}",
        seller_display_name="Reconciliation Seller",
        contact_email=f"reconcile-{uuid.uuid4().hex[:8]}@example.test",
        country="India",
        business_type="Independent",
        application_status=SellerApplicationStatus.APPROVED,
    )
    db.add(seller)
    db.flush()
    return seller


def _account(db, seller):
    account = SellerPayoutAccount(
        seller_id=seller.id,
        account_type="upi",
        display_name="Reconciliation UPI",
        masked_identifier="rec***@upi",
        provider_account_reference="token_reconciliation",
        verification_status="verified",
        is_default=True,
        is_active=True,
    )
    db.add(account)
    db.flush()
    return account


def _post_net(db, seller, amount):
    tx = FinancialTransaction(
        transaction_type="payment_capture",
        idempotency_key=f"reconcile-net:{uuid.uuid4().hex}",
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
        idempotency_key=f"reconcile-net-entry:{uuid.uuid4().hex}",
        entry_type="seller_net_earnings",
        account_code="SELLER_NET_PAYABLE",
        direction="credit",
        amount=Decimal(amount),
        currency="INR",
        seller_id=seller.id,
        description="Reconciliation test net",
    )
    db.add(entry)
    db.flush()
    return tx


def _payout(db, seller, account, amount="500.00"):
    payout = PayoutRequest(
        seller_id=seller.id,
        payout_account_id=account.id,
        idempotency_key=f"reconcile-payout:{uuid.uuid4().hex}",
        amount=Decimal(amount),
        currency="INR",
        status="approved",
        reservation_status="reserved",
        account_type_snapshot="upi",
        destination_masked_snapshot=account.masked_identifier,
        provider_account_reference_snapshot=account.provider_account_reference,
        available_balance_snapshot=Decimal(amount),
    )
    db.add(payout)
    db.flush()
    return payout


def _attempt(db, payout, outcome="success", status="completed", simulated=True, attempt_no=1):
    attempt = PayoutExecutionAttempt(
        payout_request_id=payout.id,
        attempt_no=attempt_no,
        idempotency_key=f"reconcile-attempt:{uuid.uuid4().hex}",
        provider_name="mock",
        provider_reference=f"mock_ref_{uuid.uuid4().hex[:8]}",
        status=status,
        outcome=outcome,
        retryable=False,
        uncertain=outcome == "uncertain",
        simulated=simulated,
    )
    db.add(attempt)
    db.flush()
    return attempt


def _settlement(db, payout, amount=None, seller_id=None, valid=True):
    amount = Decimal(amount or payout.amount)
    tx = FinancialTransaction(
        transaction_type="payout_settlement",
        idempotency_key=f"payout:{payout.id}:settlement:{uuid.uuid4().hex[:6]}",
        status="posted",
        currency=payout.currency,
        debit_total=amount,
        credit_total=amount,
        seller_id=seller_id or payout.seller_id,
        provider_transaction_id="mock_settlement_ref",
        metadata_json={"payout_request_id": str(payout.id), "mock_execution": True},
    )
    db.add(tx)
    db.flush()
    if valid:
        db.add(
            FinancialLedgerEntry(
                transaction_id=tx.id,
                idempotency_key=f"reconcile-ledger:{uuid.uuid4().hex}:debit",
                entry_type="payout",
                account_code="SELLER_NET_PAYABLE",
                direction="debit",
                amount=amount,
                currency=payout.currency,
                seller_id=payout.seller_id,
                description="Test payout debit",
            )
        )
        db.add(
            FinancialLedgerEntry(
                transaction_id=tx.id,
                idempotency_key=f"reconcile-ledger:{uuid.uuid4().hex}:credit",
                entry_type="payout",
                account_code="PAYOUT_CLEARING",
                direction="credit",
                amount=amount,
                currency=payout.currency,
                seller_id=payout.seller_id,
                description="Test payout clearing credit",
            )
        )
    db.flush()
    return tx


def test_consistent_pending_uncertain_failed_and_missing_settlement(db, make_customer):
    seller = _seller(db, make_customer)
    account = _account(db, seller)
    _post_net(db, seller, "3000.00")

    consistent = _payout(db, seller, account, "500.00")
    consistent.status = "completed"
    consistent.reservation_status = "deducted"
    db.flush()
    _attempt(db, consistent, "success", "completed", True)
    _settlement(db, consistent)
    assert classify_payout_reconciliation(db, consistent)["classification"] == "consistent"
    detail = inspect_payout_reconciliation(db, consistent.id)
    assert detail["latest_attempt"]["simulated"] is True
    assert detail["settlement"]["mock_execution"] is True

    pending = _payout(db, seller, account, "500.00")
    pending.status = "processing"
    db.flush()
    _attempt(db, pending, "uncertain", "pending", False)
    assert classify_payout_reconciliation(db, pending)["classification"] == "pending"

    uncertain = _payout(db, seller, account, "500.00")
    uncertain.status = "uncertain"
    uncertain.reconciliation_status = "required"
    db.flush()
    _attempt(db, uncertain, "uncertain", "uncertain", False)
    assert classify_payout_reconciliation(db, uncertain)["classification"] == "uncertain"

    failed = _payout(db, seller, account, "500.00")
    failed.status = "failed"
    db.flush()
    _attempt(db, failed, "failed", "failed", True)
    assert classify_payout_reconciliation(db, failed)["classification"] == "failed"

    missing = _payout(db, seller, account, "500.00")
    missing.status = "completed"
    db.flush()
    _attempt(db, missing, "success", "completed", True)
    assert classify_payout_reconciliation(db, missing)["classification"] == "settlement_missing"


def test_duplicate_unexpected_ledger_status_and_deterministic_priority(db, make_customer):
    seller = _seller(db, make_customer)
    account = _account(db, seller)

    unexpected = _payout(db, seller, account, "500.00")
    _settlement(db, unexpected)
    assert classify_payout_reconciliation(db, unexpected)["classification"] == "unexpected_settlement"

    duplicate = _payout(db, seller, account, "500.00")
    duplicate.status = "completed"
    db.flush()
    _attempt(db, duplicate, "success", "completed", True)
    _settlement(db, duplicate)
    _settlement(db, duplicate)
    duplicate_result = classify_payout_reconciliation(db, duplicate)
    assert duplicate_result["classification"] == "duplicate_settlement"

    mismatch = _payout(db, seller, account, "500.00")
    mismatch.status = "completed"
    db.flush()
    _attempt(db, mismatch, "success", "completed", True)
    _settlement(db, mismatch, amount="499.00")
    mismatch_result = classify_payout_reconciliation(db, mismatch)
    assert mismatch_result["classification"] == "ledger_mismatch"

    status_mismatch = _payout(db, seller, account, "500.00")
    status_mismatch.status = "failed"
    db.flush()
    _attempt(db, status_mismatch, "success", "completed", True)
    status_result = classify_payout_reconciliation(db, status_mismatch)
    assert status_result["classification"] == "status_mismatch"


def test_reconciliation_history_resolution_is_append_only_and_no_settlement(db, make_customer, make_admin):
    seller = _seller(db, make_customer)
    account = _account(db, seller)
    admin = make_admin()
    payout = _payout(db, seller, account, "500.00")

    resolved = resolve_payout_reconciliation(
        db,
        admin=admin,
        payout_id=payout.id,
        resolution_action="investigate",
        resolution_reason="Manual review is required.",
        evidence_reference="ticket-123",
        expected_classification="requires_manual_review",
    )
    assert resolved["previous_classification"] == "requires_manual_review"
    assert resolved["new_classification"] == "requires_manual_review"

    record = db.scalar(
        select(PayoutReconciliationHistory).where(
            PayoutReconciliationHistory.payout_request_id == payout.id
        )
    )
    assert record is not None
    assert record.resolution_reason == "Manual review is required."

    with pytest.raises(DBAPIError):
        record.resolution_reason = "tampered"
        db.flush()

    db.rollback()
    settlement_count = db.scalar(
        select(FinancialTransaction.id).where(
            FinancialTransaction.transaction_type == "payout_settlement",
            FinancialTransaction.metadata_json["payout_request_id"].as_string() == str(payout.id),
        )
    )
    assert settlement_count is None


def test_reconciliation_summary_uses_ledger_and_pending_reservations(db, make_customer):
    seller = _seller(db, make_customer)
    account = _account(db, seller)
    _post_net(db, seller, "2000.00")

    completed = _payout(db, seller, account, "500.00")
    completed.status = "completed"
    completed.reservation_status = "deducted"
    db.flush()
    _attempt(db, completed, "success", "completed", True)
    _settlement(db, completed)

    pending = _payout(db, seller, account, "400.00")
    pending.status = "processing"
    db.flush()
    _attempt(db, pending, "uncertain", "pending", False)

    summary = reconciliation_summary(db)
    assert summary["settled_amount"] == Decimal("500.00")
    assert summary["reserved_amount"] == Decimal("400.00")
    assert summary["pending_amount"] == Decimal("400.00")
    assert summary["completed_amount"] == Decimal("500.00")
