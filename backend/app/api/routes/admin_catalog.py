import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.core.rate_limit import get_client_ip
from app.models.admin import Admin
from app.models.enums import ProductApprovalStatus
from app.schemas.auth import GenericMessageResponse
from app.schemas.catalog import (
    AdminProductModerationRequest,
    CategoryAdminResponse,
    CategoryCreateRequest,
    CategoryUpdateRequest,
    PaginatedCategoryAdminResponse,
    PaginatedProductAdminResponse,
    ProductAdminResponse,
    ProductCreateRequest,
    ProductImageResponse,
    ProductImageUpdateRequest,
    ProductStatusUpdateRequest,
    ProductUpdateRequest,
    SaleAdminResponse,
    SaleCreateRequest,
    SaleUpdateRequest,
)
from app.services.catalog_service import (
    create_admin_category,
    create_admin_product,
    create_product_sale,
    delete_admin_category,
    delete_admin_product,
    delete_product_asset,
    delete_product_image,
    get_admin_category,
    get_admin_product,
    list_admin_categories,
    list_admin_products,
    moderate_admin_product,
    record_admin_audit,
    replace_product_image,
    update_admin_category,
    update_admin_product,
    update_admin_product_status,
    update_product_image,
    update_product_sale,
    upload_product_asset,
    upload_product_image,
)
from app.services.storage_service import get_image_storage

router = APIRouter(prefix="/admin", tags=["Admin Catalog & Product Management"])


# ---------------------------------------------------------------------------
# CATEGORY ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=PaginatedCategoryAdminResponse)
def admin_list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=120),
    is_active: Optional[bool] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedCategoryAdminResponse:
    return list_admin_categories(
        db=db, page=page, page_size=page_size, search=search, is_active=is_active
    )


