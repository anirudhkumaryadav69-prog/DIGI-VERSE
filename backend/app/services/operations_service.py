import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import Select, desc, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.logging import log_background_event

from app.models.admin import Admin, AuditLog
from app.models.auth import AuthSession
from app.models.campaign import (
    CampaignRecipient,
    EmailCampaign,
    MessageTemplate,
    WhatsAppCampaign,
    WorkerHeartbeat,
)
from app.models.catalog import Category, Product, Sale
from app.models.content import AdvertisementVideo, Banner
from app.models.customer import Customer, CustomerActivity
from app.models.enums import (
    AccountStatus,
    AdDisplayPosition,
    CampaignStatus,
    DeliveryStatus,
    MessageChannel,
    OrderPaymentStatus,
    OrderStatus,
    PaymentStatus,
)
from app.models.order import DownloadRecord, Order, OrderItem, Payment
from app.models.settings import StoreSetting
from app.schemas.operations import (
    AdminCustomerSummaryResponse,
    AdVideoCreateRequest,
    AdVideoResponse,
    AdVideoUpdateRequest,
    AuditLogEntryResponse,
    BannerCreateRequest,
    BannerResponse,
    BannerUpdateRequest,
    BestSellingProductMetric,
    CampaignDetailResponse,
    CampaignLaunchResponse,
    CampaignRecipientSummary,
    CustomerActivityItemResponse,
    DashboardAnalyticsResponse,
    EmailCampaignCreateRequest,
    EmailCampaignResponse,
    MarketingWorkerStatusResponse,
    MessageTemplateCreateRequest,
    MessageTemplateResponse,
    MessageTemplateUpdateRequest,
    MostDownloadedProductMetric,
    PaginatedAdminCustomerResponse,
    PaginatedAuditLogResponse,
    PROTECTED_SYSTEM_SETTING_KEYS,
    StoreSettingResponse,
    StoreSettingsBatchUpdateRequest,
    StoreSettingUpsertRequest,
    TimeSeriesPoint,
    TopCategoryMetric,
    WhatsAppCampaignCreateRequest,
    WhatsAppCampaignResponse,
    WorkerHeartbeatResponse,
)
from app.services.campaign_worker import (
    _check_live_recipient_consent,
    _execute_provider_send,
    _persist_job_outcome,
    claim_recipient_batch,
    materialize_campaign_recipients,
    process_campaigns_in_session,
    recompute_campaign_status,
)
from app.services.catalog_service import compute_product_pricing, record_admin_audit
from app.services.webhook_service import can_transition_delivery_status


