import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin, require_approved_seller
from app.core.rate_limit import get_client_ip
from app.models.admin import Admin
from app.models.admin import AuditLog
from app.models.seller import SellerProfile
from app.schemas.auth import GenericMessageResponse
from app.schemas.payout import (
    PaginatedPayoutRequestResponse,
    PayoutAccountCreateRequest,
    PayoutAccountResponse,
    PayoutAccountUpdateRequest,
    PayoutApproveRequest,
    PayoutBalanceResponse,
    PayoutCancelRequest,
    PayoutRejectRequest,
    PayoutReportResponse,
    PayoutRequestCreate,
    PayoutRequestResponse,
    PayoutReviewRequest,
    PayoutExecutionRequest,
    PayoutRetryRequest,
    PayoutReconcileRequest,
    PayoutExecutionAttemptResponse,
    SellerPayoutExecutionAttemptResponse,
    PayoutAccountApproveRequest,
    PayoutAccountRejectRequest,
    PayoutAccountVerificationHistoryResponse,
    PaginatedPayoutAccountVerificationResponse,
    PaginatedPayoutAccountVerificationHistoryResponse,
    PaginatedPayoutReconciliationResponse,
    PayoutReconciliationDetailResponse,
    PayoutReconciliationResolveRequest,
    PayoutReconciliationResolveResponse,
    PayoutReconciliationSummaryResponse,
)
from app.services.catalog_service import record_admin_audit
from app.services.payout_service import (
    approve_payout_request,
    cancel_seller_payout_request,
    create_payout_reservation,
    create_seller_payout_account,
    deactivate_seller_payout_account,
    get_admin_payout_report,
    get_admin_payout_request,
    get_seller_payable_balance,
    get_seller_payout_request,
    list_admin_payout_requests,
    list_seller_payout_accounts,
    list_seller_payout_requests,
    payout_request_dict,
    reject_payout_request,
    review_payout_request,
    set_seller_payout_account_default,
    update_seller_payout_account,
    execute_payout_request,
    retry_payout_request,
    reconcile_payout_request,
    list_payout_execution_attempts,
    payout_attempt_dict,
    admin_list_payout_account_verification as list_admin_payout_account_verification,
    admin_get_payout_account_verification as get_admin_payout_account_verification,
    approve_payout_account_verification,
    reject_payout_account_verification,
    list_payout_account_verification_history,
    list_seller_payout_attempts,
)
from app.services.payout_reconciliation_service import (
    inspect_payout_reconciliation,
    list_reconciliation_queue,
    reconciliation_summary,
    resolve_payout_reconciliation,
)


seller_payout_router = APIRouter(prefix="/seller/payouts", tags=["Seller Payouts"])
admin_payout_router = APIRouter(prefix="/admin/payouts", tags=["Admin Payouts"])
admin_payout_account_router = APIRouter(
    prefix="/admin/payout-accounts",
    tags=["Admin Payout Account Verification"],
)


def _seller_audit(db: Session, seller: SellerProfile, action: str, details: dict) -> None:
    db.add(
        AuditLog(
            admin_id=None,
            action=action,
            entity_type="seller_payout",
            entity_id=str(seller.id),
            details={"seller_id": str(seller.id), **details},
        )
    )


