import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin import Admin, AuditLog
from app.models.catalog import Category, Product, ProductImage, Sale
from app.models.customer import Customer
from app.models.enums import (
    AccountStatus,
    OrderPaymentStatus,
    ProductApprovalStatus,
    SellerApplicationStatus,
)
from app.models.order import DownloadRecord, Order, OrderItem
from app.models.seller import SellerProfile
from app.schemas.catalog import (
    ActiveDiscountPublicResponse,
    CategoryAdminResponse,
    CategoryCreateRequest,
    CategoryPublicResponse,
    CategorySummary,
    CategoryUpdateRequest,
    PaginatedCategoryAdminResponse,
    PaginatedCategoryPublicResponse,
    PaginatedProductAdminResponse,
    PaginatedProductPublicResponse,
    ProductAdminResponse,
    ProductAssetAdminResponse,
    ProductCreateRequest,
    ProductImageResponse,
    ProductImageUpdateRequest,
    ProductPublicResponse,
    ProductUpdateRequest,
    PublicCategorySummary,
    SaleAdminResponse,
    SaleCreateRequest,
    SaleUpdateRequest,
    SellerPublicBadge,
    slugify,
)
from app.services.asset_storage_service import (
    AssetStorageError,
    get_asset_storage,
    validate_and_spool_asset_upload,
)
from app.services.storage_service import get_image_storage


def record_admin_audit(
    db: Session,
    admin: Admin,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Append an immutable audit log record without sensitive fields (never logs private URLs or keys)."""
    safe_details = dict(details or {})
    safe_details.pop("private_download_url", None)
    safe_details.pop("asset_storage_key", None)
    if ip_address:
        safe_details["ip"] = ip_address

    db.add(
        AuditLog(
            admin_id=admin.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=safe_details,
        )
    )


def _calc_discount_percentage(original: Decimal, discounted: Decimal) -> Decimal:
    if original <= Decimal("0.00"):
        return Decimal("0.00")
    pct = ((original - discounted) / original) * Decimal("100.00")
    return pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_sale_admin_response(sale: Sale, now: Optional[datetime] = None) -> SaleAdminResponse:
    ref_now = now or datetime.now(timezone.utc)
    orig = Decimal(str(sale.original_price_snapshot))
    disc = Decimal(str(sale.discounted_price))
    diff = max(Decimal("0.00"), orig - disc)
    is_live = bool(
        sale.is_active
        and sale.starts_at <= ref_now < sale.expires_at
        and disc < orig
    )
    return SaleAdminResponse(
        id=sale.id,
        product_id=sale.product_id,
        original_price_snapshot=orig,
        discounted_price=disc,
        discount_amount=diff,
        discount_percentage=_calc_discount_percentage(orig, disc),
        starts_at=sale.starts_at,
        expires_at=sale.expires_at,
        is_active=sale.is_active,
        is_currently_live=is_live,
        created_at=sale.created_at,
    )


def compute_product_pricing(
    product: Product, now: Optional[datetime] = None
) -> tuple[Decimal, bool, Optional[ActiveDiscountPublicResponse]]:
    """Compute backend-authoritative effective price and active discount for a product."""
    ref_now = now or datetime.now(timezone.utc)
    orig_price = Decimal(str(product.original_price))

    live_sale: Optional[Sale] = None
    for s in product.sales or []:
        if (
            s.is_active
            and s.starts_at <= ref_now < s.expires_at
            and Decimal(str(s.discounted_price)) < orig_price
        ):
            live_sale = s
            break

    if not live_sale:
        return orig_price, False, None

    disc_price = Decimal(str(live_sale.discounted_price))
    discount_amount = (orig_price - disc_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    discount_pct = _calc_discount_percentage(orig_price, disc_price)

    active_discount = ActiveDiscountPublicResponse(
        sale_id=live_sale.id,
        original_price=orig_price,
        discounted_price=disc_price,
        discount_amount=discount_amount,
        discount_percentage=discount_pct,
        starts_at=live_sale.starts_at,
        expires_at=live_sale.expires_at,
    )
    return disc_price, True, active_discount


def _resolve_primary_image_url(product: Product) -> Optional[str]:
    if product.images:
        for img in product.images:
            if img.is_primary:
                return img.image_url
        if not product.image_url:
            return product.images[0].image_url
    return product.image_url


def _to_product_asset_admin_response(product: Product) -> ProductAssetAdminResponse:
    has_asset = bool(product.asset_storage_key)
    if not has_asset:
        return ProductAssetAdminResponse(has_asset=False)
    return ProductAssetAdminResponse(
        has_asset=True,
        filename=product.asset_original_filename,
        content_type=product.asset_content_type,
        size_bytes=product.asset_size_bytes,
        sha256=product.asset_sha256,
        storage_backend=product.asset_storage_backend,
        uploaded_at=product.asset_uploaded_at,
    )


def _to_seller_badge(product: Product) -> Optional[SellerPublicBadge]:
    if not product.seller:
        return None
    return SellerPublicBadge.model_validate(product.seller)


def is_product_publicly_visible(product: Product) -> bool:
    """True when product, category, and owning seller (if any) are active and approved for sale."""
    if not product or not product.is_active:
        return False
    if product.approval_status != ProductApprovalStatus.PUBLISHED:
        return False
    if not product.category or not product.category.is_active:
        return False
    if product.seller_id is not None:
        if not product.seller or product.seller.application_status != SellerApplicationStatus.APPROVED:
            return False
        if product.seller.customer and product.seller.customer.account_status != AccountStatus.ACTIVE:
            return False
    return True


def to_product_admin_response(product: Product) -> ProductAdminResponse:
    now = datetime.now(timezone.utc)
    effective_price, is_live_sale, active_discount = compute_product_pricing(product, now)
    sorted_images = sorted(product.images or [], key=lambda i: (i.display_order, str(i.id)))
    sorted_sales = sorted(product.sales or [], key=lambda s: s.created_at, reverse=True)

    return ProductAdminResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        category_id=product.category_id,
        category=CategorySummary.model_validate(product.category) if product.category else None,
        seller_id=product.seller_id,
        seller=_to_seller_badge(product),
        approval_status=product.approval_status,
        rejection_reason=product.rejection_reason,
        submitted_for_review_at=product.submitted_for_review_at,
        reviewed_at=product.reviewed_at,
        image_url=_resolve_primary_image_url(product),
        short_description=product.short_description,
        main_description=product.main_description,
        detailed_description=product.detailed_description,
        original_price=Decimal(str(product.original_price)),
        effective_price=effective_price,
        is_on_sale=is_live_sale,
        is_active=product.is_active,
        product_type=product.product_type,
        metadata=product.product_metadata,
        private_download_url=product.private_download_url,
        asset=_to_product_asset_admin_response(product),
        images=[ProductImageResponse.model_validate(img) for img in sorted_images],
        sales=[to_sale_admin_response(s, now) for s in sorted_sales],
        active_discount=active_discount,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


_FORBIDDEN_PUBLIC_META_FRAGMENTS = (
    "secret",
    "private",
    "token",
    "key",
    "url",
    "path",
    "password",
    "internal",
    "bucket",
)


def _sanitize_public_metadata(raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not raw or not isinstance(raw, dict):
        return None
    clean: dict[str, Any] = {}
    for k, v in raw.items():
        kl = str(k).strip().lower()
        if any(frag in kl for frag in _FORBIDDEN_PUBLIC_META_FRAGMENTS):
            continue
        if isinstance(v, str) and any(
            frag in v.lower() for frag in ("private_download", "storage.", "s3://", "supabase")
        ):
            continue
        clean[str(k)] = v
    return clean or None


def to_product_public_response(product: Product) -> ProductPublicResponse:
    now = datetime.now(timezone.utc)
    effective_price, is_live_sale, active_discount = compute_product_pricing(product, now)
    sorted_images = sorted(product.images or [], key=lambda i: (i.display_order, str(i.id)))

    return ProductPublicResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        category=PublicCategorySummary.model_validate(product.category),
        seller=_to_seller_badge(product),
        is_platform_product=product.seller_id is None,
        image_url=_resolve_primary_image_url(product),
        images=[ProductImageResponse.model_validate(img) for img in sorted_images],
        short_description=product.short_description,
        main_description=product.main_description,
        detailed_description=product.detailed_description,
        product_type=product.product_type,
        metadata=_sanitize_public_metadata(product.product_metadata),
        original_price=Decimal(str(product.original_price)),
        effective_price=effective_price,
        is_on_sale=is_live_sale,
        active_discount=active_discount,
        is_available=is_product_publicly_visible(product),
        created_at=product.created_at,
    )


def _public_visibility_sql_conditions() -> list[Any]:
    return [
        Product.is_active.is_(True),
        Product.approval_status == ProductApprovalStatus.PUBLISHED,
        Category.is_active.is_(True),
        or_(
            Product.seller_id.is_(None),
            (
                (SellerProfile.application_status == SellerApplicationStatus.APPROVED)
                & (Customer.account_status == AccountStatus.ACTIVE)
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# CATEGORY MANAGEMENT (ADMIN)
# ---------------------------------------------------------------------------


def _category_product_counts(db: Session, category_ids: list[uuid.UUID], active_only: bool = False) -> dict[uuid.UUID, int]:
    if not category_ids:
        return {}
    stmt = (
        select(Product.category_id, func.count(Product.id))
        .where(Product.category_id.in_(category_ids))
        .group_by(Product.category_id)
    )
    if active_only:
        stmt = (
            stmt.join(Category, Product.category_id == Category.id)
            .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
            .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
            .where(*_public_visibility_sql_conditions())
        )
    return {cid: cnt for cid, cnt in db.execute(stmt).all()}


def list_admin_categories(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> PaginatedCategoryAdminResponse:
    stmt: Select = select(Category)
    count_stmt: Select = select(func.count(Category.id))

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = or_(Category.name.ilike(q), Category.slug.ilike(q), Category.description.ilike(q))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if is_active is not None:
        stmt = stmt.where(Category.is_active.is_(is_active))
        count_stmt = count_stmt.where(Category.is_active.is_(is_active))

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    rows = db.scalars(stmt.order_by(Category.name.asc()).offset(offset).limit(page_size)).all()
    counts = _category_product_counts(db, [c.id for c in rows], active_only=False)

    items = [
        CategoryAdminResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            image_url=c.image_url,
            is_active=c.is_active,
            product_count=counts.get(c.id, 0),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in rows
    ]
    return PaginatedCategoryAdminResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_admin_category(db: Session, category_id: uuid.UUID) -> CategoryAdminResponse:
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    prod_count = (
        db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    )
    return CategoryAdminResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        image_url=category.image_url,
        is_active=category.is_active,
        product_count=prod_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def create_admin_category(
    db: Session,
    admin: Admin,
    payload: CategoryCreateRequest,
    ip_address: Optional[str] = None,
) -> CategoryAdminResponse:
    try:
        resolved_slug = payload.slug or slugify(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    dup_name = db.scalar(
        select(Category).where(func.lower(Category.name) == payload.name.lower())
    )
    if dup_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists.",
        )

    dup_slug = db.scalar(select(Category).where(Category.slug == resolved_slug))
    if dup_slug:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this slug already exists.",
        )

    category = Category(
        name=payload.name,
        slug=resolved_slug,
        description=payload.description,
        image_url=payload.image_url,
        is_active=payload.is_active,
    )
    db.add(category)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="category.created",
        entity_type="category",
        entity_id=category.id,
        details={"name": category.name, "slug": category.slug, "is_active": category.is_active},
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_category(db, category.id)


def update_admin_category(
    db: Session,
    admin: Admin,
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    ip_address: Optional[str] = None,
) -> CategoryAdminResponse:
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    changed: dict[str, Any] = {}
    if payload.name is not None and payload.name != category.name:
        dup_name = db.scalar(
            select(Category).where(
                func.lower(Category.name) == payload.name.lower(),
                Category.id != category.id,
            )
        )
        if dup_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this name already exists.",
            )
        category.name = payload.name
        changed["name"] = payload.name

    if payload.slug is not None and payload.slug != category.slug:
        dup_slug = db.scalar(
            select(Category).where(
                Category.slug == payload.slug,
                Category.id != category.id,
            )
        )
        if dup_slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this slug already exists.",
            )
        category.slug = payload.slug
        changed["slug"] = payload.slug

    if payload.description is not None:
        category.description = payload.description
        changed["description_updated"] = True

    if payload.image_url is not None:
        category.image_url = payload.image_url or None
        changed["image_url"] = category.image_url

    if payload.is_active is not None and payload.is_active != category.is_active:
        category.is_active = payload.is_active
        changed["is_active"] = payload.is_active

    record_admin_audit(
        db=db,
        admin=admin,
        action="category.updated",
        entity_type="category",
        entity_id=category.id,
        details=changed,
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_category(db, category.id)


def delete_admin_category(
    db: Session,
    admin: Admin,
    category_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> None:
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    prod_count = (
        db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    )
    if prod_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete category '{category.name}' because {prod_count} product(s) are assigned to it.",
        )

    cat_name = category.name
    cat_slug = category.slug
    db.delete(category)
    record_admin_audit(
        db=db,
        admin=admin,
        action="category.deleted",
        entity_type="category",
        entity_id=category_id,
        details={"name": cat_name, "slug": cat_slug},
        ip_address=ip_address,
    )
    db.flush()


# ---------------------------------------------------------------------------
# PRODUCT MANAGEMENT (ADMIN)
# ---------------------------------------------------------------------------


def _load_product_with_relations(
    db: Session,
    product_id: uuid.UUID,
    for_update: bool = False,
    required_seller_id: Optional[uuid.UUID] = None,
) -> Product:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.seller).selectinload(SellerProfile.customer),
            selectinload(Product.images),
            selectinload(Product.sales),
        )
        .where(Product.id == product_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        stmt = stmt.with_for_update()
    product = db.scalar(stmt)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    if required_seller_id is not None and product.seller_id != required_seller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access or modify this product.",
        )
    return product


def list_admin_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    seller_id: Optional[uuid.UUID] = None,
    approval_status: Optional[ProductApprovalStatus] = None,
    owner_type: Optional[str] = None,
) -> PaginatedProductAdminResponse:
    stmt: Select = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.seller).selectinload(SellerProfile.customer),
        selectinload(Product.images),
        selectinload(Product.sales),
    )
    count_stmt: Select = select(func.count(Product.id))

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = or_(
            Product.name.ilike(q),
            Product.slug.ilike(q),
            Product.short_description.ilike(q),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)

    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
        count_stmt = count_stmt.where(Product.is_active.is_(is_active))

    if seller_id is not None:
        stmt = stmt.where(Product.seller_id == seller_id)
        count_stmt = count_stmt.where(Product.seller_id == seller_id)

    if approval_status is not None:
        stmt = stmt.where(Product.approval_status == approval_status)
        count_stmt = count_stmt.where(Product.approval_status == approval_status)

    if owner_type == "platform":
        stmt = stmt.where(Product.seller_id.is_(None))
        count_stmt = count_stmt.where(Product.seller_id.is_(None))
    elif owner_type == "seller":
        stmt = stmt.where(Product.seller_id.is_not(None))
        count_stmt = count_stmt.where(Product.seller_id.is_not(None))

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    products = db.scalars(
        stmt.order_by(Product.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .execution_options(populate_existing=True)
    ).all()

    return PaginatedProductAdminResponse(
        items=[to_product_admin_response(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_admin_product(db: Session, product_id: uuid.UUID) -> ProductAdminResponse:
    product = _load_product_with_relations(db, product_id)
    return to_product_admin_response(product)


def create_admin_product(
    db: Session,
    admin: Admin,
    payload: ProductCreateRequest,
    ip_address: Optional[str] = None,
) -> ProductAdminResponse:
    category = db.get(Category, payload.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected category does not exist.",
        )

    try:
        resolved_slug = payload.slug or slugify(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    dup_slug = db.scalar(select(Product).where(Product.slug == resolved_slug))
    if dup_slug:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists.",
        )

    product = Product(
        name=payload.name,
        slug=resolved_slug,
        category_id=payload.category_id,
        seller_id=None,
        approval_status=(
            ProductApprovalStatus.PUBLISHED if payload.is_active else ProductApprovalStatus.DRAFT
        ),
        reviewed_at=datetime.now(timezone.utc) if payload.is_active else None,
        reviewed_by_admin_id=admin.id if payload.is_active else None,
        image_url=payload.image_url,
        short_description=payload.short_description,
        main_description=payload.main_description,
        detailed_description=payload.detailed_description,
        original_price=payload.original_price,
        product_type=payload.product_type,
        product_metadata=payload.metadata,
        is_on_sale=False,
        is_active=payload.is_active,
        private_download_url=payload.private_download_url,
    )
    db.add(product)
    db.flush()

    record_admin_audit(
        db=db,
        admin=admin,
        action="product.created",
        entity_type="product",
        entity_id=product.id,
        details={
            "name": product.name,
            "slug": product.slug,
            "category_id": str(product.category_id),
            "original_price": str(product.original_price),
            "is_active": product.is_active,
            "has_private_download_url": bool(product.private_download_url),
        },
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_product(db, product.id)


def update_admin_product(
    db: Session,
    admin: Admin,
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    ip_address: Optional[str] = None,
) -> ProductAdminResponse:
    product = _load_product_with_relations(db, product_id)
    changed: dict[str, Any] = {}

    if payload.category_id is not None and payload.category_id != product.category_id:
        cat = db.get(Category, payload.category_id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected category does not exist.",
            )
        product.category_id = payload.category_id
        changed["category_id"] = str(payload.category_id)

    if payload.name is not None and payload.name != product.name:
        product.name = payload.name
        changed["name"] = payload.name

    if payload.slug is not None and payload.slug != product.slug:
        dup_slug = db.scalar(
            select(Product).where(Product.slug == payload.slug, Product.id != product.id)
        )
        if dup_slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this slug already exists.",
            )
        product.slug = payload.slug
        changed["slug"] = payload.slug

    if payload.original_price is not None and payload.original_price != product.original_price:
        # Ensure any currently active sale still has discounted_price < new original_price
        for s in product.sales or []:
            if s.is_active and Decimal(str(s.discounted_price)) >= payload.original_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New original price must be greater than the active discount price.",
                )
        product.original_price = payload.original_price
        changed["original_price"] = str(payload.original_price)

    if payload.image_url is not None:
        product.image_url = payload.image_url or None
        changed["image_url"] = product.image_url

    if payload.short_description is not None:
        product.short_description = payload.short_description
        changed["short_description_updated"] = True

    if payload.main_description is not None:
        product.main_description = payload.main_description
        changed["main_description_updated"] = True

    if payload.detailed_description is not None:
        product.detailed_description = payload.detailed_description
        changed["detailed_description_updated"] = True

    if payload.product_type is not None:
        product.product_type = payload.product_type or None
        changed["product_type"] = product.product_type

    if payload.metadata is not None:
        product.product_metadata = payload.metadata
        changed["metadata_updated"] = True

    if payload.is_active is not None and payload.is_active != product.is_active:
        product.is_active = payload.is_active
        changed["is_active"] = payload.is_active

    if payload.private_download_url is not None and not product.asset_storage_key:
        product.private_download_url = payload.private_download_url or None
        changed["private_download_url_updated"] = True

    record_admin_audit(
        db=db,
        admin=admin,
        action="product.updated",
        entity_type="product",
        entity_id=product.id,
        details=changed,
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_product(db, product.id)


def update_admin_product_status(
    db: Session,
    admin: Admin,
    product_id: uuid.UUID,
    is_active: bool,
    ip_address: Optional[str] = None,
) -> ProductAdminResponse:
    product = _load_product_with_relations(db, product_id)
    product.is_active = is_active
    if is_active and product.approval_status in (ProductApprovalStatus.DRAFT, ProductApprovalStatus.PENDING_REVIEW):
        product.approval_status = ProductApprovalStatus.PUBLISHED
        product.reviewed_at = datetime.now(timezone.utc)
        product.reviewed_by_admin_id = admin.id

    record_admin_audit(
        db=db,
        admin=admin,
        action="product.status_changed",
        entity_type="product",
        entity_id=product.id,
        details={"is_active": is_active, "slug": product.slug},
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_product(db, product.id)


def moderate_admin_product(
    db: Session,
    admin: Admin,
    product_id: uuid.UUID,
    action: str,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> ProductAdminResponse:
    """Approve, reject, unpublish, or restore a marketplace product listing."""
    product = _load_product_with_relations(db, product_id, for_update=True)
    now = datetime.now(timezone.utc)
    cleaned_reason = (reason or "").strip() or None

    if action == "approve":
        if product.seller and product.seller.application_status != SellerApplicationStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve a product belonging to a non-approved seller.",
            )
        product.approval_status = ProductApprovalStatus.PUBLISHED
        product.is_active = True
        product.rejection_reason = None
        product.reviewed_at = now
        product.reviewed_by_admin_id = admin.id
        audit_action = "product.moderation_approved"
    elif action == "reject":
        if not cleaned_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A rejection reason is required when rejecting a product.",
            )
        product.approval_status = ProductApprovalStatus.REJECTED
        product.is_active = False
        product.rejection_reason = cleaned_reason
        product.reviewed_at = now
        product.reviewed_by_admin_id = admin.id
        audit_action = "product.moderation_rejected"
    elif action == "unpublish":
        product.is_active = False
        if product.approval_status == ProductApprovalStatus.PUBLISHED:
            product.approval_status = ProductApprovalStatus.DRAFT
        if cleaned_reason:
            product.rejection_reason = cleaned_reason
        product.reviewed_at = now
        product.reviewed_by_admin_id = admin.id
        audit_action = "product.moderation_unpublished"
    elif action == "restore":
        product.approval_status = ProductApprovalStatus.PUBLISHED
        product.is_active = True
        product.rejection_reason = None
        product.reviewed_at = now
        product.reviewed_by_admin_id = admin.id
        audit_action = "product.moderation_restored"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported moderation action.")

    record_admin_audit(
        db=db,
        admin=admin,
        action=audit_action,
        entity_type="product",
        entity_id=product.id,
        details={
            "slug": product.slug,
            "seller_id": str(product.seller_id) if product.seller_id else None,
            "approval_status": product.approval_status.value,
            "is_active": product.is_active,
            "reason": cleaned_reason,
        },
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_product(db, product.id)


def delete_admin_product(
    db: Session,
    admin: Admin,
    product_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> None:
    product = _load_product_with_relations(db, product_id)

    order_refs = (
        db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product.id)) or 0
    )
    download_refs = (
        db.scalar(
            select(func.count(DownloadRecord.id)).where(DownloadRecord.product_id == product.id)
        )
        or 0
    )
    if order_refs > 0 or download_refs > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete product because it is referenced by historical orders or downloads. "
                "Deactivate the product instead to preserve transaction history."
            ),
        )

    storage = get_image_storage()
    image_urls_to_clean = [img.image_url for img in (product.images or [])]
    if product.image_url:
        image_urls_to_clean.append(product.image_url)
    asset_key_to_clean = product.asset_storage_key
    asset_backend_to_clean = product.asset_storage_backend

    p_name = product.name
    p_slug = product.slug
    db.delete(product)
    record_admin_audit(
        db=db,
        admin=admin,
        action="product.deleted",
        entity_type="product",
        entity_id=product_id,
        details={"name": p_name, "slug": p_slug},
        ip_address=ip_address,
    )
    db.flush()

    for url in image_urls_to_clean:
        storage.delete_image(url)
    if asset_key_to_clean:
        try:
            get_asset_storage(asset_backend_to_clean).delete(asset_key_to_clean)
        except AssetStorageError:
            pass


# ---------------------------------------------------------------------------
# PRIVATE DIGITAL PRODUCT ASSET MANAGEMENT (ADMIN)
# ---------------------------------------------------------------------------


def upload_product_asset(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    file: UploadFile,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> ProductAdminResponse:
    """Validate, scan magic bytes, and store a private binary digital product asset."""
    product = _load_product_with_relations(
        db, product_id, for_update=True, required_seller_id=required_seller_id
    )
    spooled = validate_and_spool_asset_upload(file, product_id=product.id)

    old_storage_key = product.asset_storage_key
    old_storage_backend = product.asset_storage_backend
    stored_meta = None

    try:
        try:
            storage = get_asset_storage()
            stored_meta = storage.save(
                file_obj=spooled.spool,
                storage_key=spooled.storage_key,
                content_type=spooled.content_type,
                size_bytes=spooled.size_bytes,
                sha256_hex=spooled.sha256,
            )
        except AssetStorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Digital asset storage service is temporarily unavailable.",
            ) from exc

        try:
            product.asset_storage_backend = stored_meta.storage_backend
            product.asset_storage_key = stored_meta.storage_key
            product.asset_original_filename = spooled.display_filename
            product.asset_content_type = spooled.content_type
            product.asset_size_bytes = stored_meta.size_bytes
            product.asset_sha256 = spooled.sha256
            product.asset_uploaded_at = datetime.now(timezone.utc)
            product.private_download_url = "asset://managed"

            if admin is not None:
                record_admin_audit(
                    db=db,
                    admin=admin,
                    action="product.asset_uploaded",
                    entity_type="product",
                    entity_id=product.id,
                    details={
                        "filename": spooled.display_filename,
                        "content_type": spooled.content_type,
                        "size_bytes": stored_meta.size_bytes,
                        "sha256": spooled.sha256,
                        "storage_backend": stored_meta.storage_backend,
                        "replaced_existing": bool(old_storage_key),
                    },
                    ip_address=ip_address,
                )
            db.flush()
        except Exception:
            if stored_meta is not None:
                try:
                    storage.delete(stored_meta.storage_key)
                except AssetStorageError:
                    pass
            raise

        if old_storage_key and old_storage_key != stored_meta.storage_key:
            try:
                get_asset_storage(old_storage_backend).delete(old_storage_key)
            except AssetStorageError:
                pass

        return to_product_admin_response(product)
    finally:
        spooled.close()


def delete_product_asset(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> ProductAdminResponse:
    """Remove an attached private digital asset only if no paid orders rely on it."""
    product = _load_product_with_relations(
        db, product_id, for_update=True, required_seller_id=required_seller_id
    )
    if not product.asset_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No digital asset file is attached to this product.",
        )

    paid_order_count = (
        db.scalar(
            select(func.count(OrderItem.id))
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                OrderItem.product_id == product.id,
                Order.payment_status == OrderPaymentStatus.PAID,
            )
        )
        or 0
    )
    if paid_order_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete digital asset because verified paid orders depend on this product. "
                "Upload a replacement file instead so existing purchasers retain access."
            ),
        )

    old_storage_key = product.asset_storage_key
    old_storage_backend = product.asset_storage_backend
    old_filename = product.asset_original_filename

    product.asset_storage_backend = None
    product.asset_storage_key = None
    product.asset_original_filename = None
    product.asset_content_type = None
    product.asset_size_bytes = None
    product.asset_sha256 = None
    product.asset_uploaded_at = None
    if product.private_download_url == "asset://managed":
        product.private_download_url = None

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="product.asset_deleted",
            entity_type="product",
            entity_id=product.id,
            details={"deleted_filename": old_filename},
            ip_address=ip_address,
        )
    db.flush()

    try:
        get_asset_storage(old_storage_backend).delete(old_storage_key)
    except AssetStorageError:
        pass

    return to_product_admin_response(product)


# ---------------------------------------------------------------------------
# PRODUCT IMAGE MANAGEMENT (ADMIN)
# ---------------------------------------------------------------------------


def _sync_product_primary_image(product: Product) -> None:
    if not product.images:
        return
    primaries = [img for img in product.images if img.is_primary]
    if primaries:
        product.image_url = primaries[0].image_url
    else:
        ordered = sorted(product.images, key=lambda i: (i.display_order, str(i.id)))
        ordered[0].is_primary = True
        product.image_url = ordered[0].image_url


def upload_product_image(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    file: UploadFile,
    display_order: Optional[int] = None,
    is_primary: bool = False,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> ProductImageResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    storage = get_image_storage()
    image_url = storage.save_image(file)

    existing_orders = [img.display_order for img in (product.images or [])]
    if display_order is None:
        resolved_order = (max(existing_orders) + 1) if existing_orders else 0
    else:
        resolved_order = max(0, display_order)
        if resolved_order in existing_orders:
            resolved_order = max(existing_orders) + 1

    should_be_primary = is_primary or not product.images
    if should_be_primary:
        for img in product.images or []:
            img.is_primary = False
        product.image_url = image_url

    new_img = ProductImage(
        product_id=product.id,
        image_url=image_url,
        display_order=resolved_order,
        is_primary=should_be_primary,
    )
    db.add(new_img)
    db.flush()

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="product.image_uploaded",
            entity_type="product_image",
            entity_id=new_img.id,
            details={
                "product_id": str(product.id),
                "image_url": image_url,
                "display_order": resolved_order,
                "is_primary": should_be_primary,
            },
            ip_address=ip_address,
        )
    db.flush()
    return ProductImageResponse.model_validate(new_img)


def update_product_image(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    payload: ProductImageUpdateRequest,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> ProductImageResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    target = next((img for img in (product.images or []) if img.id == image_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product image not found.",
        )

    if payload.display_order is not None and payload.display_order != target.display_order:
        conflict = next(
            (
                img
                for img in (product.images or [])
                if img.display_order == payload.display_order and img.id != target.id
            ),
            None,
        )
        if conflict:
            # Swap display orders safely via a temporary offset to satisfy unique constraint
            old_order = target.display_order
            conflict.display_order = 999999
            db.flush()
            target.display_order = payload.display_order
            db.flush()
            conflict.display_order = old_order
        else:
            target.display_order = payload.display_order

    if payload.is_primary is True:
        for img in product.images or []:
            img.is_primary = img.id == target.id
        product.image_url = target.image_url

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="product.image_updated",
            entity_type="product_image",
            entity_id=target.id,
            details={
                "product_id": str(product.id),
                "display_order": target.display_order,
                "is_primary": target.is_primary,
            },
            ip_address=ip_address,
        )
    db.flush()
    return ProductImageResponse.model_validate(target)


def replace_product_image(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    file: UploadFile,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> ProductImageResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    target = next((img for img in (product.images or []) if img.id == image_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product image not found.",
        )

    storage = get_image_storage()
    new_url = storage.save_image(file)
    old_url = target.image_url
    target.image_url = new_url
    if target.is_primary or product.image_url == old_url:
        product.image_url = new_url

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="product.image_replaced",
            entity_type="product_image",
            entity_id=target.id,
            details={"product_id": str(product.id), "image_url": new_url},
            ip_address=ip_address,
        )
    db.flush()
    storage.delete_image(old_url)
    return ProductImageResponse.model_validate(target)


def delete_product_image(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> None:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    target = next((img for img in (product.images or []) if img.id == image_id), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product image not found.",
        )

    old_url = target.image_url
    was_primary = target.is_primary or (product.image_url == old_url)
    db.delete(target)
    db.flush()

    db.refresh(product)
    if not product.images:
        if product.image_url == old_url:
            product.image_url = None
    elif was_primary:
        _sync_product_primary_image(product)

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="product.image_deleted",
            entity_type="product_image",
            entity_id=image_id,
            details={"product_id": str(product.id), "deleted_url": old_url},
            ip_address=ip_address,
        )
    db.flush()
    get_image_storage().delete_image(old_url)


# ---------------------------------------------------------------------------
# SALES & DISCOUNT MANAGEMENT (ADMIN)
# ---------------------------------------------------------------------------


def create_product_sale(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    payload: SaleCreateRequest,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> SaleAdminResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    orig_price = Decimal(str(product.original_price))

    if payload.discounted_price >= orig_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discounted price must be strictly less than the product's original price.",
        )

    if payload.is_active:
        existing_active = next((s for s in (product.sales or []) if s.is_active), None)
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product already has an active discount. Deactivate or edit the existing discount first.",
            )

    sale = Sale(
        product_id=product.id,
        original_price_snapshot=orig_price,
        discounted_price=payload.discounted_price,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        is_active=payload.is_active,
    )
    db.add(sale)
    product.is_on_sale = payload.is_active
    db.flush()

    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="discount.created",
            entity_type="sale",
            entity_id=sale.id,
            details={
                "product_id": str(product.id),
                "original_price_snapshot": str(orig_price),
                "discounted_price": str(sale.discounted_price),
                "is_active": sale.is_active,
            },
            ip_address=ip_address,
        )
    db.flush()
    return to_sale_admin_response(sale)


def update_product_sale(
    db: Session,
    admin: Optional[Admin],
    product_id: uuid.UUID,
    sale_id: uuid.UUID,
    payload: SaleUpdateRequest,
    ip_address: Optional[str] = None,
    required_seller_id: Optional[uuid.UUID] = None,
) -> SaleAdminResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=required_seller_id)
    sale = next((s for s in (product.sales or []) if s.id == sale_id), None)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount record not found for this product.",
        )

    orig_price = Decimal(str(product.original_price))
    new_discounted = (
        payload.discounted_price
        if payload.discounted_price is not None
        else Decimal(str(sale.discounted_price))
    )
    if new_discounted >= orig_price or new_discounted >= Decimal(str(sale.original_price_snapshot)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discounted price must be strictly less than the product's original price.",
        )

    new_starts = payload.starts_at if payload.starts_at is not None else sale.starts_at
    new_expires = payload.expires_at if payload.expires_at is not None else sale.expires_at
    if new_expires <= new_starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount expiry date must be after the start date.",
        )

    if payload.is_active is True and not sale.is_active:
        other_active = next(
            (s for s in (product.sales or []) if s.is_active and s.id != sale.id), None
        )
        if other_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another active discount already exists for this product.",
            )

    sale.discounted_price = new_discounted
    sale.starts_at = new_starts
    sale.expires_at = new_expires
    if payload.is_active is not None:
        sale.is_active = payload.is_active

    product.is_on_sale = any(s.is_active for s in (product.sales or []))
    if admin is not None:
        record_admin_audit(
            db=db,
            admin=admin,
            action="discount.updated",
            entity_type="sale",
            entity_id=sale.id,
            details={
                "product_id": str(product.id),
                "discounted_price": str(sale.discounted_price),
                "is_active": sale.is_active,
            },
            ip_address=ip_address,
        )
    db.flush()
    return to_sale_admin_response(sale)


# ---------------------------------------------------------------------------
# PUBLIC CUSTOMER-FACING CATALOG
# ---------------------------------------------------------------------------


def list_public_categories(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
) -> PaginatedCategoryPublicResponse:
    stmt: Select = select(Category).where(Category.is_active.is_(True))
    count_stmt: Select = select(func.count(Category.id)).where(Category.is_active.is_(True))

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = or_(Category.name.ilike(q), Category.description.ilike(q))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    rows = db.scalars(stmt.order_by(Category.name.asc()).offset(offset).limit(page_size)).all()
    counts = _category_product_counts(db, [c.id for c in rows], active_only=True)

    items = [
        CategoryPublicResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            image_url=c.image_url,
            product_count=counts.get(c.id, 0),
        )
        for c in rows
    ]
    return PaginatedCategoryPublicResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_public_category_by_slug(db: Session, slug: str) -> CategoryPublicResponse:
    category = db.scalar(
        select(Category).where(Category.slug == slug, Category.is_active.is_(True))
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    prod_count = (
        db.scalar(
            select(func.count(Product.id))
            .join(Category, Product.category_id == Category.id)
            .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
            .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
            .where(
                Product.category_id == category.id,
                *_public_visibility_sql_conditions(),
            )
        )
        or 0
    )
    return CategoryPublicResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        image_url=category.image_url,
        product_count=prod_count,
    )


def list_public_products(
    db: Session,
    page: int = 1,
    page_size: int = 12,
    search: Optional[str] = None,
    category: Optional[str] = None,  # kept alias safety
    category_slug: Optional[str] = None,
    category_id: Optional[uuid.UUID] = None,
    seller_slug: Optional[str] = None,
    seller_id: Optional[uuid.UUID] = None,
    owner_type: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    on_sale: Optional[bool] = None,
    sort_by: str = "newest",
) -> PaginatedProductPublicResponse:
    now = datetime.now(timezone.utc)
    live_sale_subq = (
        select(
            Sale.product_id.label("sale_pid"),
            func.min(Sale.discounted_price).label("live_discounted_price"),
        )
        .where(
            Sale.is_active.is_(True),
            Sale.starts_at <= now,
            Sale.expires_at > now,
        )
        .group_by(Sale.product_id)
        .subquery()
    )
    eff_price_expr = func.coalesce(live_sale_subq.c.live_discounted_price, Product.original_price)

    base_conds = _public_visibility_sql_conditions()

    resolved_cat_slug = category_slug or category
    if search and search.strip():
        q = f"%{search.strip()}%"
        base_conds.append(
            or_(
                Product.name.ilike(q),
                Product.short_description.ilike(q),
                Product.main_description.ilike(q),
            )
        )

    if resolved_cat_slug and resolved_cat_slug.strip():
        base_conds.append(Category.slug == resolved_cat_slug.strip().lower())

    if category_id is not None:
        base_conds.append(Product.category_id == category_id)

    if seller_slug and seller_slug.strip():
        base_conds.append(SellerProfile.store_slug == seller_slug.strip().lower())

    if seller_id is not None:
        base_conds.append(Product.seller_id == seller_id)

    if owner_type == "platform":
        base_conds.append(Product.seller_id.is_(None))
    elif owner_type == "seller":
        base_conds.append(Product.seller_id.is_not(None))

    if min_price is not None:
        base_conds.append(eff_price_expr >= min_price)

    if max_price is not None:
        base_conds.append(eff_price_expr <= max_price)

    if on_sale is True:
        base_conds.append(live_sale_subq.c.live_discounted_price.is_not(None))
    elif on_sale is False:
        base_conds.append(live_sale_subq.c.live_discounted_price.is_(None))

    count_stmt = (
        select(func.count(Product.id))
        .join(Category, Product.category_id == Category.id)
        .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
        .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
        .outerjoin(live_sale_subq, Product.id == live_sale_subq.c.sale_pid)
        .where(*base_conds)
    )
    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    stmt = (
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
        .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
        .outerjoin(live_sale_subq, Product.id == live_sale_subq.c.sale_pid)
        .options(
            selectinload(Product.category),
            selectinload(Product.seller).selectinload(SellerProfile.customer),
            selectinload(Product.images),
            selectinload(Product.sales),
        )
        .where(*base_conds)
    )

    if sort_by == "price_asc":
        stmt = stmt.order_by(asc(eff_price_expr), desc(Product.created_at))
    elif sort_by == "price_desc":
        stmt = stmt.order_by(desc(eff_price_expr), desc(Product.created_at))
    elif sort_by == "popularity":
        # Popularity ordered by verified paid order item quantity, falling back to newest
        paid_sales_subq = (
            select(
                OrderItem.product_id.label("pid"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("sold_qty"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.payment_status == OrderPaymentStatus.PAID)
            .group_by(OrderItem.product_id)
            .subquery()
        )
        stmt = stmt.outerjoin(
            paid_sales_subq, Product.id == paid_sales_subq.c.pid
        ).order_by(
            desc(func.coalesce(paid_sales_subq.c.sold_qty, 0)),
            desc(Product.created_at),
        )
    else:
        stmt = stmt.order_by(desc(Product.created_at))

    products = db.scalars(
        stmt.offset(offset).limit(page_size).execution_options(populate_existing=True)
    ).all()

    return PaginatedProductPublicResponse(
        items=[to_product_public_response(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_public_product_by_slug(db: Session, slug: str) -> ProductPublicResponse:
    product = db.scalar(
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
        .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
        .options(
            selectinload(Product.category),
            selectinload(Product.seller).selectinload(SellerProfile.customer),
            selectinload(Product.images),
            selectinload(Product.sales),
        )
        .where(
            Product.slug == slug,
            *_public_visibility_sql_conditions(),
        )
        .execution_options(populate_existing=True)
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return to_product_public_response(product)
