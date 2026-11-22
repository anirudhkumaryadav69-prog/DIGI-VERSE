from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin import AuditLog
from app.models.financial import FinancialLedgerEntry, FinancialTransaction
from app.models.payout import (
    PayoutExecutionAttempt,
    PayoutReconciliationHistory,
    PayoutRequest,
)
from app.models.seller import SellerProfile
from app.services.financial_service import quantize_money
from app.services.payout_service import get_seller_payable_balance


CLASSIFICATIONS = {
    "consistent",
    "pending",
    "uncertain",
    "failed",
    "settlement_missing",
    "unexpected_settlement",
    "duplicate_settlement",
    "ledger_mismatch",
    "status_mismatch",
    "requires_manual_review",
}


def _settlements(db: Session, payout: PayoutRequest) -> list[FinancialTransaction]:
    prefixed = db.scalars(
        select(FinancialTransaction).where(
            FinancialTransaction.transaction_type == "payout_settlement",
            FinancialTransaction.idempotency_key == f"payout:{payout.id}:settlement",
        )
    ).all()
    if prefixed:
        return list(prefixed)
    return list(
        db.scalars(
            select(FinancialTransaction).where(
                FinancialTransaction.transaction_type == "payout_settlement",
                FinancialTransaction.metadata_json["payout_request_id"].as_string() == str(payout.id),
            )
        ).all()
    )


def _latest_attempt(db: Session, payout_id: uuid.UUID) -> Optional[PayoutExecutionAttempt]:
    return db.scalar(
        select(PayoutExecutionAttempt)
        .where(PayoutExecutionAttempt.payout_request_id == payout_id)
        .order_by(PayoutExecutionAttempt.attempt_no.desc())
        .limit(1)
    )


def _settlement_ledger_issue(
    db: Session,
    payout: PayoutRequest,
    settlements: list[FinancialTransaction],
) -> Optional[str]:
    if len(settlements) != 1:
        return "duplicate_settlement" if len(settlements) > 1 else "missing_settlement"

    tx = settlements[0]
    secondary: list[str] = []
    if tx.debit_total != tx.credit_total:
        secondary.append("unbalanced_transaction")
    if quantize_money(tx.debit_total) != quantize_money(payout.amount):
        secondary.append("incorrect_debit_amount")
    if quantize_money(tx.credit_total) != quantize_money(payout.amount):
        secondary.append("incorrect_credit_amount")
    if tx.currency != payout.currency:
        secondary.append("currency_mismatch")
    if tx.seller_id != payout.seller_id:
        secondary.append("incorrect_seller")
    if tx.status != "posted":
        secondary.append("transaction_not_posted")

    entries = db.scalars(
        select(FinancialLedgerEntry).where(FinancialLedgerEntry.transaction_id == tx.id)
    ).all()
    if len(entries) != 2:
        secondary.append("missing_or_extra_ledger_entries")
        return ";".join(secondary)

    expected = {
        ("SELLER_NET_PAYABLE", "debit"): quantize_money(payout.amount),
        ("PAYOUT_CLEARING", "credit"): quantize_money(payout.amount),
    }
    found: dict[tuple[str, str], Decimal] = {}
    for entry in entries:
        key = (entry.account_code, entry.direction)
        if key in found:
            secondary.append("duplicate_ledger_direction")
        found[key] = quantize_money(entry.amount)
        if entry.entry_type != "payout":
            secondary.append("incorrect_entry_type")
        if entry.currency != payout.currency:
            secondary.append("ledger_currency_mismatch")
        if entry.seller_id != payout.seller_id:
            secondary.append("ledger_seller_mismatch")
    if found != expected:
        secondary.append("ledger_accounts_or_amounts_mismatch")

    if sum((Decimal(str(entry.amount)) for entry in entries if entry.direction == "debit"), Decimal("0")) != sum(
        (Decimal(str(entry.amount)) for entry in entries if entry.direction == "credit"),
        Decimal("0"),
    ):
        secondary.append("ledger_unbalanced")

    return ";".join(secondary) if secondary else None


def classify_payout_reconciliation(db: Session, payout: PayoutRequest) -> dict:
    settlements = _settlements(db, payout)
    latest = _latest_attempt(db, payout.id)
    issues: list[str] = []

    if len(settlements) > 1:
        issues.append("multiple_settlement_transactions")
    ledger_issue = _settlement_ledger_issue(db, payout, settlements)
    if ledger_issue and ledger_issue not in ("missing_settlement",):
        issues.append(ledger_issue)

    confirmed_success = bool(
        latest
        and latest.outcome == "success"
        and latest.status == "completed"
        and latest.uncertain is False
    )

    if settlements and not confirmed_success:
        issues.append("settlement_without_confirmed_success")
    if confirmed_success and not settlements:
        issues.append("confirmed_success_without_settlement")
    if payout.status == "completed" and not confirmed_success:
        issues.append("completed_status_without_confirmed_success")
    if latest and latest.outcome == "success" and payout.status != "completed" and not settlements:
        issues.append("success_outcome_status_mismatch")
    if latest and latest.outcome == "failed" and payout.status != "failed":
        issues.append("failed_outcome_status_mismatch")
    if (
        latest
        and latest.outcome == "uncertain"
        and latest.status != "pending"
        and payout.status != "uncertain"
    ):
        issues.append("uncertain_outcome_status_mismatch")
    if latest and latest.status == "pending" and payout.status != "processing":
        issues.append("pending_execution_status_mismatch")

    primary = "requires_manual_review"
    if len(settlements) > 1:
        primary = "duplicate_settlement"
    elif ledger_issue and ledger_issue not in ("missing_settlement",):
        primary = "ledger_mismatch"
    elif settlements and not confirmed_success:
        primary = "unexpected_settlement"
    elif issues and any(
        issue.endswith("status_mismatch")
        or issue in ("completed_status_without_confirmed_success", "success_outcome_status_mismatch")
        for issue in issues
    ):
        primary = "status_mismatch"
    elif confirmed_success or payout.status == "completed":
        if not settlements:
            primary = "settlement_missing"
        elif ledger_issue:
            primary = "ledger_mismatch"
        else:
            primary = "consistent"
    elif payout.status == "processing" and latest and latest.status == "pending":
        primary = "pending"
    elif payout.status == "processing" or (latest and latest.status == "pending"):
        primary = "pending"
    elif payout.status == "uncertain" or (latest and latest.outcome == "uncertain"):
        primary = "uncertain"
    elif payout.status == "failed" or (latest and latest.outcome == "failed"):
        primary = "failed"
    elif not latest and payout.status in ("requested", "under_review", "approved", "rejected", "cancelled"):
        primary = "consistent" if payout.status in ("rejected", "cancelled") else "requires_manual_review"

    if latest and latest.outcome == "success" and latest.simulated:
        issues.append("mock_success_not_independent_provider_confirmation")

    settlement = settlements[0] if len(settlements) == 1 else None
    return {
        "classification": primary,
        "secondary_issues": sorted(set(issues)),
        "payout_id": payout.id,
        "payout_status": payout.status,
        "reconciliation_status": payout.reconciliation_status,
        "latest_attempt": (
            {
                "id": latest.id,
                "attempt_no": latest.attempt_no,
                "status": latest.status,
                "outcome": latest.outcome,
                "simulated": latest.simulated,
                "provider_name": latest.provider_name,
                "uncertain": latest.uncertain,
            }
            if latest
            else None
        ),
        "settlement": (
            {
                "transaction_id": settlement.id,
                "idempotency_key": settlement.idempotency_key,
                "amount": quantize_money(settlement.debit_total),
                "currency": settlement.currency,
                "posted_at": settlement.posted_at,
                "mock_execution": bool((settlement.metadata_json or {}).get("mock_execution")),
            }
            if settlement
            else None
        ),
        "settlement_count": len(settlements),
    }


