import uuid
from decimal import Decimal
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import AdDisplayPosition
from app.schemas.catalog import (
    CategoryPublicResponse,
    PaginatedCategoryPublicResponse,
    PaginatedProductPublicResponse,
    ProductPublicResponse,
)
from app.schemas.operations import AdVideoResponse, BannerResponse
from app.schemas.seller import PaginatedSellerDirectoryResponse, SellerPublicStorefrontResponse
from app.services.catalog_service import (
    get_public_category_by_slug,
    get_public_product_by_slug,
    list_public_categories,
    list_public_products,
)
from app.services.operations_service import (
    get_public_store_settings,
    list_public_banners,
    list_public_videos,
)
from app.services.seller_service import get_public_seller_storefront, list_public_sellers
from app.services.storage_service import get_image_storage

router = APIRouter(tags=["Public Product Catalog"])


@router.get("/categories", response_model=PaginatedCategoryPublicResponse)
def public_list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
) -> PaginatedCategoryPublicResponse:
    return list_public_categories(db=db, page=page, page_size=page_size, search=search)


@router.get("/categories/{slug}", response_model=CategoryPublicResponse)
def public_get_category(
    slug: str,
    db: Session = Depends(get_db),
) -> CategoryPublicResponse:
    return get_public_category_by_slug(db=db, slug=slug)


@router.get("/products", response_model=PaginatedProductPublicResponse)
def public_list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=60),
    search: Optional[str] = Query(default=None, max_length=200),
    category: Optional[str] = Query(default=None, max_length=140, description="Category slug filter"),
    category_id: Optional[uuid.UUID] = Query(default=None),
    seller: Optional[str] = Query(default=None, max_length=160, description="Seller store slug filter"),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    owner_type: Optional[Literal["platform", "seller"]] = Query(default=None),
    min_price: Optional[Decimal] = Query(default=None, ge=Decimal("0.00")),
    max_price: Optional[Decimal] = Query(default=None, ge=Decimal("0.00")),
    on_sale: Optional[bool] = Query(default=None, description="Filter by currently active promotional sale"),
    sort_by: Literal["newest", "price_asc", "price_desc", "popularity"] = Query(default="newest"),
    db: Session = Depends(get_db),
) -> PaginatedProductPublicResponse:
    return list_public_products(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category,
        category_id=category_id,
        seller_slug=seller,
        seller_id=seller_id,
        owner_type=owner_type,
        min_price=min_price,
        max_price=max_price,
        on_sale=on_sale,
        sort_by=sort_by,
    )


@router.get("/products/{slug}", response_model=ProductPublicResponse)
def public_get_product(
    slug: str,
    db: Session = Depends(get_db),
) -> ProductPublicResponse:
    return get_public_product_by_slug(db=db, slug=slug)


@router.get("/stores", response_model=PaginatedSellerDirectoryResponse)
def public_list_stores(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=60),
    search: Optional[str] = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
) -> PaginatedSellerDirectoryResponse:
    return list_public_sellers(db=db, page=page, page_size=page_size, search=search)


@router.get("/stores/{store_slug}", response_model=SellerPublicStorefrontResponse)
def public_get_storefront(
    store_slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=60),
    search: Optional[str] = Query(default=None, max_length=200),
    category: Optional[str] = Query(default=None, max_length=140),
    sort_by: Literal["newest", "price_asc", "price_desc", "popularity"] = Query(default="newest"),
    db: Session = Depends(get_db),
) -> SellerPublicStorefrontResponse:
    return get_public_seller_storefront(
        db=db,
        store_slug=store_slug,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category,
        sort_by=sort_by,
    )


@router.get("/uploads/images/{filename}")
def serve_uploaded_image(filename: str) -> FileResponse:
    """Safely serve public product/category image assets with strict path-traversal protection."""
    local_path = get_image_storage().resolve_local_path(filename)
    ext = local_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    return FileResponse(
        path=local_path,
        media_type=media_type_map.get(ext, "application/octet-stream"),
        headers={
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/banners", response_model=list[BannerResponse])
def public_get_active_banners(
    db: Session = Depends(get_db),
) -> list[BannerResponse]:
    """Return active and scheduled promotional banners ordered by priority."""
    return list_public_banners(db=db)


@router.get("/videos", response_model=list[AdVideoResponse])
def public_get_active_videos(
    position: Optional[AdDisplayPosition] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AdVideoResponse]:
    """Return active promotional videos optionally filtered by display position."""
    return list_public_videos(db=db, position=position)


@router.get("/settings/public")
def public_get_store_settings(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return non-sensitive public store settings (`store.*` keys)."""
    return get_public_store_settings(db=db)

