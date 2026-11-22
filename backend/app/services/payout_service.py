"""Phase 10.2 payout foundation.

Live payout execution is intentionally disabled. This module provides secure
account metadata, ledger-backed balances, reservations and settlement primitives.
"""
from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.financial import FinancialLedgerEntry, FinancialTransaction
from app.models.payout import (
    PayoutConfiguration,
    PayoutAccountVerificationHistory,
    PayoutExecutionAttempt,
    PayoutRequest,
    SellerPayoutAccount,
)
from app.models.seller import SellerProfile
from app.services.financial_service import quantize_money
from app.services.payout_provider import (
    MockPayoutProvider,
    PayoutProviderRequest,
    mock_payout_provider,
)


ACTIVE_RESERVATION_STATUSES = (
    "requested",
    "under_review",
    "approved",
    "processing",
)


def get_payout_configuration(db: Session) -> PayoutConfiguration:
    config = db.scalar(
        select(PayoutConfiguration).where(PayoutConfiguration.singleton_key == "default")
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payout configuration is missing.",
        )
    if config.live_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live payout execution is disabled.",
        )
    return config


def get_seller_payable_balance(db: Session, seller_id: uuid.UUID) -> dict:
    """Calculate ledger-backed payable, reserved, available, settled and debt values."""
    net_credit = db.scalar(
        select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller_id,
            FinancialLedgerEntry.entry_type == "seller_net_earnings",
            FinancialLedgerEntry.direction == "credit",
        )
    ) or Decimal("0")
    net_debit = db.scalar(
        select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller_id,
            FinancialLedgerEntry.entry_type == "seller_net_earnings",
            FinancialLedgerEntry.direction == "debit",
        )
    ) or Decimal("0")
    settlement_debit = db.scalar(
        select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller_id,
            FinancialLedgerEntry.entry_type == "payout",
            FinancialLedgerEntry.direction == "debit",
            FinancialLedgerEntry.account_code == "SELLER_NET_PAYABLE",
        )
    ) or Decimal("0")

    payable = quantize_money(
        Decimal(str(net_credit)) - Decimal(str(net_debit)) - Decimal(str(settlement_debit))
    )
    reserved = db.scalar(
        select(func.coalesce(func.sum(PayoutRequest.amount), Decimal("0"))).where(
            PayoutRequest.seller_id == seller_id,
            PayoutRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
            PayoutRequest.reservation_status == "reserved",
        )
    ) or Decimal("0")
    reserved = quantize_money(reserved)

    debt = quantize_money(max(Decimal("0"), -payable))
    available = quantize_money(max(Decimal("0"), payable - reserved))
    settled = quantize_money(settlement_debit)

    config = get_payout_configuration(db)
    if payable < Decimal("0"):
        available = Decimal("0")

    return {
        "currency": config.currency,
        "seller_net_payable_signed": quantize_money(payable),
        "seller_net_payable": quantize_money(max(Decimal("0"), payable)),
        "total_settled": settled,
        "reserved_amount": reserved,
        "available_amount": available,
        "debt_amount": debt,
        "minimum_amount": quantize_money(config.minimum_amount),
        "maximum_amount": quantize_money(config.maximum_amount),
        "live_execution_enabled": False,
    }


def lock_seller_payout_state(db: Session, seller_id: uuid.UUID) -> SellerProfile:
    seller = db.scalar(
        select(SellerProfile).where(SellerProfile.id == seller_id).with_for_update()
    )
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found.")
    return seller


def create_payout_reservation(
    db: Session,
    *,
    seller: SellerProfile,
    payout_account_id: uuid.UUID,
    amount: Decimal,
    idempotency_key: str,
) -> PayoutRequest:
    """Atomically reserve a payout against the seller's ledger-backed balance."""
    existing = db.scalar(
        select(PayoutRequest).where(PayoutRequest.idempotency_key == idempotency_key)
    )
    if existing:
        if existing.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout idempotency conflict.")
        return existing

    lock_seller_payout_state(db, seller.id)
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(
            SellerPayoutAccount.id == payout_account_id,
            SellerPayoutAccount.seller_id == seller.id,
        )
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout account is inactive.")
    if account.verification_status != "verified":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout account is not verified.")

    amount = quantize_money(amount)
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payout amount must be positive.")

    config = get_payout_configuration(db)
    if amount < quantize_money(config.minimum_amount):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payout amount is below the minimum of {config.minimum_amount}.",
        )
    if amount > quantize_money(config.maximum_amount):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payout amount exceeds the maximum of {config.maximum_amount}.",
        )

    balance = get_seller_payable_balance(db, seller.id)
    if balance["currency"] != config.currency:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout currency mismatch.")
    available = balance["available_amount"]
    if amount > available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout amount exceeds the seller's available balance.",
        )

    payout = PayoutRequest(
        seller_id=seller.id,
        payout_account_id=account.id,
        idempotency_key=idempotency_key,
        amount=amount,
        currency=config.currency,
        status="requested",
        reservation_status="reserved",
        account_type_snapshot=account.account_type,
        destination_masked_snapshot=account.masked_identifier,
        provider_account_reference_snapshot=account.provider_account_reference,
        available_balance_snapshot=available,
        snapshot_metadata={
            "account_type": account.account_type,
            "masked_identifier": account.masked_identifier,
            "provider_reference_present": bool(account.provider_account_reference),
        },
    )
    db.add(payout)
    db.flush()
    return payout


def release_payout_reservation(
    db: Session,
    *,
    payout: PayoutRequest,
    reason: str,
) -> PayoutRequest:
    lock_seller_payout_state(db, payout.seller_id)
    locked = db.scalar(
        select(PayoutRequest).where(PayoutRequest.id == payout.id).with_for_update()
    )
    if not locked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if locked.reservation_status == "reserved":
        locked.reservation_status = "released"
    if locked.status not in ("rejected", "cancelled", "failed"):
        locked.status = "cancelled"
    locked.cancelled_at = locked.cancelled_at or datetime.now(timezone.utc)
    locked.failure_reason = reason[:500]
    db.flush()
    return locked


def post_payout_settlement(
    db: Session,
    *,
    payout: PayoutRequest,
    execution_reference: Optional[str] = None,
    mock_execution: bool = True,
) -> FinancialTransaction:
    """Post an immutable balanced settlement only after a confirmed success outcome."""
    lock_seller_payout_state(db, payout.seller_id)
    locked = db.scalar(
        select(PayoutRequest).where(PayoutRequest.id == payout.id).with_for_update()
    )
    if not locked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if locked.status == "completed" and locked.reservation_status == "deducted":
        existing = db.scalar(
            select(FinancialTransaction).where(
                FinancialTransaction.idempotency_key == f"payout:{locked.id}:settlement"
            )
        )
        if existing:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed payout settlement is missing an immutable ledger transaction.",
        )
    if locked.status != "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a processing payout can be settled.",
        )
    if locked.reservation_status != "reserved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout reservation is not active.",
        )

    balance = get_seller_payable_balance(db, locked.seller_id)
    if locked.amount > quantize_money(Decimal(str(balance["seller_net_payable"]))):
        locked.status = "uncertain"
        locked.reservation_status = "retained"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout eligibility changed; settlement is held for reconciliation.",
        )

    idempotency_key = f"payout:{locked.id}:settlement"
    existing = db.scalar(
        select(FinancialTransaction).where(FinancialTransaction.idempotency_key == idempotency_key)
    )
    if existing:
        return existing

    amount = quantize_money(locked.amount)
    tx = FinancialTransaction(
        transaction_type="payout_settlement",
        idempotency_key=idempotency_key,
        status="posted",
        currency=locked.currency,
        debit_total=amount,
        credit_total=amount,
        seller_id=locked.seller_id,
        provider_transaction_id=execution_reference,
        metadata_json={
            "payout_request_id": str(locked.id),
            "execution_reference": execution_reference,
            "mock_execution": bool(mock_execution),
        },
    )
    db.add(tx)
    db.flush()

    entries = [
        {
            "entry_type": "payout",
            "account_code": "SELLER_NET_PAYABLE",
            "direction": "debit",
            "amount": amount,
            "description": "Confirmed payout settlement reduces seller net payable",
        },
        {
            "entry_type": "payout",
            "account_code": "PAYOUT_CLEARING",
            "direction": "credit",
            "amount": amount,
            "description": "Payout clearing credited for confirmed settlement",
        },
    ]
    for index, entry in enumerate(entries):
        db.add(
            FinancialLedgerEntry(
                transaction_id=tx.id,
                idempotency_key=f"{idempotency_key}:entry:{index}",
                entry_type=entry["entry_type"],
                account_code=entry["account_code"],
                direction=entry["direction"],
                amount=amount,
                currency=locked.currency,
                seller_id=locked.seller_id,
                description=entry["description"],
            )
        )

    locked.status = "completed"
    locked.reservation_status = "deducted"
    locked.completed_at = datetime.now(timezone.utc)
    db.flush()
    return tx


def list_seller_payout_accounts(db: Session, seller: SellerProfile) -> list[dict]:
    accounts = db.scalars(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.seller_id == seller.id)
        .order_by(SellerPayoutAccount.is_default.desc(), SellerPayoutAccount.created_at.desc())
    ).all()
    return [
        {
            "id": account.id,
            "account_type": account.account_type,
            "display_name": account.display_name,
            "bank_name": account.bank_name,
            "masked_identifier": account.masked_identifier,
            "verification_status": account.verification_status,
            "is_default": account.is_default,
            "is_active": account.is_active,
            "verified_at": account.verified_at,
            "verification_reason": account.verification_reason,
            "deactivated_at": account.deactivated_at,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }
        for account in accounts
    ]


def create_seller_payout_account(
    db: Session,
    *,
    seller: SellerProfile,
    account_type: str,
    display_name: str,
    bank_name: Optional[str],
    masked_identifier: str,
    provider_account_reference: Optional[str],
    is_default: bool,
) -> SellerPayoutAccount:
    lock_seller_payout_state(db, seller.id)
    if account_type == "bank":
        if not bank_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Bank name is required.")
    if account_type == "upi":
        bank_name = None

    if provider_account_reference:
        cleaned_reference = provider_account_reference.strip()
    else:
        cleaned_reference = None
    if cleaned_reference and len(cleaned_reference) > 255:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provider reference is too long.")

    account = SellerPayoutAccount(
        seller_id=seller.id,
        account_type=account_type,
        display_name=display_name.strip(),
        bank_name=bank_name.strip() if bank_name else None,
        masked_identifier=masked_identifier.strip(),
        provider_account_reference=cleaned_reference,
        verification_status="pending",
        is_default=False,
        is_active=True,
    )
    db.add(account)
    db.flush()
    if is_default:
        set_seller_payout_account_default(db, seller=seller, account_id=account.id)
    return account


def update_seller_payout_account(
    db: Session,
    *,
    seller: SellerProfile,
    account_id: uuid.UUID,
    display_name: Optional[str],
    bank_name: Optional[str],
    masked_identifier: Optional[str],
    provider_account_reference: Optional[str],
) -> SellerPayoutAccount:
    lock_seller_payout_state(db, seller.id)
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.id == account_id, SellerPayoutAccount.seller_id == seller.id)
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    active = db.scalar(
        select(PayoutRequest.id).where(
            PayoutRequest.payout_account_id == account.id,
            PayoutRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
        ).limit(1)
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout account cannot be changed while an active payout uses it.",
        )
    if display_name is not None:
        account.display_name = display_name.strip()
    if bank_name is not None:
        account.bank_name = bank_name.strip() or None
    if masked_identifier is not None:
        account.masked_identifier = masked_identifier.strip()
    if provider_account_reference is not None:
        account.provider_account_reference = provider_account_reference.strip() or None
    account.verification_status = "pending"
    account.verified_at = None
    account.verified_by_admin_id = None
    account.verification_reason = "Account details changed and require re-verification."
    db.flush()
    return account


def set_seller_payout_account_default(
    db: Session,
    *,
    seller: SellerProfile,
    account_id: uuid.UUID,
) -> SellerPayoutAccount:
    lock_seller_payout_state(db, seller.id)
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.id == account_id, SellerPayoutAccount.seller_id == seller.id)
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inactive payout accounts cannot be default.")
    for other in db.scalars(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.seller_id == seller.id, SellerPayoutAccount.is_default)
        .with_for_update()
    ).all():
        if other.id != account.id:
            other.is_default = False
    account.is_default = True
    db.flush()
    return account


def deactivate_seller_payout_account(
    db: Session,
    *,
    seller: SellerProfile,
    account_id: uuid.UUID,
) -> SellerPayoutAccount:
    lock_seller_payout_state(db, seller.id)
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.id == account_id, SellerPayoutAccount.seller_id == seller.id)
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    active = db.scalar(
        select(PayoutRequest.id).where(
            PayoutRequest.payout_account_id == account.id,
            PayoutRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
        ).limit(1)
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout account cannot be deactivated while an active payout uses it.",
        )
    account.is_active = False
    account.is_default = False
    account.deactivated_at = datetime.now(timezone.utc)
    db.flush()
    return account