@router.get("/categories/{category_id}", response_model=CategoryAdminResponse)
def admin_get_category(
    category_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CategoryAdminResponse:
    return get_admin_category(db=db, category_id=category_id)


@router.post(
    "/categories",
    response_model=CategoryAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_category(
    payload: CategoryCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CategoryAdminResponse:
    created = create_admin_category(
        db=db, admin=admin, payload=payload, ip_address=get_client_ip(request)
    )
    db.commit()
    return created


@router.patch("/categories/{category_id}", response_model=CategoryAdminResponse)
def admin_update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CategoryAdminResponse:
    updated = update_admin_category(
        db=db,
        admin=admin,
        category_id=category_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.delete("/categories/{category_id}", response_model=GenericMessageResponse)
def admin_delete_category(
    category_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_admin_category(
        db=db, admin=admin, category_id=category_id, ip_address=get_client_ip(request)
    )
    db.commit()
    return GenericMessageResponse(message="Category deleted successfully.")


@router.post(
    "/uploads/images",
    status_code=status.HTTP_201_CREATED,
)
def admin_upload_standalone_image(
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Generic admin image upload endpoint (for category cover images or previews)."""
    image_url = get_image_storage().save_image(file)
    record_admin_audit(
        db=db,
        admin=admin,
        action="media.image_uploaded",
        entity_type="media",
        entity_id=image_url,
        details={"image_url": image_url},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"image_url": image_url}


# ---------------------------------------------------------------------------
# PRODUCT ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/products", response_model=PaginatedProductAdminResponse)
def admin_list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    category_id: Optional[uuid.UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    approval_status: Optional[ProductApprovalStatus] = Query(default=None),
    owner_type: Optional[Literal["platform", "seller"]] = Query(default=None),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedProductAdminResponse:
    return list_admin_products(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        is_active=is_active,
        seller_id=seller_id,
        approval_status=approval_status,
        owner_type=owner_type,
    )


@router.get("/products/{product_id}", response_model=ProductAdminResponse)
def admin_get_product(
    product_id: uuid.UUID,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    return get_admin_product(db=db, product_id=product_id)


@router.post(
    "/products",
    response_model=ProductAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_product(
    payload: ProductCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    created = create_admin_product(
        db=db, admin=admin, payload=payload, ip_address=get_client_ip(request)
    )
    db.commit()
    return created


@router.patch("/products/{product_id}", response_model=ProductAdminResponse)
def admin_update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    updated = update_admin_product(
        db=db,
        admin=admin,
        product_id=product_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.patch("/products/{product_id}/status", response_model=ProductAdminResponse)
def admin_change_product_status(
    product_id: uuid.UUID,
    payload: ProductStatusUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    updated = update_admin_product_status(
        db=db,
        admin=admin,
        product_id=product_id,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.post("/products/{product_id}/moderate", response_model=ProductAdminResponse)
def admin_moderate_product(
    product_id: uuid.UUID,
    payload: AdminProductModerationRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    updated = moderate_admin_product(
        db=db,
        admin=admin,
        product_id=product_id,
        action=payload.action,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.delete("/products/{product_id}", response_model=GenericMessageResponse)
def admin_delete_product(
    product_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_admin_product(
        db=db, admin=admin, product_id=product_id, ip_address=get_client_ip(request)
    )
    db.commit()
    return GenericMessageResponse(message="Product deleted successfully.")


# ---------------------------------------------------------------------------
# PRIVATE DIGITAL PRODUCT ASSET ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/products/{product_id}/asset",
    response_model=ProductAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_upload_product_asset(
    product_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    """Upload or replace the private binary digital product file stored in private asset storage."""
    updated = upload_product_asset(
        db=db,
        admin=admin,
        product_id=product_id,
        file=file,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.delete(
    "/products/{product_id}/asset",
    response_model=ProductAdminResponse,
)
def admin_delete_product_asset(
    product_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductAdminResponse:
    """Remove an unpurchased product's private digital asset file."""
    updated = delete_product_asset(
        db=db,
        admin=admin,
        product_id=product_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


# ---------------------------------------------------------------------------
# PRODUCT IMAGE ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_upload_product_image(
    product_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    display_order: Optional[int] = Form(default=None),
    is_primary: bool = Form(default=False),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    created = upload_product_image(
        db=db,
        admin=admin,
        product_id=product_id,
        file=file,
        display_order=display_order,
        is_primary=is_primary,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return created


@router.patch(
    "/products/{product_id}/images/{image_id}",
    response_model=ProductImageResponse,
)
def admin_update_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    payload: ProductImageUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    updated = update_product_image(
        db=db,
        admin=admin,
        product_id=product_id,
        image_id=image_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated


@router.put(
    "/products/{product_id}/images/{image_id}",
    response_model=ProductImageResponse,
)
def admin_replace_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    replaced = replace_product_image(
        db=db,
        admin=admin,
        product_id=product_id,
        image_id=image_id,
        file=file,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return replaced


@router.delete(
    "/products/{product_id}/images/{image_id}",
    response_model=GenericMessageResponse,
)
def admin_delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    delete_product_image(
        db=db,
        admin=admin,
        product_id=product_id,
        image_id=image_id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return GenericMessageResponse(message="Product image deleted successfully.")


# ---------------------------------------------------------------------------
# PRODUCT SALES & DISCOUNT ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/products/{product_id}/sales",
    response_model=SaleAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_product_sale(
    product_id: uuid.UUID,
    payload: SaleCreateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SaleAdminResponse:
    created = create_product_sale(
        db=db,
        admin=admin,
        product_id=product_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return created


@router.patch(
    "/products/{product_id}/sales/{sale_id}",
    response_model=SaleAdminResponse,
)
def admin_update_product_sale(
    product_id: uuid.UUID,
    sale_id: uuid.UUID,
    payload: SaleUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SaleAdminResponse:
    updated = update_product_sale(
        db=db,
        admin=admin,
        product_id=product_id,
        sale_id=sale_id,
        payload=payload,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return updated
