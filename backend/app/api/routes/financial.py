import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin, require_approved_seller
from app.core.rate_limit import get_client_ip
from app.models.admin import Admin
from app.models.seller import SellerProfile
from app.schemas.financial import (
    CommissionConfigurationResponse,
    CommissionConfigurationUpdateRequest,
    CommissionReportResponse,
    PaginatedFinancialLedgerResponse,
    PaginatedSellerCommissionResponse,
    PaginatedSellerFinancialTransactionResponse,
    PaginatedSellerOrderCommissionResponse,
    SellerCommissionConfigurationResponse,
    SellerCommissionUpdateRequest,
    SellerFinancialSummaryResponse,
    SellerItemCommissionListResponse,
)
from app.services.catalog_service import record_admin_audit
from app.services.financial_service import (
    get_admin_commission_configuration,
    get_admin_commission_report,
    get_admin_seller_commission,
    get_seller_financial_summary,
    list_admin_financial_ledger,
    list_admin_seller_commissions,
    list_seller_financial_transactions,
    list_seller_order_commissions,
    list_seller_order_item_commissions,
    remove_seller_commission,
    set_seller_commission,
    update_global_commission,
)


seller_financial_router = APIRouter(prefix="/seller/financial", tags=["Seller Financials"])
admin_financial_router = APIRouter(prefix="/admin/financial", tags=["Admin Financials"])


@seller_financial_router.get("/summary", response_model=SellerFinancialSummaryResponse)
def seller_financial_summary(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerFinancialSummaryResponse:
    return SellerFinancialSummaryResponse(
        **get_seller_financial_summary(
            db=db,
            seller=seller,
            date_from=date_from,
            date_to=date_to,
        )
    )


@seller_financial_router.get(
    "/transactions",
    response_model=PaginatedSellerFinancialTransactionResponse,
)
def seller_financial_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PaginatedSellerFinancialTransactionResponse:
    return PaginatedSellerFinancialTransactionResponse(
        **list_seller_financial_transactions(
            db=db,
            seller=seller,
            page=page,
            page_size=page_size,
            date_from=date_from,
            date_to=date_to,
        )
    )


@seller_financial_router.get(
    "/orders",
    response_model=PaginatedSellerOrderCommissionResponse,
)
def seller_order_commissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PaginatedSellerOrderCommissionResponse:
    return PaginatedSellerOrderCommissionResponse(
        **list_seller_order_commissions(
            db=db,
            seller=seller,
            page=page,
            page_size=page_size,
            date_from=date_from,
            date_to=date_to,
        )
    )


@seller_financial_router.get(
    "/order-items",
    response_model=SellerItemCommissionListResponse,
)
def seller_order_item_commissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerItemCommissionListResponse:
    return SellerItemCommissionListResponse(
        **list_seller_order_item_commissions(
            db=db,
            seller=seller,
            page=page,
            page_size=page_size,
            date_from=date_from,
            date_to=date_to,
        )
    )


@admin_financial_router.get(
    "/commission",
    response_model=CommissionConfigurationResponse,
)
def admin_get_commission(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CommissionConfigurationResponse:
    return CommissionConfigurationResponse(**get_admin_commission_configuration(db))


@admin_financial_router.put(
    "/commission",
    response_model=CommissionConfigurationResponse,
)
def admin_update_commission(
    payload: CommissionConfigurationUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CommissionConfigurationResponse:
    config = update_global_commission(
        db=db,
        admin=admin,
        rate=payload.default_rate,
        reason=payload.reason,
    )
    record_admin_audit(
        db=db,
        admin=admin,
        action="commission.global.update",
        entity_type="commission_configuration",
        entity_id="default",
        details={"default_rate": str(payload.default_rate), "reason": payload.reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return CommissionConfigurationResponse(**get_admin_commission_configuration(db))


@admin_financial_router.get(
    "/sellers",
    response_model=PaginatedSellerCommissionResponse,
)
def admin_list_seller_commissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedSellerCommissionResponse:
    return PaginatedSellerCommissionResponse(
        **list_admin_seller_commissions(
            db=db,
            page=page,
            page_size=page_size,
            search=search,
        )
    )


@admin_financial_router.get(
    "/sellers/{seller_id}/commission",
    response_model=SellerCommissionConfigurationResponse,
)
def admin_get_seller_commission(
    seller_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SellerCommissionConfigurationResponse:
    return SellerCommissionConfigurationResponse(
        **get_admin_seller_commission(db=db, seller_id=seller_id)
    )


@admin_financial_router.put(
    "/sellers/{seller_id}/commission",
    response_model=SellerCommissionConfigurationResponse,
)
def admin_update_seller_commission(
    seller_id: uuid.UUID,
    payload: SellerCommissionUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SellerCommissionConfigurationResponse:
    seller = db.get(SellerProfile, seller_id)
    if not seller:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found.")
    set_seller_commission(
        db=db,
        admin=admin,
        seller=seller,
        rate=payload.rate,
        reason=payload.reason,
    )
    record_admin_audit(
        db=db,
        admin=admin,
        action="commission.seller.override.set",
        entity_type="seller_commission_override",
        entity_id=seller.id,
        details={"seller_id": str(seller.id), "rate": str(payload.rate), "reason": payload.reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return SellerCommissionConfigurationResponse(
        **get_admin_seller_commission(db=db, seller_id=seller.id)
    )


@admin_financial_router.delete(
    "/sellers/{seller_id}/commission",
)
def admin_remove_seller_commission(
    seller_id: uuid.UUID,
    request: Request,
    reason: Optional[str] = Query(default=None, max_length=2000),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    seller = db.get(SellerProfile, seller_id)
    if not seller:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found.")
    remove_seller_commission(db=db, admin=admin, seller=seller, reason=reason)
    record_admin_audit(
        db=db,
        admin=admin,
        action="commission.seller.override.remove",
        entity_type="seller_commission_override",
        entity_id=seller.id,
        details={"seller_id": str(seller.id), "reason": reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"message": "Seller commission override removed.", "seller_id": str(seller.id)}


@admin_financial_router.get(
    "/ledger",
    response_model=PaginatedFinancialLedgerResponse,
)
def admin_financial_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    order_id: Optional[uuid.UUID] = Query(default=None),
    transaction_type: Optional[str] = Query(default=None, max_length=32),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedFinancialLedgerResponse:
    return PaginatedFinancialLedgerResponse(
        **list_admin_financial_ledger(
            db=db,
            page=page,
            page_size=page_size,
            seller_id=seller_id,
            order_id=order_id,
            transaction_type=transaction_type,
            date_from=date_from,
            date_to=date_to,
        )
    )


@admin_financial_router.get(
    "/commission/report",
    response_model=CommissionReportResponse,
)
def admin_commission_report(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CommissionReportResponse:
    return CommissionReportResponse(
        **get_admin_commission_report(
            db=db,
            date_from=date_from,
            date_to=date_to,
        )
    )
