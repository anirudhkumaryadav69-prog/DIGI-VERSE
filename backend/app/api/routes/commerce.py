import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import get_current_customer
from app.core.rate_limit import get_client_ip, rate_limit_customer
from app.models.customer import Customer
from app.models.enums import DownloadStatus, OrderPaymentStatus, OrderStatus
from app.models.order import DownloadRecord, Order
from app.schemas.commerce import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartResponse,
    CheckoutRequest,
    CheckoutResponse,
    CustomerDownloadsOverviewResponse,
    DownloadGrantResponse,
    DownloadStatusResponse,
    OrderInvoiceResponse,
    OrderResponse,
    PaginatedOrderResponse,
    PaymentVerifyRequest,
    WishlistResponse,
)
from app.services.asset_storage_service import (
    FORBIDDEN_MIME_TYPES,
    AssetNotFoundError,
    AssetStorageError,
    build_download_content_disposition,
    get_asset_storage,
)
from app.services.commerce_service import (
    _validate_private_download_source,
    add_item_to_cart,
    add_product_to_wishlist,
    clear_customer_cart,
    clear_customer_wishlist,
    decode_signed_download_token,
    get_customer_cart,
    get_customer_downloads_overview,
    get_customer_order,
    get_customer_order_invoice,
    get_customer_wishlist,
    get_download_record_status,
    initialize_checkout,
    list_customer_orders,
    process_payment_webhook,
    remove_cart_item,
    remove_product_from_wishlist,
    request_digital_product_download,
    retry_order_payment,
    update_cart_item_quantity,
    verify_customer_payment,
)

router = APIRouter(tags=["Customer Wishlist, Cart, Checkout, Payments, Orders & Downloads"])