def inspect_payout_reconciliation(db: Session, payout_id: uuid.UUID) -> dict:
    payout = db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    result = classify_payout_reconciliation(db, payout)
    attempts = db.scalars(
        select(PayoutExecutionAttempt)
        .where(PayoutExecutionAttempt.payout_request_id == payout_id)
        .order_by(PayoutExecutionAttempt.attempt_no.asc())
    ).all()
    settlements = _settlements(db, payout)
    ledger_entries = []
    for settlement in settlements:
        ledger_entries.extend(
            db.scalars(
                select(FinancialLedgerEntry).where(FinancialLedgerEntry.transaction_id == settlement.id)
            ).all()
        )
    history = db.scalars(
        select(PayoutReconciliationHistory)
        .where(PayoutReconciliationHistory.payout_request_id == payout_id)
        .order_by(PayoutReconciliationHistory.created_at.desc())
    ).all()
    account = payout.payout_account_id
    result.update({
        "attempts": [
            {
                "id": attempt.id,
                "attempt_no": attempt.attempt_no,
                "status": attempt.status,
                "outcome": attempt.outcome,
                "simulated": attempt.simulated,
                "provider_name": attempt.provider_name,
                "uncertain": attempt.uncertain,
                "retryable": attempt.retryable,
                "sanitized_error": attempt.sanitized_error,
                "started_at": attempt.started_at,
                "completed_at": attempt.completed_at,
            }
            for attempt in attempts
        ],
        "ledger_entries": [
            {
                "id": entry.id,
                "transaction_id": entry.transaction_id,
                "account_code": entry.account_code,
                "entry_type": entry.entry_type,
                "direction": entry.direction,
                "amount": quantize_money(entry.amount),
                "currency": entry.currency,
                "seller_id": entry.seller_id,
            }
            for entry in ledger_entries
        ],
        "reconciliation_history": [
            {
                "id": record.id,
                "previous_classification": record.previous_classification,
                "new_classification": record.new_classification,
                "resolution_action": record.resolution_action,
                "resolution_reason": record.resolution_reason,
                "administrator_id": record.administrator_id,
                "evidence_reference": record.evidence_reference,
                "created_at": record.created_at,
            }
            for record in history
        ],
        "masked_destination": payout.destination_masked_snapshot,
        "payout_account_id": payout.payout_account_id,
        "seller_id": payout.seller_id,
    })
    return result


def list_reconciliation_queue(
    db: Session,
    *,
    page: int,
    page_size: int,
    classification: Optional[str] = None,
    execution_state: Optional[str] = None,
    seller_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    amount_from: Optional[Decimal] = None,
    amount_to: Optional[Decimal] = None,
    unresolved_only: bool = False,
    sort: str = "created_desc",
) -> dict:
    stmt = select(PayoutRequest)
    if seller_id:
        stmt = stmt.where(PayoutRequest.seller_id == seller_id)
    if date_from:
        stmt = stmt.where(PayoutRequest.created_at >= date_from)
    if date_to:
        stmt = stmt.where(PayoutRequest.created_at <= date_to)
    if amount_from is not None:
        stmt = stmt.where(PayoutRequest.amount >= amount_from)
    if amount_to is not None:
        stmt = stmt.where(PayoutRequest.amount <= amount_to)

    if sort == "amount_asc":
        stmt = stmt.order_by(PayoutRequest.amount.asc(), PayoutRequest.created_at.desc())
    elif sort == "amount_desc":
        stmt = stmt.order_by(PayoutRequest.amount.desc(), PayoutRequest.created_at.desc())
    else:
        stmt = stmt.order_by(PayoutRequest.created_at.desc())

    payouts = db.scalars(stmt).all()
    rows = []
    for payout in payouts:
        result = classify_payout_reconciliation(db, payout)
        result.update({
            "masked_destination": payout.destination_masked_snapshot,
            "payout_account_id": payout.payout_account_id,
            "seller_id": payout.seller_id,
            "attempts": [],
            "ledger_entries": [],
            "reconciliation_history": [],
        })
        if classification and result["classification"] != classification:
            continue
        if execution_state:
            latest = _latest_attempt(db, payout.id)
            state = latest.status if latest else payout.status
            if state != execution_state:
                continue
        if unresolved_only and result["classification"] == "consistent":
            continue
        rows.append(result)

    total = len(rows)
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    offset = (page - 1) * page_size
    return {
        "items": rows[offset:offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def reconciliation_summary(db: Session, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> dict:
    stmt = select(PayoutRequest)
    if date_from:
        stmt = stmt.where(PayoutRequest.created_at >= date_from)
    if date_to:
        stmt = stmt.where(PayoutRequest.created_at <= date_to)
    payouts = db.scalars(stmt).all()

    def amount_for(statuses: tuple[str, ...]) -> Decimal:
        return quantize_money(
            sum(
                (Decimal(str(payout.amount)) for payout in payouts if payout.status in statuses),
                Decimal("0"),
            )
        )

    settled = db.scalar(
        select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.entry_type == "payout",
            FinancialLedgerEntry.account_code == "SELLER_NET_PAYABLE",
            FinancialLedgerEntry.direction == "debit",
        )
    ) or Decimal("0")
    reserved = db.scalar(
        select(func.coalesce(func.sum(PayoutRequest.amount), Decimal("0"))).where(
            PayoutRequest.status.in_(("requested", "under_review", "approved", "processing")),
            PayoutRequest.reservation_status == "reserved",
        )
    ) or Decimal("0")

    debt = Decimal("0")
    seller_ids = sorted({payout.seller_id for payout in payouts})
    for seller_id in seller_ids:
        debt += quantize_money(get_seller_payable_balance(db, seller_id)["debt_amount"])

    classifications: dict[str, int] = {}
    exception_count = 0
    unresolved = 0
    classification_amounts: dict[str, Decimal] = {}
    for payout in payouts:
        result = classify_payout_reconciliation(db, payout)
        name = result["classification"]
        classifications[name] = classifications.get(name, 0) + 1
        classification_amounts[name] = quantize_money(
            Decimal(str(classification_amounts.get(name, Decimal("0")))) + Decimal(str(payout.amount))
        )
        if name != "consistent":
            exception_count += 1
            if name not in ("failed", "cancelled"):
                unresolved += 1

    config = payouts[0] if payouts else None
    currency = "INR"
    if payouts:
        currency = payouts[0].currency

    return {
        "currency": currency,
        "total_payout_requests": len(payouts),
        "total_requested_amount": quantize_money(
            sum((Decimal(str(payout.amount)) for payout in payouts), Decimal("0"))
        ),
        "approved_amount": amount_for(("approved",)),
        "processing_amount": amount_for(("processing",)),
        "completed_amount": amount_for(("completed",)),
        "failed_amount": amount_for(("failed",)),
        "pending_amount": amount_for(("requested", "under_review", "approved", "processing")),
        "uncertain_amount": amount_for(("uncertain",)),
        "settled_amount": quantize_money(settled),
        "reserved_amount": quantize_money(reserved),
        "outstanding_seller_debt": quantize_money(debt),
        "reconciliation_exception_count": exception_count,
        "unresolved_discrepancy_count": unresolved,
        "classification_counts": classifications,
        "classification_amounts": {
            name: quantize_money(amount)
            for name, amount in classification_amounts.items()
        },
    }


def resolve_payout_reconciliation(
    db: Session,
    *,
    admin,
    payout_id: uuid.UUID,
    resolution_action: str,
    resolution_reason: str,
    evidence_reference: Optional[str],
    expected_classification: Optional[str],
) -> dict:
    cleaned_reason = resolution_reason.strip()
    if len(cleaned_reason) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A non-empty resolution reason is required.")
    if resolution_action not in ("investigate", "confirm_evidence", "keep_pending", "mark_resolved"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid reconciliation resolution action.")

    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    lock_seller = payout.seller_id
    if not lock_seller:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout seller is missing.")

    current = classify_payout_reconciliation(db, payout)
    previous = current["classification"]
    if expected_classification and expected_classification != previous:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout reconciliation state changed; reload and retry.",
        )

    latest = _latest_attempt(db, payout.id)
    settlements = _settlements(db, payout)
    settlement = settlements[0] if len(settlements) == 1 else None
    record = PayoutReconciliationHistory(
        payout_request_id=payout.id,
        execution_attempt_id=latest.id if latest else None,
        settlement_transaction_id=settlement.id if settlement else None,
        previous_classification=previous,
        new_classification=previous,
        resolution_action=resolution_action,
        resolution_reason=cleaned_reason[:5000],
        administrator_id=admin.id,
        evidence_reference=(evidence_reference or "").strip()[:255] or None,
    )
    db.add(record)
    db.flush()
    return {
        "id": record.id,
        "payout_request_id": payout.id,
        "previous_classification": previous,
        "new_classification": record.new_classification,
        "resolution_action": record.resolution_action,
        "resolution_reason": record.resolution_reason,
        "administrator_id": record.administrator_id,
        "evidence_reference": record.evidence_reference,
        "created_at": record.created_at,
    }