@seller_payout_router.get("/balance", response_model=PayoutBalanceResponse)
def seller_payout_balance(
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutBalanceResponse:
    return PayoutBalanceResponse(**get_seller_payable_balance(db, seller.id))


@seller_payout_router.get("/accounts", response_model=list[PayoutAccountResponse])
def seller_payout_accounts(
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> list[PayoutAccountResponse]:
    return [PayoutAccountResponse(**row) for row in list_seller_payout_accounts(db, seller)]


@seller_payout_router.post("/accounts", response_model=PayoutAccountResponse)
def seller_create_payout_account(
    payload: PayoutAccountCreateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = create_seller_payout_account(
        db,
        seller=seller,
        account_type=payload.account_type,
        display_name=payload.display_name,
        bank_name=payload.bank_name,
        masked_identifier=payload.masked_identifier,
        provider_account_reference=payload.provider_account_reference,
        is_default=payload.is_default,
    )
    _seller_audit(db, seller, "payout.account.created", {"account_id": str(account.id)})
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@seller_payout_router.patch("/accounts/{account_id}", response_model=PayoutAccountResponse)
def seller_update_payout_account(
    account_id: uuid.UUID,
    payload: PayoutAccountUpdateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = update_seller_payout_account(
        db,
        seller=seller,
        account_id=account_id,
        display_name=payload.display_name,
        bank_name=payload.bank_name,
        masked_identifier=payload.masked_identifier,
        provider_account_reference=payload.provider_account_reference,
    )
    _seller_audit(db, seller, "payout.account.updated", {"account_id": str(account.id)})
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@seller_payout_router.post("/accounts/{account_id}/default", response_model=PayoutAccountResponse)
def seller_set_default_payout_account(
    account_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = set_seller_payout_account_default(db, seller=seller, account_id=account_id)
    _seller_audit(db, seller, "payout.account.default.set", {"account_id": str(account.id)})
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@seller_payout_router.delete("/accounts/{account_id}", response_model=PayoutAccountResponse)
def seller_deactivate_payout_account(
    account_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = deactivate_seller_payout_account(db, seller=seller, account_id=account_id)
    _seller_audit(db, seller, "payout.account.deactivated", {"account_id": str(account.id)})
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@seller_payout_router.post("/requests", response_model=PayoutRequestResponse)
def seller_create_payout_request(
    payload: PayoutRequestCreate,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    key = payload.idempotency_key or f"seller-payout:{seller.id}:{uuid.uuid4()}"
    payout = create_payout_reservation(
        db,
        seller=seller,
        payout_account_id=payload.payout_account_id,
        amount=payload.amount,
        idempotency_key=key,
    )
    _seller_audit(
        db,
        seller,
        "payout.request.created",
        {"payout_id": str(payout.id), "amount": str(payout.amount)},
    )
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@seller_payout_router.get("/requests", response_model=PaginatedPayoutRequestResponse)
def seller_list_payout_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, max_length=20),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PaginatedPayoutRequestResponse:
    return PaginatedPayoutRequestResponse(
        **list_seller_payout_requests(
            db,
            seller=seller,
            page=page,
            page_size=page_size,
            status_filter=status,
        )
    )


@seller_payout_router.get("/requests/{payout_id}", response_model=PayoutRequestResponse)
def seller_get_payout_request(
    payout_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = get_seller_payout_request(db, seller=seller, payout_id=payout_id)
    return PayoutRequestResponse(**payout_request_dict(payout))


@seller_payout_router.post("/requests/{payout_id}/cancel", response_model=PayoutRequestResponse)
def seller_cancel_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutCancelRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = cancel_seller_payout_request(
        db,
        seller=seller,
        payout_id=payout_id,
        reason=payload.reason,
    )
    _seller_audit(db, seller, "payout.request.cancelled", {"payout_id": str(payout.id)})
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@seller_payout_router.get(
    "/requests/{payout_id}/attempts",
    response_model=list[SellerPayoutExecutionAttemptResponse],
)
def seller_payout_attempts(
    payout_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> list[SellerPayoutExecutionAttemptResponse]:
    return [
        SellerPayoutExecutionAttemptResponse(**attempt)
        for attempt in list_seller_payout_attempts(
            db,
            seller=seller,
            payout_id=payout_id,
        )
    ]


@admin_payout_router.get("", response_model=PaginatedPayoutRequestResponse)
def admin_list_payout_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, max_length=20),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedPayoutRequestResponse:
    return PaginatedPayoutRequestResponse(
        **list_admin_payout_requests(
            db,
            page=page,
            page_size=page_size,
            status_filter=status,
            seller_id=seller_id,
            date_from=date_from,
            date_to=date_to,
        )
    )


@admin_payout_router.get("/reports", response_model=PayoutReportResponse)
def admin_payout_report(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutReportResponse:
    return PayoutReportResponse(**get_admin_payout_report(db, date_from, date_to))


@admin_payout_router.get(
    "/reconciliation",
    response_model=PaginatedPayoutReconciliationResponse,
)
def admin_payout_reconciliation_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    classification: Optional[str] = Query(default=None, max_length=32),
    execution_state: Optional[str] = Query(default=None, max_length=20),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    amount_from: Optional[Decimal] = Query(default=None),
    amount_to: Optional[Decimal] = Query(default=None),
    unresolved_only: bool = Query(default=False),
    sort: str = Query(default="created_desc", max_length=20),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedPayoutReconciliationResponse:
    if classification and classification not in {
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
    }:
        raise HTTPException(status_code=422, detail="Invalid reconciliation classification.")
    if amount_from is not None and amount_from < 0:
        raise HTTPException(status_code=422, detail="Minimum amount cannot be negative.")
    if amount_to is not None and amount_to < 0:
        raise HTTPException(status_code=422, detail="Maximum amount cannot be negative.")
    if amount_from is not None and amount_to is not None and amount_to < amount_from:
        raise HTTPException(status_code=422, detail="Maximum amount cannot be below minimum amount.")
    return PaginatedPayoutReconciliationResponse(
        **list_reconciliation_queue(
            db,
            page=page,
            page_size=page_size,
            classification=classification,
            execution_state=execution_state,
            seller_id=seller_id,
            date_from=date_from,
            date_to=date_to,
            amount_from=amount_from,
            amount_to=amount_to,
            unresolved_only=unresolved_only,
            sort=sort,
        )
    )


@admin_payout_router.get(
    "/reconciliation/summary",
    response_model=PayoutReconciliationSummaryResponse,
)
def admin_payout_reconciliation_summary(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutReconciliationSummaryResponse:
    return PayoutReconciliationSummaryResponse(
        **reconciliation_summary(db, date_from=date_from, date_to=date_to)
    )


@admin_payout_router.get(
    "/{payout_id}/reconciliation",
    response_model=PayoutReconciliationDetailResponse,
)
def admin_payout_reconciliation_detail(
    payout_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutReconciliationDetailResponse:
    return PayoutReconciliationDetailResponse(
        **inspect_payout_reconciliation(db, payout_id)
    )


@admin_payout_router.get(
    "/{payout_id}/detail",
)
def admin_payout_detail(
    payout_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    payout = get_admin_payout_request(db, payout_id)
    reconciliation = inspect_payout_reconciliation(db, payout_id)
    seller = db.get(SellerProfile, payout.seller_id)
    account = None
    if payout.payout_account_id:
        from app.models.payout import SellerPayoutAccount
        account = db.get(SellerPayoutAccount, payout.payout_account_id)
    audit_logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "payout_request", AuditLog.entity_id == str(payout_id))
        .order_by(AuditLog.created_at.desc())
    ).all()
    return {
        "payout": payout_request_dict(payout),
        "seller": {
            "id": payout.seller_id,
            "store_name": seller.store_name if seller else None,
            "store_slug": seller.store_slug if seller else None,
        },
        "destination": {
            "account_type": payout.account_type_snapshot,
            "masked_identifier": payout.destination_masked_snapshot,
        },
        "reconciliation": reconciliation,
        "audit_history": [
            {
                "id": row.id,
                "action": row.action,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in audit_logs
        ],
    }


@admin_payout_router.post(
    "/{payout_id}/reconciliation/resolve",
    response_model=PayoutReconciliationResolveResponse,
)
def admin_resolve_payout_reconciliation(
    payout_id: uuid.UUID,
    payload: PayoutReconciliationResolveRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutReconciliationResolveResponse:
    record = resolve_payout_reconciliation(
        db,
        admin=admin,
        payout_id=payout_id,
        resolution_action=payload.resolution_action,
        resolution_reason=payload.resolution_reason,
        evidence_reference=payload.evidence_reference,
        expected_classification=payload.expected_classification,
    )
    record_admin_audit(
        db,
        admin,
        "payout.reconciliation.resolve",
        "payout_request",
        payout_id,
        {
            "resolution_action": payload.resolution_action,
            "previous_classification": record["previous_classification"],
            "new_classification": record["new_classification"],
        },
        get_client_ip(request),
    )
    db.commit()
    return PayoutReconciliationResolveResponse(**record)


@admin_payout_router.get("/{payout_id}", response_model=PayoutRequestResponse)
def admin_get_payout_request(
    payout_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = get_admin_payout_request(db, payout_id)
    return PayoutRequestResponse(**payout_request_dict(payout))


@admin_payout_router.post("/{payout_id}/review", response_model=PayoutRequestResponse)
def admin_review_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutReviewRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = review_payout_request(db, admin=admin, payout_id=payout_id, reason=payload.reason)
    record_admin_audit(
        db,
        admin,
        "payout.request.review",
        "payout_request",
        payout.id,
        {"seller_id": str(payout.seller_id), "reason": payload.reason},
        get_client_ip(request),
    )
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@admin_payout_router.post("/{payout_id}/approve", response_model=PayoutRequestResponse)
def admin_approve_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutApproveRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = approve_payout_request(db, admin=admin, payout_id=payout_id, reason=payload.reason)
    record_admin_audit(
        db,
        admin,
        "payout.request.approve",
        "payout_request",
        payout.id,
        {"seller_id": str(payout.seller_id), "reason": payload.reason},
        get_client_ip(request),
    )
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@admin_payout_router.post("/{payout_id}/reject", response_model=PayoutRequestResponse)
def admin_reject_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutRejectRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = reject_payout_request(db, admin=admin, payout_id=payout_id, reason=payload.reason)
    record_admin_audit(
        db,
        admin,
        "payout.request.reject",
        "payout_request",
        payout.id,
        {"seller_id": str(payout.seller_id), "reason": payload.reason},
        get_client_ip(request),
    )
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@admin_payout_router.get(
    "/{payout_id}/attempts",
    response_model=list[PayoutExecutionAttemptResponse],
)
def admin_payout_attempts(
    payout_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PayoutExecutionAttemptResponse]:
    return [
        PayoutExecutionAttemptResponse(**attempt)
        for attempt in list_payout_execution_attempts(db, payout_id)
    ]


@admin_payout_router.post(
    "/{payout_id}/execute",
    response_model=PayoutExecutionAttemptResponse,
)
def admin_execute_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutExecutionRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutExecutionAttemptResponse:
    attempt = execute_payout_request(
        db,
        admin=admin,
        payout_id=payout_id,
        scenario=payload.scenario,
        idempotency_key=payload.idempotency_key,
    )
    record_admin_audit(
        db,
        admin,
        "payout.request.execute",
        "payout_request",
        payout_id,
        {
            "attempt_id": str(attempt.id),
            "scenario": payload.scenario,
            "simulated": True,
            "outcome": attempt.outcome,
        },
        get_client_ip(request),
    )
    db.commit()
    return PayoutExecutionAttemptResponse(**payout_attempt_dict(attempt))


@admin_payout_router.post(
    "/{payout_id}/retry",
    response_model=PayoutExecutionAttemptResponse,
)
def admin_retry_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutRetryRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutExecutionAttemptResponse:
    attempt = retry_payout_request(
        db,
        admin=admin,
        payout_id=payout_id,
        scenario=payload.scenario,
        idempotency_key=payload.idempotency_key,
    )
    record_admin_audit(
        db,
        admin,
        "payout.request.retry",
        "payout_request",
        payout_id,
        {
            "attempt_id": str(attempt.id),
            "scenario": payload.scenario,
            "simulated": True,
            "outcome": attempt.outcome,
        },
        get_client_ip(request),
    )
    db.commit()
    return PayoutExecutionAttemptResponse(**payout_attempt_dict(attempt))


@admin_payout_router.post(
    "/{payout_id}/reconcile",
    response_model=PayoutRequestResponse,
)
def admin_reconcile_payout_request(
    payout_id: uuid.UUID,
    payload: PayoutReconcileRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutRequestResponse:
    payout = reconcile_payout_request(
        db,
        admin=admin,
        payout_id=payout_id,
        outcome=payload.outcome,
        provider_reference=payload.provider_reference,
    )
    record_admin_audit(
        db,
        admin,
        "payout.request.reconcile",
        "payout_request",
        payout_id,
        {"outcome": payload.outcome, "provider_reference_present": bool(payload.provider_reference)},
        get_client_ip(request),
    )
    db.commit()
    return PayoutRequestResponse(**payout_request_dict(payout))


@admin_payout_account_router.get(
    "/verification",
    response_model=PaginatedPayoutAccountVerificationResponse,
)
def admin_list_payout_account_verification(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, max_length=20),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    account_type: Optional[str] = Query(default=None, max_length=16),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedPayoutAccountVerificationResponse:
    return PaginatedPayoutAccountVerificationResponse(
        **list_admin_payout_account_verification(
            db,
            page=page,
            page_size=page_size,
            status_filter=status,
            seller_id=seller_id,
            account_type=account_type,
        )
    )


@admin_payout_account_router.get(
    "/{account_id}",
    response_model=PayoutAccountResponse,
)
def admin_get_payout_account_verification(
    account_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    return PayoutAccountResponse(
        **get_admin_payout_account_verification(db, account_id)
    )


@admin_payout_account_router.post(
    "/{account_id}/approve",
    response_model=PayoutAccountResponse,
)
def admin_approve_payout_account_verification(
    account_id: uuid.UUID,
    payload: PayoutAccountApproveRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = approve_payout_account_verification(
        db,
        admin=admin,
        account_id=account_id,
        administrative_notes=payload.administrative_notes,
    )
    record_admin_audit(
        db,
        admin,
        "payout.account.verify.approve",
        "seller_payout_account",
        account.id,
        {"seller_id": str(account.seller_id), "notes": payload.administrative_notes},
        get_client_ip(request),
    )
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        seller_id=account.seller_id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@admin_payout_account_router.post(
    "/{account_id}/reject",
    response_model=PayoutAccountResponse,
)
def admin_reject_payout_account_verification(
    account_id: uuid.UUID,
    payload: PayoutAccountRejectRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PayoutAccountResponse:
    account = reject_payout_account_verification(
        db,
        admin=admin,
        account_id=account_id,
        reason=payload.reason,
        administrative_notes=payload.administrative_notes,
    )
    record_admin_audit(
        db,
        admin,
        "payout.account.verify.reject",
        "seller_payout_account",
        account.id,
        {"seller_id": str(account.seller_id), "reason": payload.reason},
        get_client_ip(request),
    )
    db.commit()
    return PayoutAccountResponse(
        id=account.id,
        seller_id=account.seller_id,
        account_type=account.account_type,
        display_name=account.display_name,
        bank_name=account.bank_name,
        masked_identifier=account.masked_identifier,
        verification_status=account.verification_status,
        is_default=account.is_default,
        is_active=account.is_active,
        verified_at=account.verified_at,
        verification_reason=account.verification_reason,
        deactivated_at=account.deactivated_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@admin_payout_account_router.get(
    "/{account_id}/history",
    response_model=PaginatedPayoutAccountVerificationHistoryResponse,
)
def admin_payout_account_verification_history(
    account_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedPayoutAccountVerificationHistoryResponse:
    return PaginatedPayoutAccountVerificationHistoryResponse(
        **list_payout_account_verification_history(
            db,
            account_id=account_id,
            page=page,
            page_size=page_size,
        )
    )
