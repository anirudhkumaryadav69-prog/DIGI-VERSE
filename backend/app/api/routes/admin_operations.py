import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.core.rate_limit import get_client_ip
from app.models.admin import Admin
from app.models.enums import AccountStatus, MessageChannel
from app.schemas.auth import GenericMessageResponse
from app.schemas.operations import (
    AdminCustomerStatusUpdateRequest,
    AdminCustomerSummaryResponse,
    AdVideoCreateRequest,
    AdVideoResponse,
    AdVideoUpdateRequest,
    BannerCreateRequest,
    BannerResponse,
    BannerUpdateRequest,
    CampaignDetailResponse,
    CampaignLaunchResponse,
    CampaignScheduleRequest,
    DashboardAnalyticsResponse,
    EmailCampaignCreateRequest,
    EmailCampaignResponse,
    MarketingWorkerStatusResponse,
    MessageTemplateCreateRequest,
    MessageTemplateResponse,
    MessageTemplateUpdateRequest,
    PaginatedAdminCustomerResponse,
    PaginatedAuditLogResponse,
    StoreSettingResponse,
    StoreSettingsBatchUpdateRequest,
    StoreSettingUpsertRequest,
    WhatsAppCampaignCreateRequest,
    WhatsAppCampaignResponse,
)
from app.services.operations_service import (
    batch_update_store_settings,
    cancel_campaign,
    create_admin_banner,
    create_admin_video,
    create_email_campaign,
    create_message_template,
    create_whatsapp_campaign,
    delete_admin_banner,
    delete_admin_video,
    delete_message_template,
    get_campaign_detail,
    get_dashboard_analytics,
    get_marketing_worker_status,
    launch_email_campaign,
    launch_whatsapp_campaign,
    list_admin_audit_logs,
    list_admin_banners,
    list_admin_customers,
    list_admin_store_settings,
    list_admin_videos,
    list_email_campaigns,
    list_message_templates,
    list_whatsapp_campaigns,
    process_scheduled_campaigns,
    queue_campaign_for_worker,
    schedule_campaign,
    update_admin_banner,
    update_admin_customer_status,
    update_admin_video,
    update_message_template,
    upsert_store_setting,
)

router = APIRouter(prefix="/admin", tags=["Admin Operations, Marketing & Store Settings"])


# ---------------------------------------------------------------------------
# 1. SQL ANALYTICS
# ---------------------------------------------------------------------------


@router.get("/dashboard/analytics", response_model=DashboardAnalyticsResponse)
def admin_get_dashboard_analytics(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DashboardAnalyticsResponse:
    return get_dashboard_analytics(db=db, date_from=date_from, date_to=date_to)


# ---------------------------------------------------------------------------
# 2. CUSTOMER MANAGEMENT
# ---------------------------------------------------------------------------


@router.get("/customers", response_model=PaginatedAdminCustomerResponse)
def admin_list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    account_status: Optional[AccountStatus] = Query(default=None),
    is_phone_verified: Optional[bool] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAdminCustomerResponse:
    return list_admin_customers(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        account_status=account_status,
        is_phone_verified=is_phone_verified,
    )


@router.patch("/customers/{customer_id}/status", response_model=AdminCustomerSummaryResponse)
def admin_update_customer_status(
    customer_id: uuid.UUID,
    payload: AdminCustomerStatusUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminCustomerSummaryResponse:
    result = update_admin_customer_status(
        db=db,
        admin=admin,
        customer_id=customer_id,
        new_status=payload.account_status,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# 3. PROMOTIONAL BANNERS
# ---------------------------------------------------------------------------


@router.get("/banners", response_model=list[BannerResponse])
def admin_list_banners(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[BannerResponse]:
    return list_admin_banners(db=db)


@router.post("/banners", response_model=BannerResponse, status_code=status.HTTP_201_CREATED)
def admin_create_banner(
    payload: BannerCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BannerResponse:
    result = create_admin_banner(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.patch("/banners/{banner_id}", response_model=BannerResponse)
def admin_update_banner(
    banner_id: uuid.UUID,
    payload: BannerUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BannerResponse:
    result = update_admin_banner(
        db=db,
        admin=admin,
        banner_id=banner_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.delete("/banners/{banner_id}", response_model=GenericMessageResponse)
def admin_delete_banner(
    banner_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_admin_banner(
        db=db,
        admin=admin,
        banner_id=banner_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return GenericMessageResponse(message="Banner deleted successfully.")


# ---------------------------------------------------------------------------
# 4. ADVERTISEMENT VIDEOS
# ---------------------------------------------------------------------------


@router.get("/videos", response_model=list[AdVideoResponse])
def admin_list_videos(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdVideoResponse]:
    return list_admin_videos(db=db)


@router.post("/videos", response_model=AdVideoResponse, status_code=status.HTTP_201_CREATED)
def admin_create_video(
    payload: AdVideoCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdVideoResponse:
    result = create_admin_video(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.patch("/videos/{video_id}", response_model=AdVideoResponse)
def admin_update_video(
    video_id: uuid.UUID,
    payload: AdVideoUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdVideoResponse:
    result = update_admin_video(
        db=db,
        admin=admin,
        video_id=video_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.delete("/videos/{video_id}", response_model=GenericMessageResponse)
def admin_delete_video(
    video_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_admin_video(
        db=db,
        admin=admin,
        video_id=video_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return GenericMessageResponse(message="Advertisement video deleted successfully.")


# ---------------------------------------------------------------------------
# 5. MESSAGE TEMPLATES, EMAIL CAMPAIGNS & WHATSAPP CAMPAIGNS
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[MessageTemplateResponse])
def admin_list_templates(
    channel: Optional[MessageChannel] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[MessageTemplateResponse]:
    return list_message_templates(db=db, channel=channel)


@router.post(
    "/templates",
    response_model=MessageTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_template(
    payload: MessageTemplateCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageTemplateResponse:
    result = create_message_template(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.patch("/templates/{template_id}", response_model=MessageTemplateResponse)
def admin_update_template(
    template_id: uuid.UUID,
    payload: MessageTemplateUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageTemplateResponse:
    result = update_message_template(
        db=db,
        admin=admin,
        template_id=template_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.delete("/templates/{template_id}", response_model=GenericMessageResponse)
def admin_delete_template(
    template_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_message_template(
        db=db,
        admin=admin,
        template_id=template_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return GenericMessageResponse(message="Message template deleted successfully.")


@router.get("/campaigns/email", response_model=list[EmailCampaignResponse])
def admin_list_email_campaigns(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[EmailCampaignResponse]:
    return list_email_campaigns(db=db)


@router.post(
    "/campaigns/email",
    response_model=EmailCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_email_campaign(
    payload: EmailCampaignCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmailCampaignResponse:
    result = create_email_campaign(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.post("/campaigns/email/{campaign_id}/launch", response_model=CampaignLaunchResponse)
def admin_launch_email_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampaignLaunchResponse:
    result = launch_email_campaign(
        db=db,
        admin=admin,
        campaign_id=campaign_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.get("/campaigns/whatsapp", response_model=list[WhatsAppCampaignResponse])
def admin_list_whatsapp_campaigns(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[WhatsAppCampaignResponse]:
    return list_whatsapp_campaigns(db=db)


@router.post(
    "/campaigns/whatsapp",
    response_model=WhatsAppCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_whatsapp_campaign(
    payload: WhatsAppCampaignCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppCampaignResponse:
    result = create_whatsapp_campaign(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.post("/campaigns/whatsapp/{campaign_id}/launch", response_model=CampaignLaunchResponse)
def admin_launch_whatsapp_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampaignLaunchResponse:
    result = launch_whatsapp_campaign(
        db=db,
        admin=admin,
        campaign_id=campaign_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.post("/campaigns/{channel}/{campaign_id}/schedule")
def admin_schedule_campaign(
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    request: Request,
    payload: Optional[CampaignScheduleRequest] = Body(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    result = schedule_campaign(
        db=db,
        admin=admin,
        channel=channel,
        campaign_id=campaign_id,
        scheduled_for=payload.scheduled_for if payload else None,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.post("/campaigns/{channel}/{campaign_id}/queue", response_model=CampaignLaunchResponse)
def admin_queue_campaign(
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampaignLaunchResponse:
    result = queue_campaign_for_worker(
        db=db,
        admin=admin,
        channel=channel,
        campaign_id=campaign_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.post("/campaigns/{channel}/{campaign_id}/cancel")
def admin_cancel_campaign(
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    result = cancel_campaign(
        db=db,
        admin=admin,
        channel=channel,
        campaign_id=campaign_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.get("/campaigns/{channel}/{campaign_id}", response_model=CampaignDetailResponse)
def admin_get_campaign_detail(
    channel: MessageChannel,
    campaign_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampaignDetailResponse:
    return get_campaign_detail(db=db, channel=channel, campaign_id=campaign_id)


@router.get("/marketing/worker-status", response_model=MarketingWorkerStatusResponse)
def admin_get_marketing_worker_status(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MarketingWorkerStatusResponse:
    return get_marketing_worker_status(db=db)


@router.post("/campaigns/process-scheduled")
def admin_process_scheduled_campaigns(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    result = process_scheduled_campaigns(db=db)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# 6. STORE SETTINGS & AUDIT LOGS
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=list[StoreSettingResponse])
def admin_list_settings(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[StoreSettingResponse]:
    return list_admin_store_settings(db=db)


@router.put("/settings", response_model=StoreSettingResponse)
def admin_upsert_setting(
    payload: StoreSettingUpsertRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreSettingResponse:
    result = upsert_store_setting(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.patch("/settings/batch", response_model=list[StoreSettingResponse])
def admin_batch_update_settings(
    payload: StoreSettingsBatchUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[StoreSettingResponse]:
    result = batch_update_store_settings(
        db=db,
        admin=admin,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return result


@router.get("/audit-logs", response_model=PaginatedAuditLogResponse)
def admin_get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    action: Optional[str] = Query(default=None, max_length=150),
    entity_type: Optional[str] = Query(default=None, max_length=100),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAuditLogResponse:
    return list_admin_audit_logs(
        db=db,
        page=page,
        page_size=page_size,
        action=action,
        entity_type=entity_type,
    )