def admin_list_payout_account_verification(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: Optional[str] = None,
    seller_id: Optional[uuid.UUID] = None,
    account_type: Optional[str] = None,
) -> dict:
    stmt = select(SellerPayoutAccount)
    if status_filter:
        stmt = stmt.where(SellerPayoutAccount.verification_status == status_filter)
    if seller_id:
        stmt = stmt.where(SellerPayoutAccount.seller_id == seller_id)
    if account_type:
        stmt = stmt.where(SellerPayoutAccount.account_type == account_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    accounts = db.scalars(
        stmt.order_by(SellerPayoutAccount.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for account in accounts:
        seller = db.get(SellerProfile, account.seller_id)
        items.append({
            "id": account.id,
            "seller_id": account.seller_id,
            "store_name": seller.store_name if seller else None,
            "account_type": account.account_type,
            "display_name": account.display_name,
            "bank_name": account.bank_name,
            "masked_identifier": account.masked_identifier,
            "verification_status": account.verification_status,
            "is_default": account.is_default,
            "is_active": account.is_active,
            "verified_at": account.verified_at,
            "verification_reason": account.verification_reason,
            "deactivated_at": account.deactivated_at,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def admin_get_payout_account_verification(db: Session, account_id: uuid.UUID) -> dict:
    account = db.get(SellerPayoutAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    seller = db.get(SellerProfile, account.seller_id)
    return {
        "id": account.id,
        "seller_id": account.seller_id,
        "store_name": seller.store_name if seller else None,
        "account_type": account.account_type,
        "display_name": account.display_name,
        "bank_name": account.bank_name,
        "masked_identifier": account.masked_identifier,
        "verification_status": account.verification_status,
        "is_default": account.is_default,
        "is_active": account.is_active,
        "verified_at": account.verified_at,
        "verification_reason": account.verification_reason,
        "deactivated_at": account.deactivated_at,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def approve_payout_account_verification(
    db: Session,
    *,
    admin,
    account_id: uuid.UUID,
    administrative_notes: Optional[str],
) -> SellerPayoutAccount:
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.id == account_id)
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    previous = account.verification_status
    if previous not in ("pending", "unverified", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout account is already verified or ineligible for approval.",
        )
    account.verification_status = "verified"
    account.verified_at = datetime.now(timezone.utc)
    account.verified_by_admin_id = admin.id
    account.verification_reason = None
    db.add(
        PayoutAccountVerificationHistory(
            payout_account_id=account.id,
            seller_id=account.seller_id,
            previous_status=previous,
            new_status="verified",
            administrator_id=admin.id,
            rejection_reason=None,
            administrative_notes=(administrative_notes or "").strip() or None,
        )
    )
    db.flush()
    return account


def reject_payout_account_verification(
    db: Session,
    *,
    admin,
    account_id: uuid.UUID,
    reason: str,
    administrative_notes: Optional[str],
) -> SellerPayoutAccount:
    cleaned_reason = reason.strip()
    if len(cleaned_reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty rejection reason is required.",
        )
    account = db.scalar(
        select(SellerPayoutAccount)
        .where(SellerPayoutAccount.id == account_id)
        .with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    previous = account.verification_status
    if previous not in ("pending", "unverified", "verified"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout account is already rejected.",
        )
    account.verification_status = "rejected"
    account.verified_at = None
    account.verified_by_admin_id = None
    account.verification_reason = cleaned_reason[:2000]
    db.add(
        PayoutAccountVerificationHistory(
            payout_account_id=account.id,
            seller_id=account.seller_id,
            previous_status=previous,
            new_status="rejected",
            administrator_id=admin.id,
            rejection_reason=cleaned_reason[:2000],
            administrative_notes=(administrative_notes or "").strip()[:2000] or None,
        )
    )
    db.flush()
    return account


def list_payout_account_verification_history(
    db: Session,
    *,
    account_id: uuid.UUID,
    page: int,
    page_size: int,
) -> dict:
    account = db.get(SellerPayoutAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout account not found.")
    stmt = select(PayoutAccountVerificationHistory).where(
        PayoutAccountVerificationHistory.payout_account_id == account_id
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    rows = db.scalars(
        stmt.order_by(PayoutAccountVerificationHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "payout_account_id": row.payout_account_id,
                "seller_id": row.seller_id,
                "previous_status": row.previous_status,
                "new_status": row.new_status,
                "administrator_id": row.administrator_id,
                "rejection_reason": row.rejection_reason,
                "administrative_notes": row.administrative_notes,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def payout_request_dict(payout: PayoutRequest) -> dict:
    return {
        "id": payout.id,
        "seller_id": payout.seller_id,
        "payout_account_id": payout.payout_account_id,
        "amount": quantize_money(payout.amount),
        "currency": payout.currency,
        "status": payout.status,
        "reservation_status": payout.reservation_status,
        "account_type_snapshot": payout.account_type_snapshot,
        "destination_masked_snapshot": payout.destination_masked_snapshot,
        "available_balance_snapshot": quantize_money(payout.available_balance_snapshot),
        "rejection_reason": payout.rejection_reason,
        "failure_reason": payout.failure_reason,
        "reviewed_at": payout.reviewed_at,
        "approved_at": payout.approved_at,
        "processing_at": payout.processing_at,
        "completed_at": payout.completed_at,
        "cancelled_at": payout.cancelled_at,
        "failed_at": payout.failed_at,
        "reconciliation_status": payout.reconciliation_status,
        "reconciled_at": payout.reconciled_at,
        "execution_status": payout.status,
        "settlement_status": "completed" if payout.status == "completed" else "not_settled",
        "settlement_reference": None,
        "created_at": payout.created_at,
        "updated_at": payout.updated_at,
    }


def list_seller_payout_requests(
    db: Session,
    *,
    seller: SellerProfile,
    page: int,
    page_size: int,
    status_filter: Optional[str] = None,
) -> dict:
    stmt = select(PayoutRequest).where(PayoutRequest.seller_id == seller.id)
    if status_filter:
        stmt = stmt.where(PayoutRequest.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    rows = db.scalars(
        stmt.order_by(PayoutRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [payout_request_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_seller_payout_request(db: Session, *, seller: SellerProfile, payout_id: uuid.UUID) -> PayoutRequest:
    payout = db.scalar(
        select(PayoutRequest).where(PayoutRequest.id == payout_id, PayoutRequest.seller_id == seller.id)
    )
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    return payout


def list_seller_payout_attempts(
    db: Session,
    *,
    seller: SellerProfile,
    payout_id: uuid.UUID,
) -> list[dict]:
    payout = db.scalar(
        select(PayoutRequest).where(PayoutRequest.id == payout_id, PayoutRequest.seller_id == seller.id)
    )
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    attempts = db.scalars(
        select(PayoutExecutionAttempt)
        .where(PayoutExecutionAttempt.payout_request_id == payout.id)
        .order_by(PayoutExecutionAttempt.attempt_no.asc())
    ).all()
    return [
        {
            "id": attempt.id,
            "attempt_no": attempt.attempt_no,
            "status": attempt.status,
            "outcome": attempt.outcome,
            "retryable": attempt.retryable,
            "uncertain": attempt.uncertain,
            "simulated": attempt.simulated,
            "sanitized_error": attempt.sanitized_error,
            "started_at": attempt.started_at,
            "completed_at": attempt.completed_at,
        }
        for attempt in attempts
    ]


def cancel_seller_payout_request(
    db: Session,
    *,
    seller: SellerProfile,
    payout_id: uuid.UUID,
    reason: Optional[str],
) -> PayoutRequest:
    lock_seller_payout_state(db, seller.id)
    payout = db.scalar(
        select(PayoutRequest)
        .where(PayoutRequest.id == payout_id, PayoutRequest.seller_id == seller.id)
        .with_for_update()
    )
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if payout.status not in ("requested", "under_review", "approved"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This payout request can no longer be cancelled.",
        )
    payout.status = "cancelled"
    payout.reservation_status = "released"
    payout.cancelled_at = datetime.now(timezone.utc)
    payout.failure_reason = (reason or "Cancelled by seller").strip()[:500]
    db.flush()
    return payout


def list_admin_payout_requests(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: Optional[str] = None,
    seller_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    stmt = select(PayoutRequest)
    if status_filter:
        stmt = stmt.where(PayoutRequest.status == status_filter)
    if seller_id:
        stmt = stmt.where(PayoutRequest.seller_id == seller_id)
    if date_from:
        stmt = stmt.where(PayoutRequest.created_at >= date_from)
    if date_to:
        stmt = stmt.where(PayoutRequest.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    rows = db.scalars(
        stmt.order_by(PayoutRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [payout_request_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_admin_payout_request(db: Session, payout_id: uuid.UUID) -> PayoutRequest:
    payout = db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    return payout


def review_payout_request(db: Session, *, admin, payout_id: uuid.UUID, reason: Optional[str]) -> PayoutRequest:
    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if payout.status != "requested":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout request cannot be put under review.")
    payout.status = "under_review"
    payout.reviewed_by_admin_id = admin.id
    payout.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return payout


def approve_payout_request(db: Session, *, admin, payout_id: uuid.UUID, reason: Optional[str]) -> PayoutRequest:
    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    lock_seller_payout_state(db, payout.seller_id)
    if payout.status not in ("requested", "under_review"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout request cannot be approved.")

    account = db.get(SellerPayoutAccount, payout.payout_account_id)
    if not account or not account.is_active or account.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout destination is inactive or unverified.",
        )
    balance = get_seller_payable_balance(db, payout.seller_id)
    other_reserved = db.scalar(
        select(func.coalesce(func.sum(PayoutRequest.amount), Decimal("0"))).where(
            PayoutRequest.seller_id == payout.seller_id,
            PayoutRequest.id != payout.id,
            PayoutRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
            PayoutRequest.reservation_status == "reserved",
        )
    ) or Decimal("0")
    eligible = (
        Decimal(str(balance["seller_net_payable_signed"]))
        - Decimal(str(other_reserved))
    )
    if payout.amount > quantize_money(max(Decimal("0"), eligible)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout is no longer eligible against the seller's available balance.",
        )
    payout.status = "approved"
    payout.approved_by_admin_id = admin.id
    payout.approved_at = datetime.now(timezone.utc)
    payout.reviewed_by_admin_id = payout.reviewed_by_admin_id or admin.id
    payout.reviewed_at = payout.reviewed_at or datetime.now(timezone.utc)
    db.flush()
    return payout


def reject_payout_request(db: Session, *, admin, payout_id: uuid.UUID, reason: str) -> PayoutRequest:
    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if payout.status not in ("requested", "under_review"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payout request cannot be rejected.")
    payout.status = "rejected"
    payout.reservation_status = "released"
    payout.rejection_reason = reason.strip()[:2000]
    payout.reviewed_by_admin_id = admin.id
    payout.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return payout


def get_admin_payout_report(db: Session, date_from: Optional[datetime], date_to: Optional[datetime]) -> dict:
    stmt = select(PayoutRequest)
    if date_from:
        stmt = stmt.where(PayoutRequest.created_at >= date_from)
    if date_to:
        stmt = stmt.where(PayoutRequest.created_at <= date_to)
    rows = db.scalars(stmt).all()
    config = get_payout_configuration(db)

    def amount_for(statuses: tuple[str, ...]) -> Decimal:
        return quantize_money(
            sum(
                (Decimal(str(row.amount)) for row in rows if row.status in statuses),
                Decimal("0"),
            )
        )

    return {
        "currency": config.currency,
        "total_requests": len(rows),
        "total_requested_amount": quantize_money(
            sum((Decimal(str(row.amount)) for row in rows), Decimal("0"))
        ),
        "awaiting_review_amount": amount_for(("requested", "under_review")),
        "approved_amount": amount_for(("approved",)),
        "processing_amount": amount_for(("processing",)),
        "settled_amount": amount_for(("completed",)),
        "failed_amount": amount_for(("failed", "uncertain")),
    }


def payout_attempt_dict(attempt: PayoutExecutionAttempt) -> dict:
    return {
        "id": attempt.id,
        "payout_request_id": attempt.payout_request_id,
        "attempt_no": attempt.attempt_no,
        "idempotency_key": attempt.idempotency_key,
        "provider_name": attempt.provider_name,
        "provider_reference": attempt.provider_reference,
        "status": attempt.status,
        "outcome": attempt.outcome,
        "retryable": attempt.retryable,
        "uncertain": attempt.uncertain,
        "sanitized_error": attempt.sanitized_error,
        "simulated": attempt.simulated,
        "executed_by_admin_id": attempt.executed_by_admin_id,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
    }


def list_payout_execution_attempts(db: Session, payout_id: uuid.UUID) -> list[dict]:
    payout = db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    attempts = db.scalars(
        select(PayoutExecutionAttempt)
        .where(PayoutExecutionAttempt.payout_request_id == payout_id)
        .order_by(PayoutExecutionAttempt.attempt_no.asc())
    ).all()
    return [payout_attempt_dict(attempt) for attempt in attempts]


def _next_attempt_no(db: Session, payout_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(PayoutExecutionAttempt.attempt_no)).where(
            PayoutExecutionAttempt.payout_request_id == payout_id
        )
    )
    return int(current or 0) + 1


def _eligible_to_execute(db: Session, payout: PayoutRequest) -> None:
    if payout.status not in ("approved", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved or retryable failed payouts can be executed.",
        )
    account = db.get(SellerPayoutAccount, payout.payout_account_id)
    if not account or not account.is_active or account.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout destination is inactive or unverified.",
        )
    balance = get_seller_payable_balance(db, payout.seller_id)
    other_reserved = db.scalar(
        select(func.coalesce(func.sum(PayoutRequest.amount), Decimal("0"))).where(
            PayoutRequest.seller_id == payout.seller_id,
            PayoutRequest.id != payout.id,
            PayoutRequest.status.in_(ACTIVE_RESERVATION_STATUSES),
            PayoutRequest.reservation_status == "reserved",
        )
    ) or Decimal("0")
    eligible = (
        Decimal(str(balance["seller_net_payable_signed"]))
        - Decimal(str(other_reserved))
    )
    if payout.amount > quantize_money(max(Decimal("0"), eligible)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payout is no longer eligible for execution.",
        )


def execute_payout_request(
    db: Session,
    *,
    admin,
    payout_id: uuid.UUID,
    scenario: str = "success",
    idempotency_key: Optional[str] = None,
) -> PayoutExecutionAttempt:
    config = get_payout_configuration(db)
    if not config.mock_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mock payout execution is disabled.",
        )

    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    lock_seller_payout_state(db, payout.seller_id)

    if idempotency_key:
        existing = db.scalar(
            select(PayoutExecutionAttempt).where(PayoutExecutionAttempt.idempotency_key == idempotency_key)
        )
        if existing:
            if existing.payout_request_id != payout.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution idempotency conflict.")
            return existing

    _eligible_to_execute(db, payout)

    if payout.status == "failed":
        last = db.scalar(
            select(PayoutExecutionAttempt)
            .where(PayoutExecutionAttempt.payout_request_id == payout.id)
            .order_by(PayoutExecutionAttempt.attempt_no.desc())
            .limit(1)
        )
        if not last or not last.retryable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This failed payout is not eligible for retry.",
            )
        payout.status = "approved"
        payout.reservation_status = "reserved"
        payout.failure_reason = None
        payout.failed_at = None
        payout.reconciliation_status = "not_required"

    attempt_no = _next_attempt_no(db, payout.id)
    attempt_key = idempotency_key or f"payout:{payout.id}:execution:{attempt_no}"
    existing = db.scalar(
        select(PayoutExecutionAttempt).where(PayoutExecutionAttempt.idempotency_key == attempt_key)
    )
    if existing:
        return existing

    payout.status = "processing"
    payout.processing_at = payout.processing_at or datetime.now(timezone.utc)
    payout.reservation_status = "reserved"
    db.flush()

    provider_request = PayoutProviderRequest(
        payout_id=payout.id,
        amount=payout.amount,
        currency=payout.currency,
        destination_masked=payout.destination_masked_snapshot,
        provider_destination_reference=payout.provider_account_reference_snapshot,
        idempotency_key=attempt_key,
        scenario=scenario if scenario in {"success", "failure", "pending", "uncertain", "timeout"} else "failure",
    )
    try:
        response = mock_payout_provider.execute(provider_request)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    if response.outcome == "success":
        attempt_status = "completed"
        attempt_outcome = "success"
        uncertain = False
        retryable = False
    elif response.outcome == "pending":
        attempt_status = "pending"
        attempt_outcome = "uncertain"
        uncertain = True
        retryable = False
    elif response.outcome in ("uncertain", "timeout"):
        attempt_status = "uncertain"
        attempt_outcome = "uncertain"
        uncertain = True
        retryable = False
    else:
        attempt_status = "failed"
        attempt_outcome = "failed"
        uncertain = False
        retryable = True

    attempt = PayoutExecutionAttempt(
        payout_request_id=payout.id,
        attempt_no=attempt_no,
        idempotency_key=attempt_key,
        provider_name=mock_payout_provider.provider_name,
        provider_reference=response.provider_reference,
        status=attempt_status,
        outcome=attempt_outcome,
        retryable=retryable,
        uncertain=uncertain,
        sanitized_error=response.sanitized_error,
        started_at=now,
        completed_at=now if attempt_status in ("completed", "failed", "uncertain") else None,
        executed_by_admin_id=admin.id,
        simulated=response.simulated,
    )
    db.add(attempt)
    db.flush()

    if response.outcome == "success":
        post_payout_settlement(
            db,
            payout=payout,
            execution_reference=response.provider_reference,
            mock_execution=True,
        )
    elif response.outcome in ("failure",):
        payout.status = "failed"
        payout.reservation_status = "released"
        payout.failure_reason = response.sanitized_error or "Payout execution failed."
        payout.failed_at = now
        payout.reconciliation_status = "not_required"
    elif response.outcome == "pending":
        payout.status = "processing"
        payout.reservation_status = "reserved"
    else:
        payout.status = "uncertain"
        payout.reservation_status = "retained"
        payout.reconciliation_status = "required"
        payout.failure_reason = "Execution outcome is uncertain and requires reconciliation."

    db.flush()
    return attempt


def retry_payout_request(
    db: Session,
    *,
    admin,
    payout_id: uuid.UUID,
    scenario: str = "success",
    idempotency_key: Optional[str] = None,
) -> PayoutExecutionAttempt:
    payout = db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    if payout.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a failed payout with a retryable attempt can be retried.",
        )
    if payout.status == "uncertain" or payout.reconciliation_status == "required":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uncertain payouts require reconciliation before retry.",
        )
    last = db.scalar(
        select(PayoutExecutionAttempt)
        .where(PayoutExecutionAttempt.payout_request_id == payout.id)
        .order_by(PayoutExecutionAttempt.attempt_no.desc())
        .limit(1)
    )
    if not last or not last.retryable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The latest payout attempt is not retryable.",
        )
    return execute_payout_request(
        db,
        admin=admin,
        payout_id=payout_id,
        scenario=scenario,
        idempotency_key=idempotency_key,
    )


def reconcile_payout_request(
    db: Session,
    *,
    admin,
    payout_id: uuid.UUID,
    outcome: str,
    provider_reference: Optional[str] = None,
) -> PayoutRequest:
    payout = db.scalar(select(PayoutRequest).where(PayoutRequest.id == payout_id).with_for_update())
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout request not found.")
    lock_seller_payout_state(db, payout.seller_id)
    if payout.status != "uncertain" or payout.reconciliation_status != "required":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This payout does not require reconciliation.",
        )
    if outcome not in ("success", "failed"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid reconciliation outcome.")

    attempt_no = _next_attempt_no(db, payout.id)
    now = datetime.now(timezone.utc)
    attempt_key = f"payout:{payout.id}:reconcile:{attempt_no}"
    if outcome == "success":
        attempt_status = "completed"
        attempt_outcome = "success"
        retryable = False
        uncertain = False
    else:
        attempt_status = "failed"
        attempt_outcome = "failed"
        retryable = False
        uncertain = False

    attempt = PayoutExecutionAttempt(
        payout_request_id=payout.id,
        attempt_no=attempt_no,
        idempotency_key=attempt_key,
        provider_name="admin-reconciliation",
        provider_reference=provider_reference,
        status=attempt_status,
        outcome=attempt_outcome,
        retryable=retryable,
        uncertain=uncertain,
        sanitized_error=None if outcome == "success" else "Reconciliation confirmed payout failure.",
        started_at=now,
        completed_at=now,
        executed_by_admin_id=admin.id,
        simulated=True,
    )
    db.add(attempt)
    db.flush()

    payout.reconciled_by_admin_id = admin.id
    payout.reconciled_at = now
    payout.reconciliation_status = "reconciled"
    if outcome == "success":
        payout.status = "processing"
        payout.reservation_status = "reserved"
        post_payout_settlement(
            db,
            payout=payout,
            execution_reference=provider_reference,
            mock_execution=True,
        )
    else:
        payout.status = "failed"
        payout.reservation_status = "released"
        payout.failed_at = now
        payout.failure_reason = "Reconciliation confirmed payout failure."
    db.flush()
    return payout