# ---------------------------------------------------------------------------
# WISHLIST ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/wishlist", response_model=WishlistResponse)
def get_wishlist(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> WishlistResponse:
    return get_customer_wishlist(db, customer)


@router.post(
    "/wishlist/{product_id}",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_wishlist_item(
    product_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> WishlistResponse:
    res = add_product_to_wishlist(db, customer, product_id)
    db.commit()
    return res


@router.delete("/wishlist/{product_id}", response_model=WishlistResponse)
def remove_wishlist_item(
    product_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> WishlistResponse:
    res = remove_product_from_wishlist(db, customer, product_id)
    db.commit()
    return res


@router.delete("/wishlist", response_model=WishlistResponse)
def clear_wishlist(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> WishlistResponse:
    res = clear_customer_wishlist(db, customer)
    db.commit()
    return res


# ---------------------------------------------------------------------------
# PERSISTENT SHOPPING CART ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/cart", response_model=CartResponse)
def get_cart(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CartResponse:
    res = get_customer_cart(db, customer)
    db.commit()
    return res


@router.post(
    "/cart/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_cart_item(
    payload: CartItemAddRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CartResponse:
    res = add_item_to_cart(db, customer, payload)
    db.commit()
    return res


@router.patch("/cart/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: uuid.UUID,
    payload: CartItemUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CartResponse:
    res = update_cart_item_quantity(db, customer, item_id, payload)
    db.commit()
    return res


@router.delete("/cart/items/{item_id}", response_model=CartResponse)
def delete_cart_item(
    item_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CartResponse:
    res = remove_cart_item(db, customer, item_id)
    db.commit()
    return res


@router.delete("/cart", response_model=CartResponse)
def clear_cart(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CartResponse:
    res = clear_customer_cart(db, customer)
    db.commit()
    return res


# ---------------------------------------------------------------------------
# CHECKOUT & PAYMENTS ENDPOINTS
# ---------------------------------------------------------------------------


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit_customer(
                "checkout_init",
                max_requests=30,
                window_seconds=60,
                ip_max_requests=45,
                ip_window_seconds=60,
            )
        )
    ],
)
def checkout(
    payload: Optional[CheckoutRequest] = Body(default=None),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    res = initialize_checkout(db, customer, payload)
    db.commit()
    return res


@router.post("/payments/verify", response_model=OrderResponse)
def verify_payment(
    payload: PaymentVerifyRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        res = verify_customer_payment(db, customer, payload)
        db.commit()
        return res
    except Exception:
        # Commit recorded failure reason if signature check failed before re-raising
        db.commit()
        raise


@router.post("/payments/webhook")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()
    signature = (
        request.headers.get("X-Razorpay-Signature")
        or request.headers.get("X-Webhook-Signature")
        or ""
    )
    event_id_header = (
        request.headers.get("X-Razorpay-Event-Id")
        or request.headers.get("X-Webhook-Event-Id")
    )
    try:
        parsed_body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook JSON body.",
        ) from exc

    res = process_payment_webhook(
        db=db,
        raw_body=raw_body,
        signature=signature,
        event_id_header=event_id_header,
        parsed_body=parsed_body,
    )
    db.commit()
    return res


# ---------------------------------------------------------------------------
# CUSTOMER ORDER ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=PaginatedOrderResponse)
def customer_list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    status: Optional[OrderStatus] = Query(default=None),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> PaginatedOrderResponse:
    return list_customer_orders(
        db=db,
        customer=customer,
        page=page,
        page_size=page_size,
        status_filter=status,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def customer_get_order(
    order_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderResponse:
    return get_customer_order(db=db, customer=customer, order_id=order_id)


@router.get("/orders/{order_id}/invoice", response_model=OrderInvoiceResponse)
def customer_get_invoice(
    order_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderInvoiceResponse:
    return get_customer_order_invoice(db=db, customer=customer, order_id=order_id)


@router.post("/orders/{order_id}/retry-payment", response_model=CheckoutResponse)
def customer_retry_order_payment(
    order_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    res = retry_order_payment(db=db, customer=customer, order_id=order_id)
    db.commit()
    return res



# ---------------------------------------------------------------------------
# DIGITAL PRODUCT DELIVERY ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/downloads", response_model=CustomerDownloadsOverviewResponse)
def customer_list_downloads(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerDownloadsOverviewResponse:
    return get_customer_downloads_overview(db=db, customer=customer)


@router.post(
    "/downloads/{order_item_id}",
    response_model=DownloadGrantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit_customer(
                "download_grant",
                max_requests=30,
                window_seconds=60,
                ip_max_requests=45,
                ip_window_seconds=60,
            )
        )
    ],
)
def customer_initiate_download(
    order_item_id: uuid.UUID,
    request: Request,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> DownloadGrantResponse:
    res = request_digital_product_download(
        db=db,
        customer=customer,
        order_item_id=order_item_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return res


@router.get("/downloads/{download_id}/status", response_model=DownloadStatusResponse)
def customer_check_download_status(
    download_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> DownloadStatusResponse:
    return get_download_record_status(db=db, customer=customer, download_id=download_id)


@router.get("/downloads/{download_id}/file")
def customer_stream_signed_download(
    download_id: uuid.UUID,
    token: str = Query(..., min_length=16),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> Response:
    """Authenticated, single-use, short-lived signed digital asset delivery stream.

    Verifies customer ownership, token signature/expiry, active download record status,
    verified paid order state, and valid product delivery source.
    Never exposes `private_download_url` in public JSON responses.
    """
    claims = decode_signed_download_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed download link is invalid or has expired.",
        )

    if claims.get("did") != str(download_id) or claims.get("sub") != str(customer.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed download token does not match this download or customer.",
        )

    record = db.scalar(
        select(DownloadRecord)
        .where(DownloadRecord.id == download_id)
        .with_for_update()
    )
    if not record or record.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download record not found.",
        )

    if record.order_item_id and claims.get("oiid") != str(record.order_item_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed download token does not match this order item.",
        )

    if record.status == DownloadStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download access has been revoked.",
        )

    if record.status == DownloadStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed download link has already been used.",
        )

    if record.status != DownloadStatus.GRANTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download grant is not active.",
        )

    order = db.get(Order, record.order_id)
    if (
        not order
        or order.payment_status != OrderPaymentStatus.PAID
        or order.status not in (OrderStatus.CONFIRMED, OrderStatus.FULFILLED)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Order is no longer eligible for download.",
        )

    product = record.product
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digital product is no longer available.",
        )
    _validate_private_download_source(product.private_download_url)
    if not product.asset_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digital asset file is not configured for this product.",
        )

    try:
        storage = get_asset_storage(product.asset_storage_backend)
        handle = storage.open(
            product.asset_storage_key,
            chunk_size=settings.ASSET_DOWNLOAD_CHUNK_BYTES,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digital asset file is no longer available in private storage.",
        ) from exc
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to stream digital asset from private storage.",
        ) from exc

    try:
        record.status = DownloadStatus.COMPLETED
        db.commit()
    except Exception:
        handle.close()
        raise

    raw_media_type = (product.asset_content_type or "").lower().split(";")[0].strip()
    media_type = (
        raw_media_type
        if raw_media_type and raw_media_type not in FORBIDDEN_MIME_TYPES
        else "application/octet-stream"
    )
    fallback_name = f"digiverse-asset-{record.id}"
    headers = {
        "Content-Disposition": build_download_content_disposition(
            product.asset_original_filename, fallback_name=fallback_name
        ),
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    content_len = handle.size_bytes if handle.size_bytes is not None else product.asset_size_bytes
    if content_len is not None:
        headers["Content-Length"] = str(content_len)

    return StreamingResponse(
        handle.iter_chunks(),
        media_type=media_type,
        headers=headers,
    )