def _q(val: Any) -> Decimal:
    return Decimal(str(val or "0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ===========================================================================
# 1. ADVANCED ADMIN DASHBOARD & SQL ANALYTICS
# ===========================================================================


def get_advanced_dashboard_overview(
    db: Session,
    admin: Admin,
    days_window: int = 30,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=max(1, days_window))

    cust_row = db.execute(
        select(
            func.count(Customer.id).label("total_customers"),
            func.count(Customer.id).filter(Customer.created_at >= window_start).label("new_customers"),
        )
    ).one()
    total_customers = int(cust_row.total_customers or 0)
    new_customers = int(cust_row.new_customers or 0)

    total_categories = db.scalar(select(func.count(Category.id))) or 0

    prod_row = db.execute(
        select(
            func.count(Product.id).label("total_products"),
            func.count(Product.id).filter(Product.is_active.is_(True)).label("active_products"),
        )
    ).one()
    total_products = int(prod_row.total_products or 0)
    active_products = int(prod_row.active_products or 0)
    inactive_products = total_products - active_products

    ord_row = db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.PENDING).label("pending_orders"),
            func.count(Order.id).filter(Order.payment_status == OrderPaymentStatus.PAID).label("paid_orders"),
            func.coalesce(
                func.sum(Order.total_amount).filter(Order.payment_status == OrderPaymentStatus.PAID),
                Decimal("0.00"),
            ).label("revenue_raw"),
        )
    ).one()
    total_orders = int(ord_row.total_orders or 0)
    pending_orders = int(ord_row.pending_orders or 0)
    paid_orders_count = int(ord_row.paid_orders or 0)
    revenue_raw = ord_row.revenue_raw or Decimal("0.00")
    total_sales_revenue = float(_q(revenue_raw))

    pay_row = db.execute(
        select(
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == PaymentStatus.CAPTURED),
                Decimal("0.00"),
            ).label("captured_raw"),
            func.count(Payment.id)
            .filter(Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.AUTHORIZED]))
            .label("pending_payments"),
            func.count(Payment.id).filter(Payment.status == PaymentStatus.FAILED).label("failed_payments"),
            func.count(Payment.id).filter(Payment.status == PaymentStatus.REFUNDED).label("refunded_payments"),
        )
    ).one()
    captured_raw = pay_row.captured_raw or Decimal("0.00")
    total_captured_revenue = float(_q(captured_raw))
    pending_payments = int(pay_row.pending_payments or 0)
    failed_payments = int(pay_row.failed_payments or 0)
    refunded_payments = int(pay_row.refunded_payments or 0)

    avg_order_val = (
        float(_q(Decimal(str(revenue_raw)) / Decimal(str(paid_orders_count))))
        if paid_orders_count > 0
        else 0.0
    )
    total_downloads = db.scalar(select(func.count(DownloadRecord.id))) or 0

    active_sales_cnt = (
        db.scalar(
            select(func.count(Sale.id)).where(
                Sale.is_active.is_(True),
                Sale.starts_at <= now,
                Sale.expires_at > now,
            )
        )
        or 0
    )
    active_banners_cnt = (
        db.scalar(select(func.count(Banner.id)).where(Banner.is_active.is_(True))) or 0
    )
    active_email_camp = (
        db.scalar(
            select(func.count(EmailCampaign.id)).where(
                EmailCampaign.status.in_(
                    [CampaignStatus.SCHEDULED, CampaignStatus.SENDING, CampaignStatus.COMPLETED]
                )
            )
        )
        or 0
    )
    active_wa_camp = (
        db.scalar(
            select(func.count(WhatsAppCampaign.id)).where(
                WhatsAppCampaign.status.in_(
                    [CampaignStatus.SCHEDULED, CampaignStatus.SENDING, CampaignStatus.COMPLETED]
                )
            )
        )
        or 0
    )
    active_promotional_campaigns = (
        active_sales_cnt + active_banners_cnt + active_email_camp + active_wa_camp
    )

    recent_customers = db.scalars(
        select(Customer).order_by(Customer.created_at.desc()).limit(5)
    ).all()
    recent_orders = db.scalars(
        select(Order)
        .options(selectinload(Order.customer))
        .order_by(Order.created_at.desc())
        .limit(5)
    ).all()
    recent_products = db.scalars(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.sales))
        .order_by(Product.created_at.desc())
        .limit(5)
    ).all()
    recent_logs = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    ).all()

    return {
        "admin": admin.username,
        "metrics": {
            "total_customers": total_customers,
            "new_customers": new_customers,
            "total_categories": total_categories,
            "total_products": total_products,
            "active_products": active_products,
            "inactive_products": inactive_products,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_sales_revenue": total_sales_revenue,
            "total_captured_revenue": total_captured_revenue,
            "pending_payments": pending_payments,
            "failed_payments": failed_payments,
            "refunded_payments": refunded_payments,
            "average_order_value": avg_order_val,
            "total_downloads": total_downloads,
            "active_promotional_campaigns": active_promotional_campaigns,
        },
        "recent_registrations": [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "email": c.email,
                "is_phone_verified": c.is_phone_verified,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent_customers
        ],
        "recent_orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "customer_name": o.customer.full_name if o.customer else "Customer",
                "customer_email": o.customer.email if o.customer else "",
                "total_amount": float(_q(o.total_amount)),
                "currency": o.currency,
                "status": o.status.value,
                "payment_status": o.payment_status.value,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
        "recent_products": [
            {
                "id": str(p.id),
                "name": p.name,
                "slug": p.slug,
                "category_name": p.category.name if p.category else "Uncategorized",
                "original_price": float(_q(p.original_price)),
                "effective_price": float(compute_product_pricing(p)[0]),
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat(),
            }
            for p in recent_products
        ],
        "recent_audit_logs": [
            {
                "id": str(entry.id),
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in recent_logs
        ],
    }


def _aggregate_sales_by_trunc(
    db: Session,
    unit: str,
    date_from: datetime,
    date_to: datetime,
) -> list[TimeSeriesPoint]:
    bucket = func.date_trunc(unit, Order.created_at).label("bucket")
    order_rows = db.execute(
        select(
            bucket,
            func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("rev"),
            func.count(Order.id).label("cnt"),
        )
        .where(
            Order.payment_status == OrderPaymentStatus.PAID,
            Order.created_at >= date_from,
            Order.created_at <= date_to,
        )
        .group_by(bucket)
        .order_by(bucket.asc())
    ).all()

    cust_bucket = func.date_trunc(unit, Customer.created_at).label("cbucket")
    cust_rows = {
        row.cbucket.date().isoformat() if hasattr(row.cbucket, "date") else str(row.cbucket): int(row.ccnt)
        for row in db.execute(
            select(cust_bucket, func.count(Customer.id).label("ccnt"))
            .where(Customer.created_at >= date_from, Customer.created_at <= date_to)
            .group_by(cust_bucket)
        ).all()
        if row.cbucket is not None
    }

    points: list[TimeSeriesPoint] = []
    for row in order_rows:
        if row.bucket is None:
            continue
        label = row.bucket.date().isoformat() if hasattr(row.bucket, "date") else str(row.bucket)
        points.append(
            TimeSeriesPoint(
                period=label,
                revenue=_q(row.rev),
                order_count=int(row.cnt),
                new_customers=cust_rows.get(label, 0),
            )
        )
    return points


def get_dashboard_analytics(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> DashboardAnalyticsResponse:
    now = datetime.now(timezone.utc)
    resolved_to = date_to or now
    resolved_from = date_from or (resolved_to - timedelta(days=90))

    daily = _aggregate_sales_by_trunc(db, "day", resolved_from, resolved_to)
    weekly = _aggregate_sales_by_trunc(db, "week", resolved_from, resolved_to)
    monthly = _aggregate_sales_by_trunc(db, "month", resolved_from, resolved_to)

    # Best-selling products (SQL aggregation over paid orders)
    best_rows = db.execute(
        select(
            OrderItem.product_id,
            OrderItem.product_name_snapshot,
            Product.slug,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
            func.coalesce(
                func.sum(OrderItem.purchase_price * OrderItem.quantity), Decimal("0.00")
            ).label("rev"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .where(
            Order.payment_status == OrderPaymentStatus.PAID,
            Order.created_at >= resolved_from,
            Order.created_at <= resolved_to,
        )
        .group_by(OrderItem.product_id, OrderItem.product_name_snapshot, Product.slug)
        .order_by(desc("units"), desc("rev"))
        .limit(10)
    ).all()

    best_products = [
        BestSellingProductMetric(
            product_id=r.product_id,
            product_name=r.product_name_snapshot,
            product_slug=r.slug,
            units_sold=int(r.units),
            total_revenue=_q(r.rev),
        )
        for r in best_rows
    ]

    # Top-performing categories
    cat_rows = db.execute(
        select(
            Category.id,
            Category.name,
            Category.slug,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
            func.coalesce(
                func.sum(OrderItem.purchase_price * OrderItem.quantity), Decimal("0.00")
            ).label("rev"),
        )
        .join(Product, Product.category_id == Category.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.payment_status == OrderPaymentStatus.PAID,
            Order.created_at >= resolved_from,
            Order.created_at <= resolved_to,
        )
        .group_by(Category.id, Category.name, Category.slug)
        .order_by(desc("rev"), desc("units"))
        .limit(10)
    ).all()

    top_categories = [
        TopCategoryMetric(
            category_id=r.id,
            category_name=r.name,
            category_slug=r.slug,
            units_sold=int(r.units),
            total_revenue=_q(r.rev),
        )
        for r in cat_rows
    ]

    # Most downloaded products
    dl_rows = db.execute(
        select(
            DownloadRecord.product_id,
            func.coalesce(Product.name, "Digital Product").label("pname"),
            Product.slug,
            func.count(DownloadRecord.id).label("dl_cnt"),
        )
        .outerjoin(Product, DownloadRecord.product_id == Product.id)
        .where(
            DownloadRecord.downloaded_at >= resolved_from,
            DownloadRecord.downloaded_at <= resolved_to,
        )
        .group_by(DownloadRecord.product_id, Product.name, Product.slug)
        .order_by(desc("dl_cnt"))
        .limit(10)
    ).all()

    most_downloaded = [
        MostDownloadedProductMetric(
            product_id=r.product_id,
            product_name=r.pname,
            product_slug=r.slug,
            download_count=int(r.dl_cnt),
        )
        for r in dl_rows
    ]

    # Recent customer activity
    act_rows = db.scalars(
        select(CustomerActivity)
        .options(selectinload(CustomerActivity.customer))
        .order_by(CustomerActivity.created_at.desc())
        .limit(15)
    ).all()

    recent_activity = [
        CustomerActivityItemResponse(
            id=a.id,
            customer_id=a.customer_id,
            customer_name=a.customer.full_name if a.customer else "Customer",
            customer_email=a.customer.email if a.customer else "",
            activity_type=a.activity_type,
            product_id=a.product_id,
            category_id=a.category_id,
            metadata=a.details,
            created_at=a.created_at,
        )
        for a in act_rows
    ]

    return DashboardAnalyticsResponse(
        date_from=resolved_from,
        date_to=resolved_to,
        daily_sales=daily,
        weekly_sales=weekly,
        monthly_sales=monthly,
        best_selling_products=best_products,
        top_categories=top_categories,
        most_downloaded_products=most_downloaded,
        recent_customer_activity=recent_activity,
    )


# ===========================================================================
# 2. ADMIN CUSTOMER MANAGEMENT
# ===========================================================================


def list_admin_customers(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    account_status: Optional[AccountStatus] = None,
    is_phone_verified: Optional[bool] = None,
) -> PaginatedAdminCustomerResponse:
    conds = []
    if search and search.strip():
        q = f"%{search.strip()}%"
        conds.append(
            or_(
                Customer.full_name.ilike(q),
                Customer.email.ilike(q),
                Customer.phone_number.ilike(q),
            )
        )
    if account_status is not None:
        conds.append(Customer.account_status == account_status)
    if is_phone_verified is not None:
        conds.append(Customer.is_phone_verified.is_(is_phone_verified))

    total = db.scalar(select(func.count(Customer.id)).where(*conds)) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    customers = db.scalars(
        select(Customer)
        .where(*conds)
        .order_by(Customer.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    c_ids = [c.id for c in customers]
    order_stats: dict[uuid.UUID, tuple[int, Decimal]] = {}
    if c_ids:
        rows = db.execute(
            select(
                Order.customer_id,
                func.count(Order.id).label("cnt"),
                func.coalesce(
                    func.sum(Order.total_amount).filter(
                        Order.payment_status == OrderPaymentStatus.PAID
                    ),
                    Decimal("0.00"),
                ).label("spent"),
            )
            .where(Order.customer_id.in_(c_ids))
            .group_by(Order.customer_id)
        ).all()
        for r in rows:
            order_stats[r.customer_id] = (int(r.cnt), _q(r.spent))

    items = [
        AdminCustomerSummaryResponse(
            id=c.id,
            full_name=c.full_name,
            email=c.email,
            phone_number=c.phone_number,
            is_email_verified=c.is_email_verified,
            is_phone_verified=c.is_phone_verified,
            account_status=c.account_status,
            email_marketing_consent=c.email_marketing_consent,
            whatsapp_marketing_consent=c.whatsapp_marketing_consent,
            order_count=order_stats.get(c.id, (0, Decimal("0.00")))[0],
            total_spent=order_stats.get(c.id, (0, Decimal("0.00")))[1],
            last_login_at=c.last_login_at,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in customers
    ]

    return PaginatedAdminCustomerResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def update_admin_customer_status(
    db: Session,
    admin: Admin,
    customer_id: uuid.UUID,
    new_status: AccountStatus,
    ip_address: Optional[str] = None,
) -> AdminCustomerSummaryResponse:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    old_status = customer.account_status
    customer.account_status = new_status

    # Revoke active sessions immediately if the account is suspended or deactivated
    if new_status != AccountStatus.ACTIVE:
        now = datetime.now(timezone.utc)
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.customer_id == customer.id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoke_reason=f"admin_account_{new_status.value}")
        )

    record_admin_audit(
        db=db,
        admin=admin,
        action="customer.status_updated",
        entity_type="customer",
        entity_id=customer.id,
        details={"previous_status": old_status.value, "new_status": new_status.value},
        ip_address=ip_address,
    )
    db.flush()

    order_cnt = (
        db.scalar(select(func.count(Order.id)).where(Order.customer_id == customer.id)) or 0
    )
    spent = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), Decimal("0.00"))).where(
            Order.customer_id == customer.id,
            Order.payment_status == OrderPaymentStatus.PAID,
        )
    ) or Decimal("0.00")

    return AdminCustomerSummaryResponse(
        id=customer.id,
        full_name=customer.full_name,
        email=customer.email,
        phone_number=customer.phone_number,
        is_email_verified=customer.is_email_verified,
        is_phone_verified=customer.is_phone_verified,
        account_status=customer.account_status,
        email_marketing_consent=customer.email_marketing_consent,
        whatsapp_marketing_consent=customer.whatsapp_marketing_consent,
        order_count=order_cnt,
        total_spent=_q(spent),
        last_login_at=customer.last_login_at,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


# ===========================================================================
# 3. PROMOTIONAL BANNERS MANAGEMENT
# ===========================================================================


def list_admin_banners(db: Session) -> list[BannerResponse]:
    rows = db.scalars(
        select(Banner).order_by(Banner.display_priority.desc(), Banner.created_at.desc())
    ).all()
    return [BannerResponse.model_validate(b) for b in rows]


def create_admin_banner(
    db: Session,
    admin: Admin,
    payload: BannerCreateRequest,
    ip_address: Optional[str] = None,
) -> BannerResponse:
    banner = Banner(**payload.model_dump())
    db.add(banner)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="banner.created",
        entity_type="banner",
        entity_id=banner.id,
        details={"heading": banner.heading, "is_active": banner.is_active},
        ip_address=ip_address,
    )
    db.flush()
    return BannerResponse.model_validate(banner)


def update_admin_banner(
    db: Session,
    admin: Admin,
    banner_id: uuid.UUID,
    payload: BannerUpdateRequest,
    ip_address: Optional[str] = None,
) -> BannerResponse:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found.")

    updates = payload.model_dump(exclude_unset=True)
    new_starts = updates.get("starts_at", banner.starts_at)
    new_ends = updates.get("ends_at", banner.ends_at)
    if new_starts and new_ends and new_ends <= new_starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Banner end date must be after start date.",
        )

    for k, v in updates.items():
        setattr(banner, k, v)

    record_admin_audit(
        db=db,
        admin=admin,
        action="banner.updated",
        entity_type="banner",
        entity_id=banner.id,
        details={"heading": banner.heading, "is_active": banner.is_active},
        ip_address=ip_address,
    )
    db.flush()
    return BannerResponse.model_validate(banner)


def delete_admin_banner(
    db: Session,
    admin: Admin,
    banner_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> None:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found.")

    heading = banner.heading
    db.delete(banner)
    record_admin_audit(
        db=db,
        admin=admin,
        action="banner.deleted",
        entity_type="banner",
        entity_id=banner_id,
        details={"heading": heading},
        ip_address=ip_address,
    )
    db.flush()


def list_public_banners(db: Session) -> list[BannerResponse]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Banner)
        .where(
            Banner.is_active.is_(True),
            or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
            or_(Banner.ends_at.is_(None), Banner.ends_at > now),
        )
        .order_by(Banner.display_priority.desc(), Banner.created_at.desc())
    ).all()
    return [BannerResponse.model_validate(b) for b in rows]


# ===========================================================================
# 4. ADVERTISEMENT VIDEOS MANAGEMENT
# ===========================================================================


def list_admin_videos(db: Session) -> list[AdVideoResponse]:
    rows = db.scalars(
        select(AdvertisementVideo).order_by(
            AdvertisementVideo.display_priority.desc(),
            AdvertisementVideo.created_at.desc(),
        )
    ).all()
    return [AdVideoResponse.model_validate(v) for v in rows]


def create_admin_video(
    db: Session,
    admin: Admin,
    payload: AdVideoCreateRequest,
    ip_address: Optional[str] = None,
) -> AdVideoResponse:
    video = AdvertisementVideo(**payload.model_dump())
    db.add(video)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="video.created",
        entity_type="advertisement_video",
        entity_id=video.id,
        details={
            "title": video.title,
            "display_position": video.display_position.value,
            "is_active": video.is_active,
        },
        ip_address=ip_address,
    )
    db.flush()
    return AdVideoResponse.model_validate(video)


def update_admin_video(
    db: Session,
    admin: Admin,
    video_id: uuid.UUID,
    payload: AdVideoUpdateRequest,
    ip_address: Optional[str] = None,
) -> AdVideoResponse:
    video = db.get(AdvertisementVideo, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement video not found."
        )

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(video, k, v)

    record_admin_audit(
        db=db,
        admin=admin,
        action="video.updated",
        entity_type="advertisement_video",
        entity_id=video.id,
        details={"title": video.title, "is_active": video.is_active},
        ip_address=ip_address,
    )
    db.flush()
    return AdVideoResponse.model_validate(video)


def delete_admin_video(
    db: Session,
    admin: Admin,
    video_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> None:
    video = db.get(AdvertisementVideo, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement video not found."
        )

    title = video.title
    db.delete(video)
    record_admin_audit(
        db=db,
        admin=admin,
        action="video.deleted",
        entity_type="advertisement_video",
        entity_id=video_id,
        details={"title": title},
        ip_address=ip_address,
    )
    db.flush()


def list_public_videos(
    db: Session, position: Optional[AdDisplayPosition] = None
) -> list[AdVideoResponse]:
    conds = [AdvertisementVideo.is_active.is_(True)]
    if position is not None:
        conds.append(AdvertisementVideo.display_position == position)
    rows = db.scalars(
        select(AdvertisementVideo)
        .where(*conds)
        .order_by(
            AdvertisementVideo.display_priority.desc(),
            AdvertisementVideo.created_at.desc(),
        )
    ).all()
    return [AdVideoResponse.model_validate(v) for v in rows]


# ===========================================================================
# 5. MARKETING AUTOMATION: MESSAGE TEMPLATES, EMAIL & WHATSAPP CAMPAIGNS
# ===========================================================================


def list_message_templates(
    db: Session, channel: Optional[MessageChannel] = None
) -> list[MessageTemplateResponse]:
    stmt: Select = select(MessageTemplate)
    if channel is not None:
        stmt = stmt.where(MessageTemplate.channel == channel)
    rows = db.scalars(stmt.order_by(MessageTemplate.created_at.desc())).all()
    return [MessageTemplateResponse.model_validate(t) for t in rows]


def create_message_template(
    db: Session,
    admin: Admin,
    payload: MessageTemplateCreateRequest,
    ip_address: Optional[str] = None,
) -> MessageTemplateResponse:
    dup = db.scalar(
        select(MessageTemplate).where(
            func.lower(MessageTemplate.name) == payload.name.lower(),
            MessageTemplate.channel == payload.channel,
        )
    )
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A message template with this name and channel already exists.",
        )

    tpl = MessageTemplate(
        name=payload.name,
        channel=payload.channel,
        subject=payload.subject,
        content=payload.content,
    )
    db.add(tpl)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="template.created",
        entity_type="message_template",
        entity_id=tpl.id,
        details={"name": tpl.name, "channel": tpl.channel.value},
        ip_address=ip_address,
    )
    db.flush()
    return MessageTemplateResponse.model_validate(tpl)


def update_message_template(
    db: Session,
    admin: Admin,
    template_id: uuid.UUID,
    payload: MessageTemplateUpdateRequest,
    ip_address: Optional[str] = None,
) -> MessageTemplateResponse:
    tpl = db.get(MessageTemplate, template_id)
    if not tpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message template not found."
        )

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        dup = db.scalar(
            select(MessageTemplate).where(
                func.lower(MessageTemplate.name) == updates["name"].lower(),
                MessageTemplate.channel == tpl.channel,
                MessageTemplate.id != tpl.id,
            )
        )
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A message template with this name and channel already exists.",
            )

    for k, v in updates.items():
        setattr(tpl, k, v)

    record_admin_audit(
        db=db,
        admin=admin,
        action="template.updated",
        entity_type="message_template",
        entity_id=tpl.id,
        details={"name": tpl.name, "channel": tpl.channel.value},
        ip_address=ip_address,
    )
    db.flush()
    return MessageTemplateResponse.model_validate(tpl)



def delete_message_template(
    db: Session,
    admin: Admin,
    template_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> None:
    tpl = db.get(MessageTemplate, template_id)
    if not tpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message template not found."
        )
    name = tpl.name
    db.delete(tpl)
    record_admin_audit(
        db=db,
        admin=admin,
        action="template.deleted",
        entity_type="message_template",
        entity_id=template_id,
        details={"name": name},
        ip_address=ip_address,
    )
    db.flush()


def _compute_recipient_counts(recs: list[CampaignRecipient]) -> dict[str, int]:
    counts: dict[str, int] = {
        "recipient_count": len(recs),
        "queued_count": 0,
        "processing_count": 0,
        "retrying_count": 0,
        "accepted_count": 0,
        "delivered_count": 0,
        "read_count": 0,
        "bounced_count": 0,
        "suppressed_count": 0,
        "skipped_count": 0,
        "unresolved_count": 0,
        "sent_count": 0,
        "failed_count": 0,
    }
    for r in recs:
        st = r.delivery_status
        if st == DeliveryStatus.QUEUED:
            counts["queued_count"] += 1
        elif st == DeliveryStatus.PROCESSING:
            counts["processing_count"] += 1
        elif st == DeliveryStatus.RETRYING:
            counts["retrying_count"] += 1
        elif st == DeliveryStatus.ACCEPTED:
            counts["accepted_count"] += 1
            counts["sent_count"] += 1
        elif st == DeliveryStatus.SENT:
            counts["sent_count"] += 1
        elif st == DeliveryStatus.DELIVERED:
            counts["delivered_count"] += 1
            counts["sent_count"] += 1
        elif st == DeliveryStatus.READ:
            counts["read_count"] += 1
            counts["sent_count"] += 1
        elif st == DeliveryStatus.BOUNCED:
            counts["bounced_count"] += 1
            counts["failed_count"] += 1
        elif st == DeliveryStatus.SUPPRESSED:
            counts["suppressed_count"] += 1
            counts["failed_count"] += 1
        elif st == DeliveryStatus.FAILED:
            counts["failed_count"] += 1
        elif st == DeliveryStatus.SKIPPED:
            counts["skipped_count"] += 1
        elif st == DeliveryStatus.UNRESOLVED:
            counts["unresolved_count"] += 1
    return counts


def _to_email_campaign_response(c: EmailCampaign) -> EmailCampaignResponse:
    counts = _compute_recipient_counts(c.recipients or [])
    return EmailCampaignResponse(
        id=c.id,
        name=c.name,
        subject=c.subject,
        content=c.content,
        template_id=c.template_id,
        audience_criteria=c.audience_criteria,
        status=c.status,
        scheduled_for=c.scheduled_for,
        queued_at=c.queued_at,
        started_at=c.started_at,
        created_at=c.created_at,
        completed_at=c.completed_at,
        **counts,
    )


def _to_whatsapp_campaign_response(c: WhatsAppCampaign) -> WhatsAppCampaignResponse:
    counts = _compute_recipient_counts(c.recipients or [])
    return WhatsAppCampaignResponse(
        id=c.id,
        name=c.name,
        content=c.content,
        approved_template_name=c.approved_template_name,
        template_id=c.template_id,
        audience_criteria=c.audience_criteria,
        status=c.status,
        scheduled_for=c.scheduled_for,
        queued_at=c.queued_at,
        started_at=c.started_at,
        created_at=c.created_at,
        completed_at=c.completed_at,
        **counts,
    )


def list_email_campaigns(db: Session) -> list[EmailCampaignResponse]:
    rows = db.scalars(
        select(EmailCampaign)
        .options(selectinload(EmailCampaign.recipients))
        .order_by(EmailCampaign.created_at.desc())
        .execution_options(populate_existing=True)
    ).all()
    return [_to_email_campaign_response(c) for c in rows]


def create_email_campaign(
    db: Session,
    admin: Admin,
    payload: EmailCampaignCreateRequest,
    ip_address: Optional[str] = None,
) -> EmailCampaignResponse:
    if payload.template_id:
        tpl = db.get(MessageTemplate, payload.template_id)
        if not tpl or tpl.channel != MessageChannel.EMAIL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced template does not exist or is not an email template.",
            )

    camp = EmailCampaign(
        name=payload.name,
        subject=payload.subject,
        content=payload.content,
        template_id=payload.template_id,
        audience_criteria=payload.audience_criteria,
        status=CampaignStatus.DRAFT,
    )
    db.add(camp)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="campaign.email_created",
        entity_type="email_campaign",
        entity_id=camp.id,
        details={"name": camp.name},
        ip_address=ip_address,
    )
    db.flush()
    return _to_email_campaign_response(camp)


def _launch_campaign_sync(
    db: Session,
    *,
    admin: Optional[Admin],
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> CampaignLaunchResponse:
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    label = "Email" if channel == MessageChannel.EMAIL else "WhatsApp"
    locked_id = db.scalar(select(model.id).where(model.id == campaign_id).with_for_update())
    if not locked_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} campaign not found."
        )
    camp = db.scalar(
        select(model)
        .options(selectinload(model.recipients))
        .where(model.id == campaign_id)
        .execution_options(populate_existing=True)
    )
    if camp.status in (CampaignStatus.COMPLETED, CampaignStatus.SENDING, CampaignStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This {label.lower()} campaign has already been launched or is currently sending.",
        )
    if camp.status == CampaignStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cancelled {label.lower()} campaigns cannot be launched directly.",
        )

    now = datetime.now(timezone.utc)
    camp.status = CampaignStatus.PROCESSING
    camp.queued_at = camp.queued_at or now
    camp.started_at = camp.started_at or now
    db.flush()

    materialize_campaign_recipients(db, channel, camp, force_new_generation=True)
    jobs = claim_recipient_batch(
        db,
        worker_id="api-sync-launch",
        batch_size=10000,
        campaign_filter=(channel, camp.id),
    )

    sent_count = 0
    failed_count = 0
    accepted_count = 0
    skipped_count = 0
    unresolved_count = 0

    for job in jobs:
        consent_ok, cust, skip_reason = _check_live_recipient_consent(db, job.channel, job.customer_id)
        if not consent_ok or cust is None:
            result: dict[str, Any] = {"outcome": "skipped", "reason": skip_reason}
            skipped_count += 1
        else:
            result = _execute_provider_send(job, cust)
            if result["outcome"] == "accepted":
                sent_count += 1
                accepted_count += 1
            elif result.get("is_ambiguous_timeout"):
                unresolved_count += 1
            else:
                failed_count += 1
        _persist_job_outcome(db, job, result, allow_deferred_retry=False)

    camp = recompute_campaign_status(db, channel, camp.id)
    if camp.status == CampaignStatus.FAILED:
        log_background_event(
            f"campaign.{channel.value}_failed",
            level=logging.ERROR,
            campaign_id=str(camp.id),
            failed_count=failed_count,
        )

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action=f"campaign.{channel.value}_launched",
            entity_type=f"{channel.value}_campaign",
            entity_id=camp.id,
            details={
                "name": camp.name,
                "status": camp.status.value,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "skipped_count": skipped_count,
            },
            ip_address=ip_address,
        )
    db.flush()

    return CampaignLaunchResponse(
        campaign_id=camp.id,
        channel=channel,
        status=camp.status,
        targeted_recipients=len(jobs),
        sent_count=sent_count,
        failed_count=failed_count,
        accepted_count=accepted_count,
        retrying_count=0,
        skipped_count=skipped_count,
        unresolved_count=unresolved_count,
        completed_at=camp.completed_at,
    )


def launch_email_campaign(
    db: Session,
    admin: Optional[Admin],
    campaign_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> CampaignLaunchResponse:
    return _launch_campaign_sync(
        db,
        admin=admin,
        channel=MessageChannel.EMAIL,
        campaign_id=campaign_id,
        ip_address=ip_address,
    )


def list_whatsapp_campaigns(db: Session) -> list[WhatsAppCampaignResponse]:
    rows = db.scalars(
        select(WhatsAppCampaign)
        .options(selectinload(WhatsAppCampaign.recipients))
        .order_by(WhatsAppCampaign.created_at.desc())
        .execution_options(populate_existing=True)
    ).all()
    return [_to_whatsapp_campaign_response(c) for c in rows]


def create_whatsapp_campaign(
    db: Session,
    admin: Admin,
    payload: WhatsAppCampaignCreateRequest,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaignResponse:
    if payload.template_id:
        tpl = db.get(MessageTemplate, payload.template_id)
        if not tpl or tpl.channel != MessageChannel.WHATSAPP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced template does not exist or is not a WhatsApp template.",
            )

    camp = WhatsAppCampaign(
        name=payload.name,
        content=payload.content,
        approved_template_name=payload.approved_template_name,
        template_id=payload.template_id,
        audience_criteria=payload.audience_criteria,
        status=CampaignStatus.DRAFT,
    )
    db.add(camp)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="campaign.whatsapp_created",
        entity_type="whatsapp_campaign",
        entity_id=camp.id,
        details={"name": camp.name, "approved_template_name": camp.approved_template_name},
        ip_address=ip_address,
    )
    db.flush()
    return _to_whatsapp_campaign_response(camp)


def launch_whatsapp_campaign(
    db: Session,
    admin: Optional[Admin],
    campaign_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> CampaignLaunchResponse:
    return _launch_campaign_sync(
        db,
        admin=admin,
        channel=MessageChannel.WHATSAPP,
        campaign_id=campaign_id,
        ip_address=ip_address,
    )


def schedule_campaign(
    db: Session,
    admin: Admin,
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    *,
    scheduled_for: Optional[datetime] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """Queue a DRAFT, FAILED, PARTIALLY_COMPLETED, or CANCELLED campaign into SCHEDULED for worker execution."""
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    camp = db.scalar(select(model).where(model.id == campaign_id).with_for_update())
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    if camp.status not in (
        CampaignStatus.DRAFT,
        CampaignStatus.FAILED,
        CampaignStatus.PARTIALLY_COMPLETED,
        CampaignStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign in status '{camp.status.value}' cannot be scheduled.",
        )

    fk_col = (
        CampaignRecipient.email_campaign_id
        if channel == MessageChannel.EMAIL
        else CampaignRecipient.whatsapp_campaign_id
    )
    failed_rows = db.scalars(
        select(CampaignRecipient).where(
            fk_col == camp.id,
            CampaignRecipient.delivery_status.in_((DeliveryStatus.FAILED, DeliveryStatus.SKIPPED)),
        )
    ).all()
    for row in failed_rows:
        row.delivery_status = DeliveryStatus.QUEUED
        row.attempt_count = 0
        row.next_retry_at = None
        row.locked_by = None
        row.locked_at = None
        row.failure_reason = None
        row.error_code = None
        row.is_retryable_error = None
        row.failed_at = None
        row.idempotency_key = (
            f"dv-{channel.value}-{camp.id.hex[:12]}-{row.customer_id.hex[:12]}-{uuid.uuid4().hex[:6]}"
        )

    camp.status = CampaignStatus.SCHEDULED
    camp.scheduled_for = scheduled_for or datetime.now(timezone.utc)
    camp.completed_at = None
    camp.locked_by = None
    camp.locked_at = None
    camp.last_error = None

    record_admin_audit(
        db=db,
        admin=admin,
        action=f"campaign.{channel.value}_scheduled",
        entity_type=f"{channel.value}_campaign",
        entity_id=camp.id,
        details={"name": camp.name, "scheduled_for": camp.scheduled_for.isoformat()},
        ip_address=ip_address,
    )
    db.flush()
    return {
        "campaign_id": str(camp.id),
        "channel": channel.value,
        "status": camp.status.value,
        "scheduled_for": camp.scheduled_for.isoformat(),
    }


def queue_campaign_for_worker(
    db: Session,
    admin: Admin,
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> CampaignLaunchResponse:
    """Enqueue eligible recipient jobs immediately for asynchronous background worker processing."""
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    camp = db.scalar(
        select(model)
        .options(selectinload(model.recipients))
        .where(model.id == campaign_id)
        .with_for_update()
    )
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    if camp.status in (CampaignStatus.COMPLETED, CampaignStatus.SENDING, CampaignStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign in status '{camp.status.value}' cannot be re-queued.",
        )

    now = datetime.now(timezone.utc)
    camp.status = CampaignStatus.QUEUED
    camp.queued_at = now
    camp.scheduled_for = now
    camp.completed_at = None
    enqueued_count = materialize_campaign_recipients(db, channel, camp, force_new_generation=True)
    recompute_campaign_status(db, channel, camp.id)

    record_admin_audit(
        db=db,
        admin=admin,
        action=f"campaign.{channel.value}_queued",
        entity_type=f"{channel.value}_campaign",
        entity_id=camp.id,
        details={"name": camp.name, "queued_recipients": enqueued_count},
        ip_address=ip_address,
    )
    db.flush()

    camp_refreshed = db.scalar(
        select(model)
        .options(selectinload(model.recipients))
        .where(model.id == campaign_id)
        .execution_options(populate_existing=True)
    )
    counts = _compute_recipient_counts(camp_refreshed.recipients or [])
    return CampaignLaunchResponse(
        campaign_id=camp_refreshed.id,
        channel=channel,
        status=camp_refreshed.status,
        targeted_recipients=counts["recipient_count"],
        sent_count=counts["sent_count"],
        failed_count=counts["failed_count"],
        accepted_count=counts["accepted_count"],
        retrying_count=counts["retrying_count"],
        skipped_count=counts["skipped_count"],
        unresolved_count=counts["unresolved_count"],
        completed_at=camp_refreshed.completed_at,
    )


def cancel_campaign(
    db: Session,
    admin: Admin,
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> dict[str, str]:
    """Cancel a draft, scheduled, or queued campaign and skip pending queued recipients."""
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    camp = db.scalar(select(model).where(model.id == campaign_id).with_for_update())
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    if camp.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign in status '{camp.status.value}' cannot be cancelled.",
        )

    fk_col = (
        CampaignRecipient.email_campaign_id
        if channel == MessageChannel.EMAIL
        else CampaignRecipient.whatsapp_campaign_id
    )
    pending_rows = db.scalars(
        select(CampaignRecipient).where(
            fk_col == camp.id,
            CampaignRecipient.delivery_status.in_((DeliveryStatus.QUEUED, DeliveryStatus.RETRYING)),
        )
    ).all()
    for r in pending_rows:
        r.delivery_status = DeliveryStatus.SKIPPED
        r.failure_reason = "Campaign cancelled by administrator."
        r.next_retry_at = None

    camp.status = CampaignStatus.CANCELLED
    camp.locked_by = None
    camp.locked_at = None

    record_admin_audit(
        db=db,
        admin=admin,
        action=f"campaign.{channel.value}_cancelled",
        entity_type=f"{channel.value}_campaign",
        entity_id=camp.id,
        details={"name": camp.name, "skipped_pending": len(pending_rows)},
        ip_address=ip_address,
    )
    db.flush()
    return {"campaign_id": str(camp.id), "channel": channel.value, "status": camp.status.value}


def get_campaign_detail(
    db: Session,
    channel: MessageChannel,
    campaign_id: uuid.UUID,
) -> CampaignDetailResponse:
    model = EmailCampaign if channel == MessageChannel.EMAIL else WhatsAppCampaign
    camp = db.scalar(
        select(model)
        .options(selectinload(model.recipients).selectinload(CampaignRecipient.customer))
        .where(model.id == campaign_id)
        .execution_options(populate_existing=True)
    )
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    recs = sorted(camp.recipients or [], key=lambda r: (r.updated_at or camp.created_at), reverse=True)
    counts = _compute_recipient_counts(recs)

    failure_summary: dict[str, int] = {}
    recipient_items: list[CampaignRecipientSummary] = []
    for r in recs:
        if r.error_code:
            failure_summary[r.error_code] = failure_summary.get(r.error_code, 0) + 1
        recipient_items.append(
            CampaignRecipientSummary(
                id=r.id,
                customer_id=r.customer_id,
                customer_email=r.customer.email if r.customer else None,
                delivery_status=r.delivery_status,
                provider_message_id=r.provider_message_id,
                attempt_count=r.attempt_count,
                max_attempts=r.max_attempts,
                next_retry_at=r.next_retry_at,
                error_code=r.error_code,
                is_retryable_error=r.is_retryable_error,
                failure_reason=r.failure_reason,
                sent_at=r.sent_at,
                accepted_at=r.accepted_at,
                delivered_at=r.delivered_at,
                read_at=r.read_at,
                bounced_at=r.bounced_at,
                failed_at=r.failed_at,
            )
        )

    return CampaignDetailResponse(
        id=camp.id,
        channel=channel,
        name=camp.name,
        subject=getattr(camp, "subject", None),
        content=camp.content,
        approved_template_name=getattr(camp, "approved_template_name", None),
        template_id=camp.template_id,
        audience_criteria=camp.audience_criteria,
        status=camp.status,
        scheduled_for=camp.scheduled_for,
        queued_at=camp.queued_at,
        started_at=camp.started_at,
        created_at=camp.created_at,
        completed_at=camp.completed_at,
        last_error=camp.last_error,
        failure_summary=failure_summary,
        recipients=recipient_items[:200],
        **counts,
    )


def get_marketing_worker_status(db: Session) -> MarketingWorkerStatusResponse:
    queued_jobs = int(
        db.scalar(
            select(func.count(CampaignRecipient.id)).where(
                CampaignRecipient.delivery_status == DeliveryStatus.QUEUED
            )
        )
        or 0
    )
    processing_jobs = int(
        db.scalar(
            select(func.count(CampaignRecipient.id)).where(
                CampaignRecipient.delivery_status == DeliveryStatus.PROCESSING
            )
        )
        or 0
    )
    retrying_jobs = int(
        db.scalar(
            select(func.count(CampaignRecipient.id)).where(
                CampaignRecipient.delivery_status == DeliveryStatus.RETRYING
            )
        )
        or 0
    )
    sched_email = int(
        db.scalar(
            select(func.count(EmailCampaign.id)).where(EmailCampaign.status == CampaignStatus.SCHEDULED)
        )
        or 0
    )
    sched_wa = int(
        db.scalar(
            select(func.count(WhatsAppCampaign.id)).where(
                WhatsAppCampaign.status == CampaignStatus.SCHEDULED
            )
        )
        or 0
    )
    heartbeats = db.scalars(
        select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_heartbeat_at.desc()).limit(20)
    ).all()
    return MarketingWorkerStatusResponse(
        queued_jobs=queued_jobs,
        processing_jobs=processing_jobs,
        retrying_jobs=retrying_jobs,
        scheduled_campaigns=sched_email + sched_wa,
        workers=[
            WorkerHeartbeatResponse(
                worker_id=hb.worker_id,
                hostname=hb.hostname,
                pid=hb.pid,
                status=hb.status,
                started_at=hb.started_at,
                last_heartbeat_at=hb.last_heartbeat_at,
                processed_jobs_count=hb.processed_jobs_count,
            )
            for hb in heartbeats
        ],
    )


def process_scheduled_campaigns(db: Session, max_campaigns: int = 10) -> dict[str, int]:
    """Process due SCHEDULED campaigns and retrying/queued recipient jobs in-session."""
    return process_campaigns_in_session(db, max_campaigns=max_campaigns, allow_deferred_retry=True)


def update_campaign_delivery_status(
    db: Session,
    provider_message_id: str,
    delivery_status: DeliveryStatus,
    failure_reason: Optional[str] = None,
) -> bool:
    """Update a CampaignRecipient delivery status safely with transition guards."""
    rec = db.scalar(
        select(CampaignRecipient)
        .where(CampaignRecipient.provider_message_id == provider_message_id)
        .with_for_update()
    )
    if not rec:
        return False
    if not can_transition_delivery_status(rec.delivery_status, delivery_status):
        return False
    now = datetime.now(timezone.utc)
    rec.delivery_status = delivery_status
    if delivery_status == DeliveryStatus.DELIVERED:
        rec.delivered_at = now
    elif delivery_status == DeliveryStatus.READ:
        rec.delivered_at = rec.delivered_at or now
        rec.read_at = now
    elif delivery_status == DeliveryStatus.BOUNCED:
        rec.bounced_at = now
    elif delivery_status in (DeliveryStatus.FAILED, DeliveryStatus.SUPPRESSED):
        rec.failed_at = now
    if failure_reason:
        rec.failure_reason = failure_reason[:500]
    cid = rec.email_campaign_id if rec.channel == MessageChannel.EMAIL else rec.whatsapp_campaign_id
    if cid:
        recompute_campaign_status(db, rec.channel, cid)
    db.flush()
    return True


# ===========================================================================
# 6. STORE SETTINGS & AUDIT LOGS
# ===========================================================================


def list_admin_store_settings(db: Session) -> list[StoreSettingResponse]:
    rows = db.scalars(
        select(StoreSetting)
        .where(StoreSetting.key.not_in(PROTECTED_SYSTEM_SETTING_KEYS))
        .order_by(StoreSetting.key.asc())
    ).all()
    return [StoreSettingResponse.model_validate(s) for s in rows]


def upsert_store_setting(
    db: Session,
    admin: Admin,
    payload: StoreSettingUpsertRequest,
    ip_address: Optional[str] = None,
) -> StoreSettingResponse:
    setting = db.scalar(select(StoreSetting).where(StoreSetting.key == payload.key))
    if setting:
        setting.value = payload.value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        setting = StoreSetting(key=payload.key, value=payload.value)
        db.add(setting)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="settings.updated",
        entity_type="store_setting",
        entity_id=setting.key,
        details={"key": setting.key},
        ip_address=ip_address,
    )
    db.flush()
    return StoreSettingResponse.model_validate(setting)


def batch_update_store_settings(
    db: Session,
    admin: Admin,
    payload: StoreSettingsBatchUpdateRequest,
    ip_address: Optional[str] = None,
) -> list[StoreSettingResponse]:
    now = datetime.now(timezone.utc)
    updated_keys: list[str] = []
    for key, val in payload.settings.items():
        setting = db.scalar(select(StoreSetting).where(StoreSetting.key == key))
        if setting:
            setting.value = val
            setting.updated_at = now
        else:
            db.add(StoreSetting(key=key, value=val))
        updated_keys.append(key)

    db.flush()
    record_admin_audit(
        db=db,
        admin=admin,
        action="settings.batch_updated",
        entity_type="store_setting",
        entity_id="batch",
        details={"keys": updated_keys},
        ip_address=ip_address,
    )
    db.flush()
    return list_admin_store_settings(db)


def get_public_store_settings(db: Session) -> dict[str, Any]:
    rows = db.scalars(
        select(StoreSetting).where(
            StoreSetting.key.not_in(PROTECTED_SYSTEM_SETTING_KEYS),
            StoreSetting.key.like("store.%"),
        )
    ).all()
    return {r.key: r.value for r in rows}


def list_admin_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 25,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> PaginatedAuditLogResponse:
    conds = []
    if action and action.strip():
        conds.append(AuditLog.action.ilike(f"%{action.strip()}%"))
    if entity_type and entity_type.strip():
        conds.append(AuditLog.entity_type == entity_type.strip())

    total = db.scalar(select(func.count(AuditLog.id)).where(*conds)) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    rows = db.scalars(
        select(AuditLog)
        .options(selectinload(AuditLog.admin))
        .where(*conds)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    items = [
        AuditLogEntryResponse(
            id=r.id,
            admin_id=r.admin_id,
            admin_username=r.admin.username if r.admin else None,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            metadata=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PaginatedAuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
