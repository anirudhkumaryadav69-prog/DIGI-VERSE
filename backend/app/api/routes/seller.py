"""Multi-vendor seller onboarding, seller dashboard/catalog/order APIs, and admin seller governance."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_customer, require_admin, require_approved_seller
from app.core.rate_limit import get_client_ip, rate_limit_customer
from app.models.admin import Admin
from app.models.customer import Customer
from app.models.enums import (
    OrderPaymentStatus,
    OrderStatus,
    ProductApprovalStatus,
    SellerApplicationStatus,
)
from app.models.seller import SellerProfile
from app.schemas.auth import GenericMessageResponse
from app.schemas.catalog import (
    PaginatedSellerProductResponse,
    ProductImageResponse,
    ProductImageUpdateRequest,
    SaleAdminResponse,
    SaleCreateRequest,
    SaleUpdateRequest,
    SellerProductCreateRequest,
    SellerProductResponse,
    SellerProductStatusActionRequest,
    SellerProductUpdateRequest,
)
from app.schemas.seller import (
    AdminSellerReviewRequest,
    AdminSellerSummaryResponse,
    PaginatedAdminSellerResponse,
    PaginatedSellerOrderResponse,
    SellerAnalyticsResponse,
    SellerApplicationCreateRequest,
    SellerOrderResponse,
    SellerOverviewResponse,
    SellerProfileResponse,
    SellerProfileUpdateRequest,
)
from app.services.catalog_service import (
    create_product_sale,
    delete_product_asset,
    delete_product_image,
    replace_product_image,
    update_product_image,
    update_product_sale,
    upload_product_asset,
    upload_product_image,
)
from app.services.seller_service import (
    change_seller_product_status,
    create_seller_product,
    delete_seller_product,
    get_admin_seller,
    get_my_seller_application,
    get_seller_analytics,
    get_seller_order,
    get_seller_overview,
    get_seller_product,
    list_admin_sellers,
    list_seller_orders,
    list_seller_products,
    review_admin_seller,
    submit_seller_application,
    update_seller_product,
    update_seller_store_profile,
    upload_seller_branding_image,
)

router = APIRouter(prefix="/seller", tags=["Multi-Vendor Seller Portal"])
admin_seller_router = APIRouter(prefix="/admin/sellers", tags=["Admin Seller Management"])


# ---------------------------------------------------------------------------
# SELLER ONBOARDING (ANY AUTHENTICATED ACTIVE CUSTOMER)
# ---------------------------------------------------------------------------


@router.get("/application", response_model=SellerProfileResponse)
def seller_get_my_application(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> SellerProfileResponse:
    return get_my_seller_application(db=db, customer=customer)


@router.post(
    "/application",
    response_model=SellerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def seller_submit_application(
    payload: SellerApplicationCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> SellerProfileResponse:
    created = submit_seller_application(db=db, customer=customer, payload=payload)
    db.commit()
    return created


@router.post(
    "/branding-image",
    dependencies=[
        Depends(rate_limit_customer("seller_branding_upload", max_requests=10, window_seconds=300))
    ],
)
def seller_upload_branding_image(
    file: UploadFile = File(...),
    customer: Customer = Depends(get_current_customer),
) -> dict[str, str]:
    image_url = upload_seller_branding_image(file)
    return {"image_url": image_url}


# ---------------------------------------------------------------------------
# APPROVED SELLER DASHBOARD & STORE PROFILE
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=SellerOverviewResponse)
def seller_dashboard_overview(
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerOverviewResponse:
    return get_seller_overview(db=db, seller=seller)


@router.get("/analytics", response_model=SellerAnalyticsResponse)
def seller_dashboard_analytics(
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerAnalyticsResponse:
    return get_seller_analytics(db=db, seller=seller)


@router.get("/profile", response_model=SellerProfileResponse)
def seller_get_profile(
    seller: SellerProfile = Depends(require_approved_seller),
) -> SellerProfileResponse:
    from app.services.seller_service import _to_seller_profile_response

    return _to_seller_profile_response(seller)


@router.patch("/profile", response_model=SellerProfileResponse)
def seller_update_profile(
    payload: SellerProfileUpdateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProfileResponse:
    updated = update_seller_store_profile(db=db, seller=seller, payload=payload)
    db.commit()
    return updated


# ---------------------------------------------------------------------------
# SELLER PRODUCT MANAGEMENT (OWNERSHIP ISOLATED)
# ---------------------------------------------------------------------------


@router.get("/products", response_model=PaginatedSellerProductResponse)
def seller_list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    category_id: Optional[uuid.UUID] = Query(default=None),
    approval_status: Optional[ProductApprovalStatus] = Query(default=None),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PaginatedSellerProductResponse:
    return list_seller_products(
        db=db,
        seller=seller,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        approval_status=approval_status,
    )


@router.post(
    "/products",
    response_model=SellerProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def seller_create_product(
    payload: SellerProductCreateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    created = create_seller_product(db=db, seller=seller, payload=payload)
    db.commit()
    return created


@router.get("/products/{product_id}", response_model=SellerProductResponse)
def seller_get_product(
    product_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    return get_seller_product(db=db, seller=seller, product_id=product_id)


@router.patch("/products/{product_id}", response_model=SellerProductResponse)
def seller_update_product(
    product_id: uuid.UUID,
    payload: SellerProductUpdateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    updated = update_seller_product(db=db, seller=seller, product_id=product_id, payload=payload)
    db.commit()
    return updated


@router.patch("/products/{product_id}/status", response_model=SellerProductResponse)
def seller_change_product_status(
    product_id: uuid.UUID,
    payload: SellerProductStatusActionRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    updated = change_seller_product_status(
        db=db, seller=seller, product_id=product_id, action=payload.action
    )
    db.commit()
    return updated


@router.delete("/products/{product_id}", response_model=GenericMessageResponse)
def seller_delete_product(
    product_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_seller_product(db=db, seller=seller, product_id=product_id)
    db.commit()
    return GenericMessageResponse(message="Product deleted successfully.")


# ---------------------------------------------------------------------------
# SELLER PRIVATE ASSETS, GALLERY IMAGES & DISCOUNTS (OWNERSHIP ISOLATED)
# ---------------------------------------------------------------------------


@router.post(
    "/products/{product_id}/asset",
    response_model=SellerProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def seller_upload_product_asset(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    updated = upload_product_asset(
        db=db,
        admin=None,
        product_id=product_id,
        file=file,
        required_seller_id=seller.id,
    )
    db.commit()
    data = updated.model_dump()
    data["private_download_url"] = None
    return SellerProductResponse(**data)


@router.delete("/products/{product_id}/asset", response_model=SellerProductResponse)
def seller_delete_product_asset(
    product_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerProductResponse:
    updated = delete_product_asset(
        db=db,
        admin=None,
        product_id=product_id,
        required_seller_id=seller.id,
    )
    db.commit()
    data = updated.model_dump()
    data["private_download_url"] = None
    return SellerProductResponse(**data)


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def seller_upload_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    display_order: Optional[int] = Form(default=None),
    is_primary: bool = Form(default=False),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    created = upload_product_image(
        db=db,
        admin=None,
        product_id=product_id,
        file=file,
        display_order=display_order,
        is_primary=is_primary,
        required_seller_id=seller.id,
    )
    db.commit()
    return created


@router.patch("/products/{product_id}/images/{image_id}", response_model=ProductImageResponse)
def seller_update_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    payload: ProductImageUpdateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    updated = update_product_image(
        db=db,
        admin=None,
        product_id=product_id,
        image_id=image_id,
        payload=payload,
        required_seller_id=seller.id,
    )
    db.commit()
    return updated


@router.put("/products/{product_id}/images/{image_id}", response_model=ProductImageResponse)
def seller_replace_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    file: UploadFile = File(...),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    updated = replace_product_image(
        db=db,
        admin=None,
        product_id=product_id,
        image_id=image_id,
        file=file,
        required_seller_id=seller.id,
    )
    db.commit()
    return updated


@router.delete("/products/{product_id}/images/{image_id}", response_model=GenericMessageResponse)
def seller_delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_product_image(
        db=db,
        admin=None,
        product_id=product_id,
        image_id=image_id,
        required_seller_id=seller.id,
    )
    db.commit()
    return GenericMessageResponse(message="Product image deleted successfully.")


@router.post(
    "/products/{product_id}/sales",
    response_model=SaleAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def seller_create_product_sale(
    product_id: uuid.UUID,
    payload: SaleCreateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SaleAdminResponse:
    created = create_product_sale(
        db=db,
        admin=None,
        product_id=product_id,
        payload=payload,
        required_seller_id=seller.id,
    )
    db.commit()
    return created


@router.patch("/products/{product_id}/sales/{sale_id}", response_model=SaleAdminResponse)
def seller_update_product_sale(
    product_id: uuid.UUID,
    sale_id: uuid.UUID,
    payload: SaleUpdateRequest,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SaleAdminResponse:
    updated = update_product_sale(
        db=db,
        admin=None,
        product_id=product_id,
        sale_id=sale_id,
        payload=payload,
        required_seller_id=seller.id,
    )
    db.commit()
    return updated


# ---------------------------------------------------------------------------
# SELLER ORDER ATTRIBUTION VIEWS (ISOLATED TO SELLER-OWNED ITEMS)
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=PaginatedSellerOrderResponse)
def seller_list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[OrderStatus] = Query(default=None, alias="status"),
    payment_status: Optional[OrderPaymentStatus] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=120),
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> PaginatedSellerOrderResponse:
    return list_seller_orders(
        db=db,
        seller=seller,
        page=page,
        page_size=page_size,
        order_status=status_filter,
        payment_status=payment_status,
        search=search,
    )


@router.get("/orders/{order_id}", response_model=SellerOrderResponse)
def seller_get_order(
    order_id: uuid.UUID,
    seller: SellerProfile = Depends(require_approved_seller),
    db: Session = Depends(get_db),
) -> SellerOrderResponse:
    return get_seller_order(db=db, seller=seller, order_id=order_id)


# ---------------------------------------------------------------------------
# ADMIN SELLER GOVERNANCE ROUTES
# ---------------------------------------------------------------------------


@admin_seller_router.get("", response_model=PaginatedAdminSellerResponse)
def admin_list_sellers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    status_filter: Optional[SellerApplicationStatus] = Query(default=None, alias="status"),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAdminSellerResponse:
    return list_admin_sellers(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter,
    )


@admin_seller_router.get("/{seller_id}", response_model=AdminSellerSummaryResponse)
def admin_get_single_seller(
    seller_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSellerSummaryResponse:
    return get_admin_seller(db=db, seller_id=seller_id)


@admin_seller_router.post("/{seller_id}/review", response_model=AdminSellerSummaryResponse)
def admin_review_seller(
    seller_id: uuid.UUID,
    payload: AdminSellerReviewRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSellerSummaryResponse:
    updated = review_admin_seller(
        db=db,
        admin=admin,
        seller_id=seller_id,
        action=payload.action,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated
