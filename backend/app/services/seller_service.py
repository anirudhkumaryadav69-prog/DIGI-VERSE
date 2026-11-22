"""Multi-vendor seller onboarding, ownership-isolated catalog, orders, storefronts, and admin governance."""
from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.admin import Admin
from app.models.catalog import Category, Product
from app.models.customer import Customer
from app.models.enums import (
    AccountStatus,
    DownloadStatus,
    OrderPaymentStatus,
    OrderStatus,
    ProductApprovalStatus,
    SellerApplicationStatus,
)
from app.models.order import DownloadRecord, Order, OrderItem
from app.models.seller import SellerProfile
from app.schemas.catalog import (
    PaginatedSellerProductResponse,
    ProductAdminResponse,
    SellerProductCreateRequest,
    SellerProductResponse,
    SellerProductUpdateRequest,
    slugify,
)
from app.schemas.seller import (
    AdminSellerSummaryResponse,
    PaginatedAdminSellerResponse,
    PaginatedSellerDirectoryResponse,
    PaginatedSellerOrderResponse,
    SellerAnalyticsResponse,
    SellerApplicationCreateRequest,
    SellerOrderItemResponse,
    SellerOrderResponse,
    SellerOverviewResponse,
    SellerProductPerformanceItem,
    SellerProfileResponse,
    SellerProfileUpdateRequest,
    SellerPublicProfileResponse,
    SellerPublicStorefrontResponse,
)
from app.services.asset_storage_service import AssetStorageError, get_asset_storage
from app.services.catalog_service import (
    _load_product_with_relations,
    _public_visibility_sql_conditions,
    get_admin_product,
    list_public_products,
    record_admin_audit,
    to_product_admin_response,
)
from app.services.storage_service import get_image_storage


def _quantize(val: Decimal | int | float) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_seller_profile_response(seller: SellerProfile) -> SellerProfileResponse:
    return SellerProfileResponse(
        id=seller.id,
        customer_id=seller.customer_id,
        store_name=seller.store_name,
        store_slug=seller.store_slug,
        seller_display_name=seller.seller_display_name,
        store_description=seller.store_description,
        application_description=seller.application_description,
        logo_url=seller.logo_url,
        banner_url=seller.banner_url,
        contact_email=seller.contact_email,
        contact_info=seller.contact_info,
        country=seller.country,
        business_type=seller.business_type,
        product_categories=list(seller.product_categories or []),
        application_status=seller.application_status,
        rejection_reason=seller.rejection_reason,
        suspension_reason=seller.suspension_reason,
        approved_at=seller.approved_at,
        rejected_at=seller.rejected_at,
        suspended_at=seller.suspended_at,
        created_at=seller.created_at,
        updated_at=seller.updated_at,
    )


def _to_seller_product_response(product: Product) -> SellerProductResponse:
    base: ProductAdminResponse = to_product_admin_response(product)
    data = base.model_dump()
    # Never expose raw legacy download URL or internal backend paths unnecessarily
    data["private_download_url"] = None
    return SellerProductResponse(**data)


# ===========================================================================
# 1. CUSTOMER SELLER APPLICATION & PROFILE MANAGEMENT
# ===========================================================================


def submit_seller_application(
    db: Session,
    customer: Customer,
    payload: SellerApplicationCreateRequest,
) -> SellerProfileResponse:
    existing = db.scalar(select(SellerProfile).where(SellerProfile.customer_id == customer.id))
    if existing:
        if existing.application_status == SellerApplicationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a seller application pending administrator review.",
            )
        if existing.application_status == SellerApplicationStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your seller account is already approved.",
            )
        if existing.application_status == SellerApplicationStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Suspended seller accounts cannot submit a new application. Contact marketplace support.",
            )

    try:
        resolved_slug = payload.store_slug or slugify(payload.store_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    slug_q = select(SellerProfile).where(SellerProfile.store_slug == resolved_slug)
    if existing:
        slug_q = slug_q.where(SellerProfile.id != existing.id)
    if db.scalar(slug_q):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A store with this storefront URL slug already exists. Choose a different slug.",
        )

    if existing and existing.application_status == SellerApplicationStatus.REJECTED:
        existing.store_name = payload.store_name.strip()
        existing.store_slug = resolved_slug
        existing.seller_display_name = payload.seller_display_name.strip()
        existing.store_description = payload.store_description
        existing.application_description = payload.application_description
        existing.logo_url = payload.logo_url
        existing.banner_url = payload.banner_url
        existing.contact_email = payload.contact_email
        existing.contact_info = payload.contact_info
        existing.country = payload.country.strip()
        existing.business_type = payload.business_type.strip()
        existing.product_categories = payload.product_categories
        existing.application_status = SellerApplicationStatus.PENDING
        existing.rejection_reason = None
        existing.rejected_at = None
        db.flush()
        db.refresh(existing)
        return _to_seller_profile_response(existing)

    profile = SellerProfile(
        customer_id=customer.id,
        store_name=payload.store_name.strip(),
        store_slug=resolved_slug,
        seller_display_name=payload.seller_display_name.strip(),
        store_description=payload.store_description,
        application_description=payload.application_description,
        logo_url=payload.logo_url,
        banner_url=payload.banner_url,
        contact_email=payload.contact_email,
        contact_info=payload.contact_info,
        country=payload.country.strip(),
        business_type=payload.business_type.strip(),
        product_categories=payload.product_categories,
        application_status=SellerApplicationStatus.PENDING,
    )
    db.add(profile)
    db.flush()
    db.refresh(profile)
    return _to_seller_profile_response(profile)


def get_my_seller_application(db: Session, customer: Customer) -> SellerProfileResponse:
    profile = db.scalar(select(SellerProfile).where(SellerProfile.customer_id == customer.id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No seller application found for this account.",
        )
    return _to_seller_profile_response(profile)


def update_seller_store_profile(
    db: Session,
    seller: SellerProfile,
    payload: SellerProfileUpdateRequest,
) -> SellerProfileResponse:
    if payload.store_name is not None:
        seller.store_name = payload.store_name.strip()
    if payload.seller_display_name is not None:
        seller.seller_display_name = payload.seller_display_name.strip()
    if payload.store_description is not None:
        seller.store_description = payload.store_description
    if payload.logo_url is not None:
        seller.logo_url = payload.logo_url or None
    if payload.banner_url is not None:
        seller.banner_url = payload.banner_url or None
    if payload.contact_email is not None:
        seller.contact_email = payload.contact_email
    if payload.contact_info is not None:
        seller.contact_info = payload.contact_info
    if payload.country is not None:
        seller.country = payload.country.strip()
    if payload.business_type is not None:
        seller.business_type = payload.business_type.strip()
    if payload.product_categories is not None:
        seller.product_categories = [
            c.strip()[:80] for c in payload.product_categories if (c or "").strip()
        ]
    db.flush()
    db.refresh(seller)
    return _to_seller_profile_response(seller)


def upload_seller_branding_image(file: UploadFile) -> str:
    return get_image_storage().save_image(file)


# ===========================================================================
# 2. SELLER PRODUCT MANAGEMENT (STRICT OWNERSHIP ISOLATION)
# ===========================================================================


def list_seller_products(
    db: Session,
    seller: SellerProfile,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category_id: Optional[uuid.UUID] = None,
    approval_status: Optional[ProductApprovalStatus] = None,
) -> PaginatedSellerProductResponse:
    stmt: Select = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.seller),
            selectinload(Product.images),
            selectinload(Product.sales),
        )
        .where(Product.seller_id == seller.id)
    )
    count_stmt: Select = select(func.count(Product.id)).where(Product.seller_id == seller.id)

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

    if approval_status is not None:
        stmt = stmt.where(Product.approval_status == approval_status)
        count_stmt = count_stmt.where(Product.approval_status == approval_status)

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    rows = db.scalars(
        stmt.order_by(Product.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .execution_options(populate_existing=True)
    ).all()

    return PaginatedSellerProductResponse(
        items=[_to_seller_product_response(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_seller_product(
    db: Session,
    seller: SellerProfile,
    product_id: uuid.UUID,
) -> SellerProductResponse:
    product = _load_product_with_relations(db, product_id, required_seller_id=seller.id)
    return _to_seller_product_response(product)


def create_seller_product(
    db: Session,
    seller: SellerProfile,
    payload: SellerProductCreateRequest,
) -> SellerProductResponse:
    category = db.get(Category, payload.category_id)
    if not category or not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected active category does not exist.",
        )

    try:
        resolved_slug = payload.slug or slugify(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if db.scalar(select(Product).where(Product.slug == resolved_slug)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists.",
        )

    now = datetime.now(timezone.utc)
    initial_status = (
        ProductApprovalStatus.PENDING_REVIEW
        if payload.submit_for_review
        else ProductApprovalStatus.DRAFT
    )
    product = Product(
        name=payload.name.strip(),
        slug=resolved_slug,
        category_id=payload.category_id,
        seller_id=seller.id,
        approval_status=initial_status,
        submitted_for_review_at=now if payload.submit_for_review else None,
        image_url=payload.image_url,
        short_description=payload.short_description,
        main_description=payload.main_description,
        detailed_description=payload.detailed_description,
        original_price=payload.original_price,
        product_type=payload.product_type,
        product_metadata=payload.metadata,
        is_on_sale=False,
        is_active=False,  # Requires administrator approval before first publication
    )
    db.add(product)
    db.flush()
    return get_seller_product(db, seller, product.id)


def update_seller_product(
    db: Session,
    seller: SellerProfile,
    product_id: uuid.UUID,
    payload: SellerProductUpdateRequest,
) -> SellerProductResponse:
    product = _load_product_with_relations(
        db, product_id, for_update=True, required_seller_id=seller.id
    )

    if payload.category_id is not None and payload.category_id != product.category_id:
        cat = db.get(Category, payload.category_id)
        if not cat or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected active category does not exist.",
            )
        product.category_id = payload.category_id

    if payload.name is not None:
        product.name = payload.name.strip()

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

    if payload.original_price is not None and payload.original_price != product.original_price:
        for s in product.sales or []:
            if s.is_active and Decimal(str(s.discounted_price)) >= payload.original_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New original price must be greater than the active discount price.",
                )
        product.original_price = payload.original_price

    if payload.image_url is not None:
        product.image_url = payload.image_url or None
    if payload.short_description is not None:
        product.short_description = payload.short_description
    if payload.main_description is not None:
        product.main_description = payload.main_description
    if payload.detailed_description is not None:
        product.detailed_description = payload.detailed_description
    if payload.product_type is not None:
        product.product_type = payload.product_type or None
    if payload.metadata is not None:
        product.product_metadata = payload.metadata

    if product.approval_status == ProductApprovalStatus.REJECTED:
        product.approval_status = ProductApprovalStatus.DRAFT

    db.flush()
    return get_seller_product(db, seller, product.id)


def change_seller_product_status(
    db: Session,
    seller: SellerProfile,
    product_id: uuid.UUID,
    action: str,
) -> SellerProductResponse:
    product = _load_product_with_relations(
        db, product_id, for_update=True, required_seller_id=seller.id
    )
    now = datetime.now(timezone.utc)

    if action == "save_draft":
        product.approval_status = ProductApprovalStatus.DRAFT
        product.is_active = False
    elif action == "submit_for_review":
        product.approval_status = ProductApprovalStatus.PENDING_REVIEW
        product.is_active = False
        product.submitted_for_review_at = now
        product.rejection_reason = None
    elif action == "publish":
        # First-time seller products or rejected products require explicit admin approval first.
        if (
            product.reviewed_by_admin_id is None
            or product.approval_status == ProductApprovalStatus.REJECTED
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product requires administrator approval before first publication. Submit it for review first.",
            )
        product.approval_status = ProductApprovalStatus.PUBLISHED
        product.is_active = True
    elif action == "unpublish":
        product.is_active = False
    elif action == "archive":
        product.approval_status = ProductApprovalStatus.ARCHIVED
        product.is_active = False
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status action.")

    db.flush()
    return get_seller_product(db, seller, product.id)


def delete_seller_product(
    db: Session,
    seller: SellerProfile,
    product_id: uuid.UUID,
) -> None:
    product = _load_product_with_relations(
        db, product_id, for_update=True, required_seller_id=seller.id
    )
    order_refs = (
        db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product.id)) or 0
    )
    download_refs = (
        db.scalar(select(func.count(DownloadRecord.id)).where(DownloadRecord.product_id == product.id))
        or 0
    )
    if order_refs > 0 or download_refs > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete product because historical orders or downloads reference it. "
                "Archive the product instead so existing customers retain access."
            ),
        )

    storage = get_image_storage()
    image_urls_to_clean = [img.image_url for img in (product.images or [])]
    if product.image_url:
        image_urls_to_clean.append(product.image_url)
    asset_key_to_clean = product.asset_storage_key
    asset_backend_to_clean = product.asset_storage_backend

    db.delete(product)
    db.flush()

    for url in image_urls_to_clean:
        storage.delete_image(url)
    if asset_key_to_clean:
        try:
            get_asset_storage(asset_backend_to_clean).delete(asset_key_to_clean)
        except AssetStorageError:
            pass


# ===========================================================================
# 3. SELLER ORDERS, OVERVIEW & GROSS PRODUCT SALES ANALYTICS
# ===========================================================================


def _item_download_count(order: Order, item: OrderItem) -> int:
    count = 0
    for d in order.downloads or []:
        if d.status in (DownloadStatus.GRANTED, DownloadStatus.COMPLETED) and (
            d.order_item_id == item.id
            or (d.order_item_id is None and d.product_id and d.product_id == item.product_id)
        ):
            count += 1
    return count


def _build_seller_order_response(order: Order, seller_id: uuid.UUID) -> SellerOrderResponse:
    seller_items = [item for item in (order.items or []) if item.seller_id == seller_id]
    subtotal = Decimal("0.00")
    units_count = 0
    total_dl_used = 0
    item_responses: list[SellerOrderItemResponse] = []

    for item in seller_items:
        line_total = _quantize(Decimal(str(item.purchase_price)) * item.quantity)
        subtotal = _quantize(subtotal + line_total)
        units_count += item.quantity
        max_dl = settings.MAX_DOWNLOADS_PER_ORDER_ITEM * max(1, item.quantity)
        used_dl = _item_download_count(order, item)
        total_dl_used += used_dl
        item_responses.append(
            SellerOrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                product_id=item.product_id,
                product_name_snapshot=item.product_name_snapshot,
                original_price_snapshot=_quantize(item.original_price_snapshot),
                purchase_price=_quantize(item.purchase_price),
                quantity=item.quantity,
                line_total=line_total,
                seller_store_name_snapshot=item.seller_store_name_snapshot,
                seller_store_slug_snapshot=item.seller_store_slug_snapshot,
                downloads_used=used_dl,
                max_downloads=max_dl,
            )
        )

    if order.status == OrderStatus.REFUNDED or order.payment_status == OrderPaymentStatus.REFUNDED:
        dl_status = "revoked"
    elif order.payment_status != OrderPaymentStatus.PAID:
        dl_status = "pending_payment"
    elif total_dl_used > 0:
        dl_status = "downloaded"
    else:
        dl_status = "ready"

    return SellerOrderResponse(
        order_id=order.id,
        order_number=order.order_number,
        created_at=order.created_at,
        paid_at=order.paid_at,
        fulfilled_at=order.fulfilled_at,
        status=order.status,
        payment_status=order.payment_status,
        currency=order.currency,
        seller_items_subtotal=subtotal,
        seller_units_count=units_count,
        download_fulfilment_status=dl_status,
        items=item_responses,
    )


def list_seller_orders(
    db: Session,
    seller: SellerProfile,
    page: int = 1,
    page_size: int = 20,
    order_status: Optional[OrderStatus] = None,
    payment_status: Optional[OrderPaymentStatus] = None,
    search: Optional[str] = None,
) -> PaginatedSellerOrderResponse:
    seller_order_ids_subq = (
        select(OrderItem.order_id).where(OrderItem.seller_id == seller.id).distinct()
    )
    stmt: Select = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.downloads))
        .where(Order.id.in_(seller_order_ids_subq))
    )
    count_stmt: Select = select(func.count(Order.id)).where(Order.id.in_(seller_order_ids_subq))

    if order_status is not None:
        stmt = stmt.where(Order.status == order_status)
        count_stmt = count_stmt.where(Order.status == order_status)

    if payment_status is not None:
        stmt = stmt.where(Order.payment_status == payment_status)
        count_stmt = count_stmt.where(Order.payment_status == payment_status)

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = Order.order_number.ilike(q)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    orders = db.scalars(
        stmt.order_by(Order.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .execution_options(populate_existing=True)
    ).all()

    return PaginatedSellerOrderResponse(
        items=[_build_seller_order_response(o, seller.id) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_seller_order(
    db: Session,
    seller: SellerProfile,
    order_id: uuid.UUID,
) -> SellerOrderResponse:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.downloads))
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )
    if not order or not any(item.seller_id == seller.id for item in (order.items or [])):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found for this seller.",
        )
    return _build_seller_order_response(order, seller.id)


def _compute_seller_metrics(db: Session, seller: SellerProfile) -> tuple[
    list[Product],
    list[Order],
    int,
    int,
    Decimal,
    int,
    list[SellerProductPerformanceItem],
    dict[str, dict[str, Any]],
]:
    products = db.scalars(
        select(Product).where(Product.seller_id == seller.id).order_by(Product.created_at.desc())
    ).all()
    product_map = {p.id: p for p in products}

    seller_order_ids_subq = (
        select(OrderItem.order_id).where(OrderItem.seller_id == seller.id).distinct()
    )
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.downloads))
        .where(Order.id.in_(seller_order_ids_subq))
        .order_by(Order.created_at.desc())
    ).all()

    paid_orders = 0
    total_units_sold = 0
    gross_sales = Decimal("0.00")
    total_downloads = 0
    per_product_units: dict[uuid.UUID, int] = defaultdict(int)
    per_product_sales: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0.00"))
    per_product_downloads: dict[uuid.UUID, int] = defaultdict(int)
    daily_buckets: dict[str, dict[str, Any]] = {}

    for o in orders:
        seller_items = [i for i in (o.items or []) if i.seller_id == seller.id]
        if not seller_items:
            continue
        is_paid = (
            o.payment_status == OrderPaymentStatus.PAID
            and o.status in (OrderStatus.CONFIRMED, OrderStatus.FULFILLED)
        )
        if is_paid:
            paid_orders += 1
        day_key = o.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        if day_key not in daily_buckets:
            daily_buckets[day_key] = {"date": day_key, "units": 0, "gross_sales": Decimal("0.00")}

        for item in seller_items:
            dl_cnt = _item_download_count(o, item)
            total_downloads += dl_cnt
            if item.product_id:
                per_product_downloads[item.product_id] += dl_cnt
            if is_paid:
                line_tot = _quantize(Decimal(str(item.purchase_price)) * item.quantity)
                total_units_sold += item.quantity
                gross_sales = _quantize(gross_sales + line_tot)
                daily_buckets[day_key]["units"] += item.quantity
                daily_buckets[day_key]["gross_sales"] = _quantize(
                    daily_buckets[day_key]["gross_sales"] + line_tot
                )
                if item.product_id:
                    per_product_units[item.product_id] += item.quantity
                    per_product_sales[item.product_id] = _quantize(
                        per_product_sales[item.product_id] + line_tot
                    )

    breakdown: list[SellerProductPerformanceItem] = []
    for p in products:
        breakdown.append(
            SellerProductPerformanceItem(
                product_id=p.id,
                name=p.name,
                slug=p.slug,
                approval_status=p.approval_status,
                is_active=p.is_active,
                units_sold=per_product_units.get(p.id, 0),
                gross_sales=_quantize(per_product_sales.get(p.id, Decimal("0.00"))),
                downloads_count=per_product_downloads.get(p.id, 0),
            )
        )
    breakdown.sort(key=lambda x: (x.gross_sales, x.units_sold), reverse=True)
    return (
        products,
        orders,
        paid_orders,
        total_units_sold,
        gross_sales,
        total_downloads,
        breakdown,
        daily_buckets,
    )


def get_seller_overview(db: Session, seller: SellerProfile) -> SellerOverviewResponse:
    (
        products,
        orders,
        paid_orders,
        total_units_sold,
        gross_sales,
        _,
        breakdown,
        _,
    ) = _compute_seller_metrics(db, seller)

    return SellerOverviewResponse(
        store_name=seller.store_name,
        store_slug=seller.store_slug,
        application_status=seller.application_status,
        total_products=len(products),
        published_products=sum(
            1
            for p in products
            if p.approval_status == ProductApprovalStatus.PUBLISHED and p.is_active
        ),
        draft_products=sum(
            1 for p in products if p.approval_status == ProductApprovalStatus.DRAFT
        ),
        pending_review_products=sum(
            1 for p in products if p.approval_status == ProductApprovalStatus.PENDING_REVIEW
        ),
        rejected_products=sum(
            1 for p in products if p.approval_status == ProductApprovalStatus.REJECTED
        ),
        archived_products=sum(
            1 for p in products if p.approval_status == ProductApprovalStatus.ARCHIVED
        ),
        total_orders=len(orders),
        paid_orders=paid_orders,
        total_units_sold=total_units_sold,
        gross_product_sales=gross_sales,
        currency=settings.STORE_CURRENCY,
        recent_orders=[_build_seller_order_response(o, seller.id) for o in orders[:5]],
        top_products=breakdown[:5],
    )


def get_seller_analytics(db: Session, seller: SellerProfile) -> SellerAnalyticsResponse:
    (
        _,
        orders,
        _,
        total_units_sold,
        gross_sales,
        total_downloads,
        breakdown,
        daily_buckets,
    ) = _compute_seller_metrics(db, seller)
    daily_list = [
        {"date": k, "units": v["units"], "gross_sales": str(v["gross_sales"])}
        for k, v in sorted(daily_buckets.items())
    ]
    return SellerAnalyticsResponse(
        currency=settings.STORE_CURRENCY,
        total_orders=len(orders),
        total_units_sold=total_units_sold,
        gross_product_sales=gross_sales,
        total_downloads=total_downloads,
        product_breakdown=breakdown,
        daily_sales=daily_list,
    )


# ===========================================================================
# 4. PUBLIC SELLER STOREFRONTS
# ===========================================================================


def _seller_published_counts(db: Session, seller_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not seller_ids:
        return {}
    rows = db.execute(
        select(Product.seller_id, func.count(Product.id))
        .join(Category, Product.category_id == Category.id)
        .where(
            Product.seller_id.in_(seller_ids),
            Product.is_active.is_(True),
            Product.approval_status == ProductApprovalStatus.PUBLISHED,
            Category.is_active.is_(True),
        )
        .group_by(Product.seller_id)
    ).all()
    return {sid: cnt for sid, cnt in rows if sid is not None}


def list_public_sellers(
    db: Session,
    page: int = 1,
    page_size: int = 24,
    search: Optional[str] = None,
) -> PaginatedSellerDirectoryResponse:
    base_conds = [
        SellerProfile.application_status == SellerApplicationStatus.APPROVED,
        Customer.account_status == AccountStatus.ACTIVE,
    ]
    stmt: Select = (
        select(SellerProfile)
        .join(Customer, SellerProfile.customer_id == Customer.id)
        .where(*base_conds)
    )
    count_stmt: Select = (
        select(func.count(SellerProfile.id))
        .join(Customer, SellerProfile.customer_id == Customer.id)
        .where(*base_conds)
    )

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = or_(
            SellerProfile.store_name.ilike(q),
            SellerProfile.seller_display_name.ilike(q),
            SellerProfile.store_description.ilike(q),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    sellers = db.scalars(
        stmt.order_by(SellerProfile.store_name.asc()).offset(offset).limit(page_size)
    ).all()
    counts = _seller_published_counts(db, [s.id for s in sellers])

    items = [
        SellerPublicProfileResponse(
            id=s.id,
            store_name=s.store_name,
            store_slug=s.store_slug,
            seller_display_name=s.seller_display_name,
            store_description=s.store_description,
            logo_url=s.logo_url,
            banner_url=s.banner_url,
            country=s.country,
            business_type=s.business_type,
            product_categories=list(s.product_categories or []),
            published_product_count=counts.get(s.id, 0),
            created_at=s.created_at,
        )
        for s in sellers
    ]
    return PaginatedSellerDirectoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_public_seller_storefront(
    db: Session,
    store_slug: str,
    page: int = 1,
    page_size: int = 12,
    search: Optional[str] = None,
    category_slug: Optional[str] = None,
    sort_by: str = "newest",
) -> SellerPublicStorefrontResponse:
    seller = db.scalar(
        select(SellerProfile)
        .join(Customer, SellerProfile.customer_id == Customer.id)
        .where(
            SellerProfile.store_slug == store_slug.strip().lower(),
            SellerProfile.application_status == SellerApplicationStatus.APPROVED,
            Customer.account_status == AccountStatus.ACTIVE,
        )
    )
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storefront not found or currently unavailable.",
        )

    cat_rows = db.execute(
        select(Category.id, Category.name, Category.slug, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .outerjoin(SellerProfile, Product.seller_id == SellerProfile.id)
        .outerjoin(Customer, SellerProfile.customer_id == Customer.id)
        .where(
            Product.seller_id == seller.id,
            *_public_visibility_sql_conditions(),
        )
        .group_by(Category.id, Category.name, Category.slug)
        .order_by(Category.name.asc())
    ).all()

    total_pub = sum(cnt for _, _, _, cnt in cat_rows)
    categories = [
        {"id": str(cid), "name": cname, "slug": cslug, "product_count": cnt}
        for cid, cname, cslug, cnt in cat_rows
    ]

    products_page = list_public_products(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category_slug,
        seller_id=seller.id,
        sort_by=sort_by,
    )

    return SellerPublicStorefrontResponse(
        seller=SellerPublicProfileResponse(
            id=seller.id,
            store_name=seller.store_name,
            store_slug=seller.store_slug,
            seller_display_name=seller.seller_display_name,
            store_description=seller.store_description,
            logo_url=seller.logo_url,
            banner_url=seller.banner_url,
            country=seller.country,
            business_type=seller.business_type,
            product_categories=list(seller.product_categories or []),
            published_product_count=total_pub,
            created_at=seller.created_at,
        ),
        categories=categories,
        products=products_page,
    )


# ===========================================================================
# 5. ADMINISTRATOR SELLER GOVERNANCE & MODERATION
# ===========================================================================


def _to_admin_seller_summary(
    seller: SellerProfile,
    total_cnt: int,
    pub_cnt: int,
) -> AdminSellerSummaryResponse:
    base = _to_seller_profile_response(seller).model_dump()
    return AdminSellerSummaryResponse(
        **base,
        customer_email=seller.customer.email if seller.customer else None,
        customer_name=seller.customer.full_name if seller.customer else None,
        product_count=total_cnt,
        published_product_count=pub_cnt,
    )


def list_admin_sellers(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[SellerApplicationStatus] = None,
) -> PaginatedAdminSellerResponse:
    stmt: Select = (
        select(SellerProfile)
        .join(Customer, SellerProfile.customer_id == Customer.id)
        .options(selectinload(SellerProfile.customer))
    )
    count_stmt: Select = select(func.count(SellerProfile.id)).join(
        Customer, SellerProfile.customer_id == Customer.id
    )

    if status_filter is not None:
        stmt = stmt.where(SellerProfile.application_status == status_filter)
        count_stmt = count_stmt.where(SellerProfile.application_status == status_filter)

    if search and search.strip():
        q = f"%{search.strip()}%"
        cond = or_(
            SellerProfile.store_name.ilike(q),
            SellerProfile.store_slug.ilike(q),
            SellerProfile.seller_display_name.ilike(q),
            SellerProfile.contact_email.ilike(q),
            Customer.email.ilike(q),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    rows = db.scalars(
        stmt.order_by(SellerProfile.created_at.desc()).offset(offset).limit(page_size)
    ).all()
    sids = [r.id for r in rows]

    total_counts: dict[uuid.UUID, int] = {}
    pub_counts: dict[uuid.UUID, int] = {}
    if sids:
        for sid, cnt in db.execute(
            select(Product.seller_id, func.count(Product.id))
            .where(Product.seller_id.in_(sids))
            .group_by(Product.seller_id)
        ).all():
            if sid:
                total_counts[sid] = cnt
        pub_counts = _seller_published_counts(db, sids)

    return PaginatedAdminSellerResponse(
        items=[
            _to_admin_seller_summary(r, total_counts.get(r.id, 0), pub_counts.get(r.id, 0))
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_admin_seller(db: Session, seller_id: uuid.UUID) -> AdminSellerSummaryResponse:
    seller = db.scalar(
        select(SellerProfile)
        .options(selectinload(SellerProfile.customer))
        .where(SellerProfile.id == seller_id)
    )
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller profile not found.")
    total_cnt = (
        db.scalar(select(func.count(Product.id)).where(Product.seller_id == seller.id)) or 0
    )
    pub_cnt = _seller_published_counts(db, [seller.id]).get(seller.id, 0)
    return _to_admin_seller_summary(seller, total_cnt, pub_cnt)


def review_admin_seller(
    db: Session,
    admin: Admin,
    seller_id: uuid.UUID,
    action: str,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AdminSellerSummaryResponse:
    seller = db.scalar(
        select(SellerProfile)
        .options(selectinload(SellerProfile.customer))
        .where(SellerProfile.id == seller_id)
        .with_for_update()
    )
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller profile not found.")

    now = datetime.now(timezone.utc)
    cleaned_reason = (reason or "").strip() or None
    prev_status = seller.application_status

    if action == "approve":
        seller.application_status = SellerApplicationStatus.APPROVED
        seller.approved_at = now
        seller.approved_by_admin_id = admin.id
        seller.rejection_reason = None
        seller.suspension_reason = None
        audit_action = "seller.approved"
    elif action == "reject":
        if not cleaned_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A rejection reason is required when rejecting a seller application.",
            )
        seller.application_status = SellerApplicationStatus.REJECTED
        seller.rejection_reason = cleaned_reason
        seller.rejected_at = now
        audit_action = "seller.rejected"
    elif action == "suspend":
        if not cleaned_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A suspension reason is required when suspending a seller account.",
            )
        seller.application_status = SellerApplicationStatus.SUSPENDED
        seller.suspension_reason = cleaned_reason
        seller.suspended_at = now
        audit_action = "seller.suspended"
    elif action == "reinstate":
        if seller.application_status != SellerApplicationStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only suspended seller accounts can be reinstated.",
            )
        seller.application_status = SellerApplicationStatus.APPROVED
        seller.suspension_reason = None
        seller.approved_at = now
        seller.approved_by_admin_id = admin.id
        audit_action = "seller.reinstated"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported seller action.")

    record_admin_audit(
        db=db,
        admin=admin,
        action=audit_action,
        entity_type="seller_profile",
        entity_id=seller.id,
        details={
            "store_slug": seller.store_slug,
            "customer_id": str(seller.customer_id),
            "previous_status": prev_status.value,
            "new_status": seller.application_status.value,
            "reason": cleaned_reason,
        },
        ip_address=ip_address,
    )
    db.flush()
    return get_admin_seller(db, seller.id)
