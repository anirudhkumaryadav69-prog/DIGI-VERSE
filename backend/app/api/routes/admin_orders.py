import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.core.rate_limit import get_client_ip
from app.models.admin import Admin
from app.models.enums import OrderPaymentStatus, OrderStatus
from app.schemas.commerce import (
    AdminOrderResponse,
    AdminOrderStatisticsResponse,
    AdminOrderStatusUpdateRequest,
    PaginatedAdminOrderResponse,
)
from app.services.commerce_service import (
    get_admin_order,
    get_admin_order_statistics,
    list_admin_orders,
    update_admin_order_status,
)

router = APIRouter(prefix="/admin/orders", tags=["Admin Order Management"])


@router.get("/statistics", response_model=AdminOrderStatisticsResponse)
def admin_orders_statistics(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOrderStatisticsResponse:
    return get_admin_order_statistics(db=db)


@router.get("", response_model=PaginatedAdminOrderResponse)
def admin_list_all_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    status: Optional[OrderStatus] = Query(default=None),
    payment_status: Optional[OrderPaymentStatus] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAdminOrderResponse:
    return list_admin_orders(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        order_status=status,
        payment_status=payment_status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{order_id}", response_model=AdminOrderResponse)
def admin_get_single_order(
    order_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOrderResponse:
    return get_admin_order(db=db, order_id=order_id)


@router.patch("/{order_id}/status", response_model=AdminOrderResponse)
def admin_change_order_status(
    order_id: uuid.UUID,
    payload: AdminOrderStatusUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOrderResponse:
    updated = update_admin_order_status(
        db=db,
        admin=admin,
        order_id=order_id,
        new_status=payload.status,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated
