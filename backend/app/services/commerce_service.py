import logging
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.logging import log_payment_event, log_security_event
from app.core.security import JWT_ISSUER
from app.models.admin import Admin
from app.models.catalog import Category, Product
from app.models.customer import Customer, CustomerActivity
from app.models.enums import (
    ActivityType,
    DownloadStatus,
    OrderPaymentStatus,
    OrderStatus,
    PaymentStatus,
)
from app.models.order import DownloadRecord, Order, OrderItem, Payment, PaymentWebhookEvent
from app.models.seller import SellerProfile
from app.models.shopping import Cart, CartItem, Wishlist
from app.schemas.commerce import (
    AdminOrderCustomerInfo,
    AdminOrderResponse,
    AdminOrderStatisticsResponse,
    CartItemAddRequest,
    CartItemResponse,
    CartItemUpdateRequest,
    CartResponse,
    CheckoutRequest,
    CheckoutResponse,
    CustomerDownloadableItemResponse,
    CustomerDownloadsOverviewResponse,
    DownloadGrantResponse,
    DownloadRecordSummary,
    DownloadStatusResponse,
    OrderInvoiceResponse,
    OrderItemResponse,
    OrderResponse,
    PaginatedAdminOrderResponse,
    PaginatedOrderResponse,
    PaymentInitPayload,
    PaymentSummaryResponse,
    PaymentVerifyRequest,
    WishlistItemResponse,
    WishlistResponse,
)
from app.services.catalog_service import (
    _resolve_primary_image_url,
    compute_product_pricing,
    record_admin_audit,
)
from app.services.asset_storage_service import AssetStorageError, get_asset_storage
from app.services.email_service import safe_send_commerce_notification
from app.services.payment_gateway import get_payment_provider
from app.services.financial_service import (
    post_payment_capture,
    post_refund_reversal,
    quantize_money,
    snapshot_order_commissions,
)

DOWNLOAD_TOKEN_AUDIENCE = "digiverse:download"

# Centralized valid order state transitions
ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {
        OrderStatus.CONFIRMED,
        OrderStatus.FULFILLED,
        OrderStatus.FAILED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.FULFILLED,
        OrderStatus.REFUNDED,
    },
    OrderStatus.FULFILLED: {
        OrderStatus.REFUNDED,
    },
    OrderStatus.FAILED: {
        OrderStatus.CONFIRMED,
        OrderStatus.FULFILLED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}

# Centralized valid payment state transitions
ALLOWED_PAYMENT_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.CREATED: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.FAILED: {
        PaymentStatus.CAPTURED,
    },
    PaymentStatus.CAPTURED: {
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.REFUNDED: set(),
}


def _quantize(val: Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _load_active_product_or_400(db: Session, product_id: uuid.UUID) -> Product:
    from app.services.catalog_service import is_product_publicly_visible

    product = db.scalar(
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
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    if not is_product_publicly_visible(product):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.name}' is currently inactive or unavailable.",
        )
    return product


# ===========================================================================
# 1. WISHLIST SERVICE
# ===========================================================================


def get_customer_wishlist(db: Session, customer: Customer) -> WishlistResponse:
    rows = db.scalars(
        select(Wishlist)
        .options(
            selectinload(Wishlist.product).selectinload(Product.category),
            selectinload(Wishlist.product).selectinload(Product.images),
            selectinload(Wishlist.product).selectinload(Product.sales),
        )
        .where(Wishlist.customer_id == customer.id)
        .order_by(Wishlist.created_at.desc())
        .execution_options(populate_existing=True)
    ).all()

    now = datetime.now(timezone.utc)
    items: list[WishlistItemResponse] = []
    for w in rows:
        p = w.product
        if not p:
            continue
        eff_price, is_live_sale, active_disc = compute_product_pricing(p, now)
        available = bool(p.is_active and p.category and p.category.is_active)
        items.append(
            WishlistItemResponse(
                id=w.id,
                product_id=p.id,
                product_name=p.name,
                product_slug=p.slug,
                category_name=p.category.name if p.category else "Uncategorized",
                image_url=_resolve_primary_image_url(p),
                original_price=_quantize(p.original_price),
                effective_price=_quantize(eff_price),
                is_on_sale=is_live_sale,
                active_discount=active_disc,
                is_available=available,
                created_at=w.created_at,
            )
        )
    return WishlistResponse(items=items, total_items=len(items))


def add_product_to_wishlist(
    db: Session, customer: Customer, product_id: uuid.UUID
) -> WishlistResponse:
    product = _load_active_product_or_400(db, product_id)

    existing = db.scalar(
        select(Wishlist).where(
            Wishlist.customer_id == customer.id,
            Wishlist.product_id == product.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is already in your wishlist.",
        )

    entry = Wishlist(customer_id=customer.id, product_id=product.id)
    db.add(entry)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.WISHLIST_ADD,
            product_id=product.id,
            category_id=product.category_id,
        )
    )
    db.flush()
    return get_customer_wishlist(db, customer)


def remove_product_from_wishlist(
    db: Session, customer: Customer, product_id: uuid.UUID
) -> WishlistResponse:
    entry = db.scalar(
        select(Wishlist).where(
            Wishlist.customer_id == customer.id,
            Wishlist.product_id == product_id,
        )
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product was not found in your wishlist.",
        )
    db.delete(entry)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.WISHLIST_REMOVE,
            product_id=product_id,
        )
    )
    db.flush()
    return get_customer_wishlist(db, customer)


def clear_customer_wishlist(db: Session, customer: Customer) -> WishlistResponse:
    db.execute(delete(Wishlist).where(Wishlist.customer_id == customer.id))
    db.flush()
    return WishlistResponse(items=[], total_items=0)


# ===========================================================================
# 2. PERSISTENT SHOPPING CART SERVICE
# ===========================================================================


def _get_or_create_cart_entity(
    db: Session, customer_id: uuid.UUID, for_update: bool = False
) -> Cart:
    stmt = (
        select(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.category),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.seller)
            .selectinload(SellerProfile.customer),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.images),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.sales),
        )
        .where(Cart.customer_id == customer_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        stmt = stmt.with_for_update()
    cart = db.scalar(stmt)
    if not cart:
        try:
            with db.begin_nested():
                cart = Cart(customer_id=customer_id)
                db.add(cart)
                db.flush()
        except IntegrityError:
            # Concurrent cart initialization for the same customer: load existing row
            pass
        cart = db.scalar(stmt)
        if cart:
            db.refresh(cart)
    return cart


def _build_cart_response(cart: Cart) -> CartResponse:
    now = datetime.now(timezone.utc)
    item_responses: list[CartItemResponse] = []
    subtotal = Decimal("0.00")
    total_discount = Decimal("0.00")
    final_payable = Decimal("0.00")
    total_qty = 0

    sorted_items = sorted(cart.items or [], key=lambda i: i.created_at)
    for ci in sorted_items:
        p = ci.product
        if not p:
            continue
        unit_price = _quantize(p.original_price)
        eff_unit_price, _, active_disc = compute_product_pricing(p, now)
        eff_unit_price = _quantize(eff_unit_price)
        qty = ci.quantity

        from app.services.catalog_service import is_product_publicly_visible

        line_sub = _quantize(unit_price * qty)
        line_tot = _quantize(eff_unit_price * qty)
        line_disc = _quantize(line_sub - line_tot)
        available = is_product_publicly_visible(p)

        subtotal = _quantize(subtotal + line_sub)
        total_discount = _quantize(total_discount + line_disc)
        final_payable = _quantize(final_payable + line_tot)
        total_qty += qty

        item_responses.append(
            CartItemResponse(
                id=ci.id,
                product_id=p.id,
                product_name=p.name,
                product_slug=p.slug,
                category_name=p.category.name if p.category else "Uncategorized",
                thumbnail_url=_resolve_primary_image_url(p),
                unit_price=unit_price,
                active_discount=active_disc,
                effective_unit_price=eff_unit_price,
                quantity=qty,
                line_subtotal=line_sub,
                line_discount=line_disc,
                line_total=line_tot,
                is_available=available,
            )
        )

    return CartResponse(
        cart_id=cart.id,
        customer_id=cart.customer_id,
        currency=settings.STORE_CURRENCY,
        items=item_responses,
        total_quantity=total_qty,
        subtotal=subtotal,
        total_discount=total_discount,
        final_payable_amount=final_payable,
        updated_at=cart.updated_at,
    )


def get_customer_cart(db: Session, customer: Customer) -> CartResponse:
    cart = _get_or_create_cart_entity(db, customer.id)
    return _build_cart_response(cart)


def add_item_to_cart(
    db: Session, customer: Customer, payload: CartItemAddRequest
) -> CartResponse:
    product = _load_active_product_or_400(db, payload.product_id)
    cart = _get_or_create_cart_entity(db, customer.id)

    existing_line = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product.id,
        )
    )
    if existing_line:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is already in your shopping cart. Update the item quantity instead.",
        )

    item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=payload.quantity,
    )
    db.add(item)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.CART_ADD,
            product_id=product.id,
            category_id=product.category_id,
            details={"quantity": payload.quantity},
        )
    )
    db.flush()
    cart = _get_or_create_cart_entity(db, customer.id)
    return _build_cart_response(cart)


def update_cart_item_quantity(
    db: Session,
    customer: Customer,
    item_id: uuid.UUID,
    payload: CartItemUpdateRequest,
) -> CartResponse:
    cart = _get_or_create_cart_entity(db, customer.id)
    item = db.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    _load_active_product_or_400(db, item.product_id)
    item.quantity = payload.quantity
    db.flush()
    cart = _get_or_create_cart_entity(db, customer.id)
    return _build_cart_response(cart)


def remove_cart_item(
    db: Session,
    customer: Customer,
    item_id: uuid.UUID,
) -> CartResponse:
    cart = _get_or_create_cart_entity(db, customer.id)
    item = db.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    pid = item.product_id
    db.delete(item)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.CART_REMOVE,
            product_id=pid,
        )
    )
    db.flush()
    cart = _get_or_create_cart_entity(db, customer.id)
    return _build_cart_response(cart)


def clear_customer_cart(db: Session, customer: Customer) -> CartResponse:
    cart = _get_or_create_cart_entity(db, customer.id)
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    db.flush()
    cart = _get_or_create_cart_entity(db, customer.id)
    return _build_cart_response(cart)


# ===========================================================================
# 3. CHECKOUT SYSTEM
# ===========================================================================


def _generate_order_number() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_part = uuid.uuid4().hex[:8].upper()
    return f"DV-{date_part}-{rand_part}"


def _resolve_public_key_id(provider: Any) -> str:
    if provider.gateway_name == "razorpay":
        key_id = (settings.RAZORPAY_KEY_ID or "").strip()
        if not key_id or key_id == "your_razorpay_key_id_placeholder":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Razorpay public key (RAZORPAY_KEY_ID) is not configured.",
            )
        return key_id
    return "rzp_test_mock_public_key"


def initialize_checkout(
    db: Session,
    customer: Customer,
    payload: Optional[CheckoutRequest] = None,
) -> CheckoutResponse:
    idem_key = (payload.idempotency_key.strip() if payload and payload.idempotency_key else None)

    # Lock the customer's Cart row first so simultaneous checkout requests serialize cleanly
    cart = _get_or_create_cart_entity(db, customer.id, for_update=True)

    # 1. Check idempotency key if supplied
    if idem_key:
        existing_order = db.scalar(
            select(Order)
            .options(selectinload(Order.payments))
            .where(
                Order.customer_id == customer.id,
                Order.idempotency_key == idem_key,
            )
        )
        if existing_order:
            if (
                existing_order.payment_status == OrderPaymentStatus.PAID
                or existing_order.status in (OrderStatus.FULFILLED, OrderStatus.REFUNDED, OrderStatus.CANCELLED)
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Checkout for this idempotency key has already been finalized.",
                )
            provider = get_payment_provider()
            active_payment = next(
                (
                    p
                    for p in existing_order.payments
                    if p.status == PaymentStatus.CREATED and p.gateway_name == provider.gateway_name
                ),
                None,
            )
            if not active_payment:
                return retry_order_payment(db=db, customer=customer, order_id=existing_order.id)
            pub_key = _resolve_public_key_id(provider)
            return CheckoutResponse(
                order_id=existing_order.id,
                order_number=existing_order.order_number,
                status=existing_order.status,
                payment_status=existing_order.payment_status,
                subtotal_amount=_quantize(existing_order.subtotal_amount),
                discount_amount=_quantize(existing_order.discount_amount),
                total_amount=_quantize(existing_order.total_amount),
                currency=existing_order.currency,
                payment=PaymentInitPayload(
                    payment_id=active_payment.id,
                    gateway_name=active_payment.gateway_name,
                    gateway_order_id=active_payment.gateway_order_id,
                    public_key_id=pub_key,
                    amount=_quantize(active_payment.amount),
                    amount_subunits=int((Decimal(str(active_payment.amount)) * 100).to_integral_value()),
                    currency=active_payment.currency,
                ),
                created_at=existing_order.created_at,
            )

    # 2. Validate all products & categories in the locked cart
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your shopping cart is empty.",
        )

    now = datetime.now(timezone.utc)
    subtotal = Decimal("0.00")
    total_discount = Decimal("0.00")
    final_total = Decimal("0.00")
    line_snapshots: list[dict[str, Any]] = []

    from app.services.catalog_service import is_product_publicly_visible

    for ci in sorted(cart.items, key=lambda i: i.created_at):
        p = ci.product
        if not p or not is_product_publicly_visible(p):
            p_label = p.name if p else str(ci.product_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{p_label}' in your cart is no longer available.",
            )

        orig_unit = _quantize(p.original_price)
        eff_unit, _, _ = compute_product_pricing(p, now)
        eff_unit = _quantize(eff_unit)
        qty = ci.quantity

        line_sub = _quantize(orig_unit * qty)
        line_tot = _quantize(eff_unit * qty)
        line_disc = _quantize(line_sub - line_tot)

        subtotal = _quantize(subtotal + line_sub)
        total_discount = _quantize(total_discount + line_disc)
        final_total = _quantize(final_total + line_tot)

        line_snapshots.append(
            {
                "product_id": p.id,
                "seller_id": p.seller_id,
                "seller_store_name_snapshot": p.seller.store_name if p.seller else "DIGI-VERSE Official",
                "seller_store_slug_snapshot": p.seller.store_slug if p.seller else None,
                "product_name_snapshot": p.name,
                "original_price_snapshot": orig_unit,
                "purchase_price": eff_unit,
                "quantity": qty,
            }
        )

    if final_total <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order total must be greater than zero for payment processing.",
        )

    # 3. Create pending order & immutable order item snapshots
    order_number = _generate_order_number()
    currency = settings.STORE_CURRENCY
    order = Order(
        customer_id=customer.id,
        order_number=order_number,
        subtotal_amount=subtotal,
        discount_amount=total_discount,
        total_amount=final_total,
        currency=currency,
        status=OrderStatus.PENDING,
        payment_status=OrderPaymentStatus.PENDING,
        idempotency_key=idem_key,
    )
    db.add(order)
    db.flush()

    for snap in line_snapshots:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=snap["product_id"],
                seller_id=snap["seller_id"],
                seller_store_name_snapshot=snap["seller_store_name_snapshot"],
                seller_store_slug_snapshot=snap["seller_store_slug_snapshot"],
                product_name_snapshot=snap["product_name_snapshot"],
                original_price_snapshot=snap["original_price_snapshot"],
                purchase_price=snap["purchase_price"],
                quantity=snap["quantity"],
            )
        )
    db.flush()
    snapshot_order_commissions(db, order)

    # 4. Initialize payment with configured provider
    provider = get_payment_provider()
    gateway_init = provider.create_order(
        order_number=order.order_number,
        amount=final_total,
        currency=currency,
        notes={"order_id": str(order.id), "customer_id": str(customer.id)},
    )

    payment = Payment(
        order_id=order.id,
        customer_id=customer.id,
        gateway_name=gateway_init.gateway_name,
        gateway_order_id=gateway_init.gateway_order_id,
        amount=final_total,
        currency=currency,
        status=PaymentStatus.CREATED,
        is_signature_verified=False,
        provider_metadata=gateway_init.metadata,
    )
    db.add(payment)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.CHECKOUT_START,
            details={"order_id": str(order.id), "order_number": order.order_number},
        )
    )
    db.flush()

    safe_send_commerce_notification(
        email=customer.email,
        template_name="order_confirmation",
        order_number=order.order_number,
        customer_name=customer.full_name,
        total_amount=order.total_amount,
        currency=order.currency,
    )

    return CheckoutResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        subtotal_amount=subtotal,
        discount_amount=total_discount,
        total_amount=final_total,
        currency=currency,
        payment=PaymentInitPayload(
            payment_id=payment.id,
            gateway_name=payment.gateway_name,
            gateway_order_id=payment.gateway_order_id,
            public_key_id=gateway_init.public_key_id,
            amount=final_total,
            amount_subunits=gateway_init.amount_subunits,
            currency=currency,
        ),
        created_at=order.created_at,
    )


def retry_order_payment(
    db: Session,
    customer: Customer,
    order_id: uuid.UUID,
) -> CheckoutResponse:
    """Re-initialize payment for an existing pending or failed order without creating a duplicate order."""
    order = _load_order_full(db, order_id, for_update=True)
    if order.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to retry payment for this order.",
        )

    if order.payment_status == OrderPaymentStatus.PAID or order.status in (
        OrderStatus.FULFILLED,
        OrderStatus.REFUNDED,
        OrderStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order cannot be retried in status '{order.status.value}' ({order.payment_status.value}).",
        )

    provider = get_payment_provider()
    active_payment = next(
        (
            p
            for p in order.payments
            if p.status == PaymentStatus.CREATED and p.gateway_name == provider.gateway_name
        ),
        None,
    )
    if not active_payment:
        gateway_init = provider.create_order(
            order_number=order.order_number,
            amount=_quantize(order.total_amount),
            currency=order.currency,
            notes={"order_id": str(order.id), "customer_id": str(customer.id), "retry": "true"},
        )
        active_payment = Payment(
            order_id=order.id,
            customer_id=customer.id,
            gateway_name=gateway_init.gateway_name,
            gateway_order_id=gateway_init.gateway_order_id,
            amount=_quantize(order.total_amount),
            currency=order.currency,
            status=PaymentStatus.CREATED,
            is_signature_verified=False,
            provider_metadata=gateway_init.metadata,
        )
        db.add(active_payment)
        pub_key = gateway_init.public_key_id
    else:
        pub_key = _resolve_public_key_id(provider)

    order.status = OrderStatus.PENDING
    order.payment_status = OrderPaymentStatus.PENDING
    db.flush()

    return CheckoutResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        subtotal_amount=_quantize(order.subtotal_amount),
        discount_amount=_quantize(order.discount_amount),
        total_amount=_quantize(order.total_amount),
        currency=order.currency,
        payment=PaymentInitPayload(
            payment_id=active_payment.id,
            gateway_name=active_payment.gateway_name,
            gateway_order_id=active_payment.gateway_order_id,
            public_key_id=pub_key,
            amount=_quantize(active_payment.amount),
            amount_subunits=int((Decimal(str(active_payment.amount)) * 100).to_integral_value()),
            currency=active_payment.currency,
        ),
        created_at=order.created_at,
    )



# ===========================================================================
# 4. CENTRALIZED STATE TRANSITIONS, PAYMENT VERIFICATION & WEBHOOKS
# ===========================================================================


def _load_order_full(db: Session, order_id: uuid.UUID, for_update: bool = False) -> Order:
    if for_update:
        # Lock the Order row itself (PostgreSQL forbids FOR UPDATE on nullable outer-joined sides)
        locked_id = db.scalar(
            select(Order.id).where(Order.id == order_id).with_for_update()
        )
        if not locked_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payments),
            selectinload(Order.downloads),
        )
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    return order


def _finalize_successful_capture(
    db: Session,
    order: Order,
    payment: Payment,
    gateway_payment_id: str,
    gateway_signature: Optional[str],
    payment_method: Optional[str],
) -> None:
    """Centralized atomic transition for a verified payment capture."""
    if payment.status not in ALLOWED_PAYMENT_TRANSITIONS or (
        payment.status != PaymentStatus.CAPTURED
        and PaymentStatus.CAPTURED not in ALLOWED_PAYMENT_TRANSITIONS[payment.status]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition payment from {payment.status.value} to captured.",
        )

    now = datetime.now(timezone.utc)
    payment.gateway_payment_id = gateway_payment_id
    if gateway_signature:
        payment.gateway_signature = gateway_signature
    payment.payment_method = payment_method or payment.payment_method or "upi"
    payment.is_signature_verified = True
    payment.status = PaymentStatus.CAPTURED
    payment.verified_at = now
    payment.failure_reason = None

    order.payment_status = OrderPaymentStatus.PAID
    order.status = OrderStatus.FULFILLED
    order.paid_at = order.paid_at or now
    order.fulfilled_at = order.fulfilled_at or now

    # Clear the customer's cart items only AFTER verified payment confirmation
    cart = db.scalar(select(Cart).where(Cart.customer_id == order.customer_id))
    if cart:
        db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    db.add(
        CustomerActivity(
            customer_id=order.customer_id,
            activity_type=ActivityType.PURCHASE,
            details={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "gateway_payment_id": gateway_payment_id,
                "total_amount": str(order.total_amount),
            },
        )
    )
    db.flush()
    post_payment_capture(db=db, order=order, payment=payment)

    customer = order.customer or db.get(Customer, order.customer_id)
    if customer:
        safe_send_commerce_notification(
            email=customer.email,
            template_name="payment_success",
            order_number=order.order_number,
            customer_name=customer.full_name,
            total_amount=order.total_amount,
            currency=order.currency,
        )
        safe_send_commerce_notification(
            email=customer.email,
            template_name="purchase_receipt",
            order_number=order.order_number,
            customer_name=customer.full_name,
            total_amount=order.total_amount,
            currency=order.currency,
            extra={"gateway_payment_id": gateway_payment_id},
        )
        safe_send_commerce_notification(
            email=customer.email,
            template_name="download_ready",
            order_number=order.order_number,
            customer_name=customer.full_name,
            total_amount=order.total_amount,
            currency=order.currency,
        )


def verify_customer_payment(
    db: Session,
    customer: Customer,
    payload: PaymentVerifyRequest,
) -> OrderResponse:
    order = _load_order_full(db, payload.order_id, for_update=True)
    if order.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to verify payment for this order.",
        )

    payment = next(
        (p for p in order.payments if p.gateway_order_id == payload.gateway_order_id),
        None,
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment order reference does not match this order.",
        )

    if (
        payment.status == PaymentStatus.CAPTURED
        or order.payment_status == OrderPaymentStatus.PAID
        or order.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED)
        or payment.status == PaymentStatus.REFUNDED
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment for this order has already been finalized and cannot be verified again.",
        )

    # Prevent payment replay across different orders
    replayed = db.scalar(
        select(Payment).where(
            Payment.gateway_payment_id == payload.gateway_payment_id,
            Payment.id != payment.id,
        )
    )
    if replayed:
        log_payment_event(
            "payment.replay_rejected",
            level=logging.WARNING,
            order_id=str(order.id),
            gateway_payment_id=payload.gateway_payment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gateway payment reference has already been used.",
        )

    if _quantize(payment.amount) != _quantize(order.total_amount) or payment.currency != order.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount or currency mismatch.",
        )

    provider = get_payment_provider()
    is_valid = provider.verify_payment_signature(
        gateway_order_id=payload.gateway_order_id,
        gateway_payment_id=payload.gateway_payment_id,
        signature=payload.gateway_signature,
    )
    if not is_valid:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "signature_verification_failed"
        order.payment_status = OrderPaymentStatus.FAILED
        order.status = OrderStatus.FAILED
        db.flush()
        log_payment_event(
            "payment.signature_verification_failed",
            level=logging.WARNING,
            order_id=str(order.id),
            order_number=order.order_number,
        )
        safe_send_commerce_notification(
            email=customer.email,
            template_name="payment_failed",
            order_number=order.order_number,
            customer_name=customer.full_name,
            total_amount=order.total_amount,
            currency=order.currency,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed.",
        )

    _finalize_successful_capture(
        db=db,
        order=order,
        payment=payment,
        gateway_payment_id=payload.gateway_payment_id,
        gateway_signature=payload.gateway_signature,
        payment_method=payload.payment_method,
    )
    log_payment_event(
        "payment.verified_captured",
        order_id=str(order.id),
        order_number=order.order_number,
        gateway_payment_id=payload.gateway_payment_id,
    )
    order = _load_order_full(db, order.id)
    return to_order_response(db, order)


def process_payment_webhook(
    db: Session,
    raw_body: bytes,
    signature: str,
    event_id_header: Optional[str],
    parsed_body: dict[str, Any],
) -> dict[str, Any]:
    provider = get_payment_provider()
    if not provider.verify_webhook_signature(raw_body, signature):
        log_payment_event("webhook.signature_invalid", level=logging.WARNING, gateway=provider.gateway_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment webhook signature.",
        )

    event_id = (
        event_id_header
        or parsed_body.get("event_id")
        or parsed_body.get("id")
        or ""
    ).strip()
    event_type = (parsed_body.get("event") or parsed_body.get("event_type") or "").strip()
    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload is missing event_id or event_type.",
        )

    # Idempotency check: ignore duplicate webhook deliveries (including concurrent duplicates)
    existing_event = db.scalar(
        select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == event_id)
    )
    if existing_event:
        return {"status": "duplicate_ignored", "event_id": event_id}

    payment_entity = (
        parsed_body.get("payload", {}).get("payment", {}).get("entity", {})
        or parsed_body.get("data", {})
    )
    refund_entity = parsed_body.get("payload", {}).get("refund", {}).get("entity", {})

    gateway_order_id = payment_entity.get("order_id") or parsed_body.get("gateway_order_id")
    gateway_payment_id = (
        payment_entity.get("id")
        or refund_entity.get("payment_id")
        or parsed_body.get("gateway_payment_id")
    )
    refund_id = refund_entity.get("id") or parsed_body.get("refund_id")
    amount_subunits = (
        refund_entity.get("amount")
        if refund_entity and refund_entity.get("amount") is not None
        else payment_entity.get("amount") or parsed_body.get("amount_subunits")
    )
    currency = payment_entity.get("currency") or parsed_body.get("currency")

    try:
        with db.begin_nested():
            db.add(
                PaymentWebhookEvent(
                    gateway_name=provider.gateway_name,
                    event_id=event_id,
                    event_type=event_type,
                    gateway_order_id=gateway_order_id,
                    gateway_payment_id=gateway_payment_id,
                    payload=parsed_body,
                )
            )
            db.flush()
    except IntegrityError:
        return {"status": "duplicate_ignored", "event_id": event_id}

    payment: Optional[Payment] = None
    if gateway_order_id:
        payment = db.scalar(
            select(Payment).where(Payment.gateway_order_id == gateway_order_id)
        )
    if not payment and gateway_payment_id:
        payment = db.scalar(
            select(Payment).where(Payment.gateway_payment_id == gateway_payment_id)
        )
    if not payment:
        log_payment_event(
            "webhook.payment_not_found",
            level=logging.WARNING,
            event_id=event_id,
            event_type=event_type,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referenced payment order not found.",
        )

    # Acquire row lock on Order to serialize concurrent verify vs webhook calls
    order = _load_order_full(db, payment.order_id, for_update=True)
    payment = next((p for p in order.payments if p.id == payment.id), payment)
    customer = order.customer or db.get(Customer, order.customer_id)

    # Validate amount and currency if present in the webhook payload
    if amount_subunits is not None and event_type not in ("payment.refunded", "refund.processed"):
        try:
            parsed_subunits = int(amount_subunits)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook payment amount format is invalid.",
            ) from exc
        expected_subunits = int((Decimal(str(payment.amount)) * Decimal("100")).to_integral_value())
        if parsed_subunits != expected_subunits:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook payment amount does not match order amount.",
            )
    if currency is not None and currency != payment.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook currency does not match order currency.",
        )

    if event_type == "payment.captured":
        if (
            payment.status in (PaymentStatus.CAPTURED, PaymentStatus.REFUNDED)
            or order.payment_status in (OrderPaymentStatus.PAID, OrderPaymentStatus.REFUNDED)
            or order.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED)
        ):
            return {"status": "already_processed", "event_id": event_id}
        if not gateway_payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payment.captured webhook requires gateway_payment_id.",
            )
        replayed = db.scalar(
            select(Payment).where(
                Payment.gateway_payment_id == gateway_payment_id,
                Payment.id != payment.id,
            )
        )
        if replayed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Gateway payment reference has already been used.",
            )
        _finalize_successful_capture(
            db=db,
            order=order,
            payment=payment,
            gateway_payment_id=gateway_payment_id,
            gateway_signature=signature,
            payment_method=payment_entity.get("method", "upi"),
        )
        log_payment_event("webhook.payment_captured", event_id=event_id, order_id=str(order.id))
        return {"status": "captured", "event_id": event_id}

    if event_type == "payment.failed":
        # Out-of-order protection: NEVER downgrade a captured/paid/fulfilled/refunded/cancelled order!
        if (
            payment.status in (PaymentStatus.CAPTURED, PaymentStatus.REFUNDED)
            or order.payment_status in (OrderPaymentStatus.PAID, OrderPaymentStatus.REFUNDED)
            or order.status in (OrderStatus.FULFILLED, OrderStatus.REFUNDED, OrderStatus.CANCELLED)
        ):
            return {"status": "ignored_out_of_order_failure", "event_id": event_id}

        payment.status = PaymentStatus.FAILED
        payment.failure_reason = (
            payment_entity.get("error_description")
            or parsed_body.get("failure_reason")
            or "payment_failed_webhook"
        )
        order.payment_status = OrderPaymentStatus.FAILED
        order.status = OrderStatus.FAILED
        db.flush()

        if customer:
            safe_send_commerce_notification(
                email=customer.email,
                template_name="payment_failed",
                order_number=order.order_number,
                customer_name=customer.full_name,
                total_amount=order.total_amount,
                currency=order.currency,
            )
        return {"status": "failed_recorded", "event_id": event_id}

    if event_type in ("payment.refunded", "refund.processed"):
        if payment.status == PaymentStatus.REFUNDED:
            return {"status": "already_refunded", "event_id": event_id}
        if payment.status != PaymentStatus.CAPTURED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot refund a payment that has not been captured.",
            )
        now = datetime.now(timezone.utc)
        refund_amount = (
            Decimal(str(int(amount_subunits))) / Decimal("100")
            if amount_subunits is not None
            else Decimal(str(payment.amount))
        )
        resolved_refund_id = refund_id or f"rfnd_{uuid.uuid4().hex[:12]}"
        refund_record, _ = post_refund_reversal(
            db=db,
            order=order,
            payment=payment,
            refund_id=resolved_refund_id,
            refund_amount=refund_amount,
            gateway_event_id=event_id,
        )
        if refund_record and refund_record.status == "processed":
            is_full_refund = refund_amount >= quantize_money(payment.amount)
            if is_full_refund:
                payment.status = PaymentStatus.REFUNDED
                payment.refund_id = resolved_refund_id
                payment.refunded_at = now
                order.payment_status = OrderPaymentStatus.REFUNDED
                order.status = OrderStatus.REFUNDED
                for d in order.downloads or []:
                    d.status = DownloadStatus.REVOKED
            else:
                payment.refunded_at = payment.refunded_at or now
        db.flush()

        if customer:
            safe_send_commerce_notification(
                email=customer.email,
                template_name="refund_confirmation",
                order_number=order.order_number,
                customer_name=customer.full_name,
                total_amount=order.total_amount,
                currency=order.currency,
                extra={"refund_id": payment.refund_id},
            )
        return {"status": "refunded", "event_id": event_id}

    return {"status": "unhandled_event_acknowledged", "event_id": event_id}


# ===========================================================================
# 5. ORDER MANAGEMENT (CUSTOMER & ADMIN)
# ===========================================================================


def _is_order_download_eligible(order: Order) -> bool:
    has_verified_capture = any(
        p.status == PaymentStatus.CAPTURED and p.is_signature_verified
        for p in (order.payments or [])
    )
    return bool(
        has_verified_capture
        and order.payment_status == OrderPaymentStatus.PAID
        and order.status in (OrderStatus.CONFIRMED, OrderStatus.FULFILLED)
    )


def _count_item_downloads(order: Order, item: OrderItem) -> int:
    count = 0
    for d in order.downloads or []:
        if d.status in (DownloadStatus.GRANTED, DownloadStatus.COMPLETED):
            if d.order_item_id == item.id or (
                d.order_item_id is None and d.product_id and d.product_id == item.product_id
            ):
                count += 1
    return count


def to_order_response(db: Session, order: Order) -> OrderResponse:
    order_eligible = _is_order_download_eligible(order)
    item_responses: list[OrderItemResponse] = []

    for item in order.items or []:
        max_dl = settings.MAX_DOWNLOADS_PER_ORDER_ITEM * max(1, item.quantity)
        used_dl = _count_item_downloads(order, item)
        has_download_source = bool(
            item.product and item.product.private_download_url and item.product.asset_storage_key
        )
        item_eligible = bool(order_eligible and has_download_source and used_dl < max_dl)

        item_responses.append(
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_slug=item.product.slug if item.product else None,
                seller_id=item.seller_id,
                seller_store_name_snapshot=item.seller_store_name_snapshot,
                seller_store_slug_snapshot=item.seller_store_slug_snapshot,
                product_name_snapshot=item.product_name_snapshot,
                original_price_snapshot=_quantize(item.original_price_snapshot),
                purchase_price=_quantize(item.purchase_price),
                quantity=item.quantity,
                line_total=_quantize(Decimal(str(item.purchase_price)) * item.quantity),
                download_eligible=item_eligible,
                downloads_used=used_dl,
                max_downloads=max_dl,
            )
        )

    payment_summaries = [
        PaymentSummaryResponse.model_validate(p)
        for p in sorted(order.payments or [], key=lambda p: p.created_at, reverse=True)
    ]

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        subtotal_amount=_quantize(order.subtotal_amount),
        discount_amount=_quantize(order.discount_amount),
        total_amount=_quantize(order.total_amount),
        currency=order.currency,
        status=order.status,
        payment_status=order.payment_status,
        download_eligible=order_eligible,
        items=item_responses,
        payments=payment_summaries,
        paid_at=order.paid_at,
        fulfilled_at=order.fulfilled_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def list_customer_orders(
    db: Session,
    customer: Customer,
    page: int = 1,
    page_size: int = 10,
    status_filter: Optional[OrderStatus] = None,
) -> PaginatedOrderResponse:
    conds = [Order.customer_id == customer.id]
    if status_filter is not None:
        conds.append(Order.status == status_filter)

    total = db.scalar(select(func.count(Order.id)).where(*conds)) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    orders = db.scalars(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payments),
            selectinload(Order.downloads),
        )
        .where(*conds)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .execution_options(populate_existing=True)
    ).all()

    return PaginatedOrderResponse(
        items=[to_order_response(db, o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_customer_order(db: Session, customer: Customer, order_id: uuid.UUID) -> OrderResponse:
    order = _load_order_full(db, order_id)
    if order.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this order.",
        )
    return to_order_response(db, order)


def get_customer_order_invoice(
    db: Session, customer: Customer, order_id: uuid.UUID
) -> OrderInvoiceResponse:
    order = _load_order_full(db, order_id)
    if order.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this invoice.",
        )

    order_resp = to_order_response(db, order)
    captured_payment = next(
        (p for p in (order.payments or []) if p.status == PaymentStatus.CAPTURED),
        order.payments[0] if order.payments else None,
    )
    return OrderInvoiceResponse(
        invoice_number=f"INV-{order.order_number}",
        order_id=order.id,
        order_number=order.order_number,
        issued_at=order.paid_at or order.created_at,
        customer_name=customer.full_name,
        customer_email=customer.email,
        customer_phone=customer.phone_number,
        currency=order.currency,
        subtotal_amount=order_resp.subtotal_amount,
        discount_amount=order_resp.discount_amount,
        total_amount=order_resp.total_amount,
        payment_status=order.payment_status,
        gateway_payment_id=captured_payment.gateway_payment_id if captured_payment else None,
        payment_method=captured_payment.payment_method if captured_payment else None,
        items=order_resp.items,
    )


def to_admin_order_response(db: Session, order: Order) -> AdminOrderResponse:
    base = to_order_response(db, order)
    cust = order.customer or db.get(Customer, order.customer_id)
    item_name_by_product = {
        i.product_id: i.product_name_snapshot for i in (order.items or []) if i.product_id
    }
    item_name_by_id = {i.id: i.product_name_snapshot for i in (order.items or [])}

    dl_summaries = [
        DownloadRecordSummary(
            id=d.id,
            order_id=d.order_id,
            order_item_id=d.order_item_id,
            product_id=d.product_id,
            product_name=(
                item_name_by_id.get(d.order_item_id)
                or item_name_by_product.get(d.product_id)
                or "Digital Product"
            ),
            status=d.status,
            downloaded_at=d.downloaded_at,
            ip_address=d.ip_address,
        )
        for d in sorted(order.downloads or [], key=lambda x: x.downloaded_at, reverse=True)
    ]

    return AdminOrderResponse(
        **base.model_dump(),
        customer=AdminOrderCustomerInfo(
            id=cust.id,
            full_name=cust.full_name,
            email=cust.email,
            phone_number=cust.phone_number,
        ),
        downloads=dl_summaries,
    )


def list_admin_orders(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    order_status: Optional[OrderStatus] = None,
    payment_status: Optional[OrderPaymentStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> PaginatedAdminOrderResponse:
    conds = []
    if search and search.strip():
        q = f"%{search.strip()}%"
        conds.append(
            or_(
                Order.order_number.ilike(q),
                Customer.email.ilike(q),
                Customer.full_name.ilike(q),
            )
        )
    if order_status is not None:
        conds.append(Order.status == order_status)
    if payment_status is not None:
        conds.append(Order.payment_status == payment_status)
    if date_from is not None:
        conds.append(Order.created_at >= date_from)
    if date_to is not None:
        conds.append(Order.created_at <= date_to)

    count_stmt = (
        select(func.count(Order.id))
        .join(Customer, Order.customer_id == Customer.id)
        .where(*conds)
    )
    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size

    stmt: Select = (
        select(Order)
        .join(Customer, Order.customer_id == Customer.id)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payments),
            selectinload(Order.downloads),
        )
        .where(*conds)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .execution_options(populate_existing=True)
    )
    orders = db.scalars(stmt).all()

    return PaginatedAdminOrderResponse(
        items=[to_admin_order_response(db, o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_admin_order(db: Session, order_id: uuid.UUID) -> AdminOrderResponse:
    order = _load_order_full(db, order_id)
    return to_admin_order_response(db, order)


def update_admin_order_status(
    db: Session,
    admin: Admin,
    order_id: uuid.UUID,
    new_status: OrderStatus,
    ip_address: Optional[str] = None,
) -> AdminOrderResponse:
    order = _load_order_full(db, order_id, for_update=True)
    current_status = order.status

    if new_status == current_status:
        return to_admin_order_response(db, order)

    allowed = ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order state transition from '{current_status.value}' to '{new_status.value}'.",
        )

    # Security enforcement: Admin cannot mark an order as confirmed/fulfilled without verified payment evidence!
    if new_status in (OrderStatus.CONFIRMED, OrderStatus.FULFILLED):
        if not _is_order_download_eligible(order) and not any(
            p.status == PaymentStatus.CAPTURED and p.is_signature_verified
            for p in (order.payments or [])
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot confirm or fulfill an order without a verified captured payment.",
            )

    now = datetime.now(timezone.utc)
    if new_status == OrderStatus.REFUNDED:
        captured_payment = next(
            (p for p in (order.payments or []) if p.status == PaymentStatus.CAPTURED),
            None,
        )
        if captured_payment and captured_payment.gateway_payment_id:
            refund_res = get_payment_provider().initiate_refund(
                captured_payment.gateway_payment_id, order.total_amount
            )
            refund_status = str(refund_res.status).lower()
            if refund_status not in ("processed", "succeeded", "success", "refunded"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Refund provider did not confirm a successful refund.",
                )
            refund_record, _ = post_refund_reversal(
                db=db,
                order=order,
                payment=captured_payment,
                refund_id=refund_res.refund_id,
                refund_amount=order.total_amount,
                gateway_event_id=None,
            )
            if refund_record and refund_record.status == "processed":
                captured_payment.status = PaymentStatus.REFUNDED
                captured_payment.refund_id = refund_res.refund_id
                captured_payment.refunded_at = now
        order.payment_status = OrderPaymentStatus.REFUNDED
        for d in order.downloads or []:
            d.status = DownloadStatus.REVOKED

    order.status = new_status
    if new_status == OrderStatus.FULFILLED and not order.fulfilled_at:
        order.fulfilled_at = now

    record_admin_audit(
        db=db,
        admin=admin,
        action="order.status_updated",
        entity_type="order",
        entity_id=order.id,
        details={
            "order_number": order.order_number,
            "previous_status": current_status.value,
            "new_status": new_status.value,
        },
        ip_address=ip_address,
    )
    db.flush()
    order = _load_order_full(db, order.id)
    return to_admin_order_response(db, order)


def get_admin_order_statistics(db: Session) -> AdminOrderStatisticsResponse:
    row = db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.PENDING).label("pending_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.CONFIRMED).label("confirmed_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.FULFILLED).label("fulfilled_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.CANCELLED).label("cancelled_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.REFUNDED).label("refunded_orders"),
            func.count(Order.id).filter(Order.status == OrderStatus.FAILED).label("failed_orders"),
            func.count(Order.id).filter(Order.payment_status == OrderPaymentStatus.PAID).label("paid_orders"),
            func.count(Order.id)
            .filter(Order.payment_status.in_([OrderPaymentStatus.UNPAID, OrderPaymentStatus.PENDING]))
            .label("unpaid_orders"),
            func.coalesce(
                func.sum(Order.total_amount).filter(Order.payment_status == OrderPaymentStatus.PAID),
                Decimal("0.00"),
            ).label("total_revenue"),
            func.coalesce(
                func.sum(Order.total_amount).filter(Order.payment_status == OrderPaymentStatus.REFUNDED),
                Decimal("0.00"),
            ).label("total_refunded"),
        )
    ).one()
    total_downloads = db.scalar(select(func.count(DownloadRecord.id))) or 0

    return AdminOrderStatisticsResponse(
        total_orders=int(row.total_orders or 0),
        pending_orders=int(row.pending_orders or 0),
        confirmed_orders=int(row.confirmed_orders or 0),
        fulfilled_orders=int(row.fulfilled_orders or 0),
        cancelled_orders=int(row.cancelled_orders or 0),
        refunded_orders=int(row.refunded_orders or 0),
        failed_orders=int(row.failed_orders or 0),
        paid_orders=int(row.paid_orders or 0),
        unpaid_orders=int(row.unpaid_orders or 0),
        total_revenue=_quantize(row.total_revenue or Decimal("0.00")),
        total_refunded_amount=_quantize(row.total_refunded or Decimal("0.00")),
        total_downloads=total_downloads,
    )


# ===========================================================================
# 6. SECURE DIGITAL PRODUCT DELIVERY
# ===========================================================================


def _create_signed_download_token(
    download_id: uuid.UUID,
    customer_id: uuid.UUID,
    order_item_id: uuid.UUID,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.SIGNED_DOWNLOAD_TOKEN_EXPIRE_SECONDS)
    claims = {
        "iss": JWT_ISSUER,
        "aud": DOWNLOAD_TOKEN_AUDIENCE,
        "sub": str(customer_id),
        "did": str(download_id),
        "oiid": str(order_item_id),
        "type": "signed_download",
        "exp": expires_at,
    }
    token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_signed_download_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=DOWNLOAD_TOKEN_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        if payload.get("type") != "signed_download":
            return None
        return payload
    except JWTError:
        return None


def _validate_private_download_source(private_url: Optional[str]) -> str:
    if not private_url or not private_url.strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digital download source is not configured for this product.",
        )
    cleaned = private_url.strip()
    # Guard against path traversal sequences in storage paths or URLs
    if ".." in cleaned or "\\\\" in cleaned or re.search(r"(?i)%2e%2e", cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unsafe download storage path detected.",
        )
    return cleaned


def get_customer_downloads_overview(
    db: Session, customer: Customer
) -> CustomerDownloadsOverviewResponse:
    orders = db.scalars(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payments),
            selectinload(Order.downloads),
        )
        .where(
            Order.customer_id == customer.id,
            Order.payment_status == OrderPaymentStatus.PAID,
        )
        .order_by(Order.created_at.desc())
        .execution_options(populate_existing=True)
    ).all()

    eligible_items: list[CustomerDownloadableItemResponse] = []
    for o in orders:
        order_ok = _is_order_download_eligible(o)
        for item in o.items or []:
            max_dl = settings.MAX_DOWNLOADS_PER_ORDER_ITEM * max(1, item.quantity)
            used_dl = _count_item_downloads(o, item)
            rem_dl = max(0, max_dl - used_dl)
            has_src = bool(
                item.product and item.product.private_download_url and item.product.asset_storage_key
            )

            eligible_items.append(
                CustomerDownloadableItemResponse(
                    order_id=o.id,
                    order_number=o.order_number,
                    order_item_id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name_snapshot,
                    product_slug=item.product.slug if item.product else None,
                    purchased_at=o.paid_at or o.created_at,
                    download_eligible=bool(order_ok and has_src and rem_dl > 0),
                    downloads_used=used_dl,
                    max_downloads=max_dl,
                    remaining_downloads=rem_dl,
                    asset_filename=item.product.asset_original_filename if item.product else None,
                    asset_content_type=item.product.asset_content_type if item.product else None,
                    asset_size_bytes=item.product.asset_size_bytes if item.product else None,
                )
            )

    all_downloads = db.scalars(
        select(DownloadRecord)
        .options(selectinload(DownloadRecord.product))
        .where(DownloadRecord.customer_id == customer.id)
        .order_by(DownloadRecord.downloaded_at.desc())
        .limit(200)
    ).all()

    history = [
        DownloadRecordSummary(
            id=d.id,
            order_id=d.order_id,
            order_item_id=d.order_item_id,
            product_id=d.product_id,
            product_name=d.product.name if d.product else "Digital Product",
            status=d.status,
            downloaded_at=d.downloaded_at,
            ip_address=d.ip_address,
        )
        for d in all_downloads
    ]

    return CustomerDownloadsOverviewResponse(
        eligible_items=eligible_items,
        history=history,
    )


def request_digital_product_download(
    db: Session,
    customer: Customer,
    order_item_id: uuid.UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> DownloadGrantResponse:
    order_item = db.scalar(
        select(OrderItem)
        .options(selectinload(OrderItem.product))
        .where(OrderItem.id == order_item_id)
    )
    if not order_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchased order item not found.",
        )

    order = _load_order_full(db, order_item.order_id, for_update=True)
    if order.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to download this item.",
        )

    if not _is_order_download_eligible(order):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Order payment has not been verified or order is not eligible for download.",
        )

    product = order_item.product
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
        if not storage.exists(product.asset_storage_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Digital asset file is currently unavailable.",
            )
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Digital asset storage service is temporarily unavailable.",
        ) from exc

    max_dl = settings.MAX_DOWNLOADS_PER_ORDER_ITEM * max(1, order_item.quantity)
    used_dl = _count_item_downloads(order, order_item)
    if used_dl >= max_dl:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Download limit of {max_dl} reached for this order item.",
        )

    record = DownloadRecord(
        customer_id=customer.id,
        product_id=product.id,
        order_id=order.id,
        order_item_id=order_item.id,
        status=DownloadStatus.GRANTED,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(record)
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.DOWNLOAD,
            product_id=product.id,
            details={"order_id": str(order.id), "order_item_id": str(order_item.id)},
        )
    )
    db.flush()

    signed_token, expires_at = _create_signed_download_token(
        download_id=record.id,
        customer_id=customer.id,
        order_item_id=order_item.id,
    )
    new_used = used_dl + 1
    return DownloadGrantResponse(
        download_id=record.id,
        order_id=order.id,
        order_item_id=order_item.id,
        product_id=product.id,
        product_name=order_item.product_name_snapshot,
        status=record.status,
        download_url=f"/api/downloads/{record.id}/file?token={signed_token}",
        expires_at=expires_at,
        downloads_used=new_used,
        max_downloads=max_dl,
        remaining_downloads=max(0, max_dl - new_used),
        filename=product.asset_original_filename,
    )


def get_download_record_status(
    db: Session,
    customer: Customer,
    download_id: uuid.UUID,
) -> DownloadStatusResponse:
    record = db.scalar(
        select(DownloadRecord)
        .options(selectinload(DownloadRecord.product))
        .where(DownloadRecord.id == download_id)
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download record not found.",
        )
    if record.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this download record.",
        )

    order = _load_order_full(db, record.order_id)
    order_item = next(
        (
            i
            for i in (order.items or [])
            if i.id == record.order_item_id or i.product_id == record.product_id
        ),
        None,
    )
    max_dl = settings.MAX_DOWNLOADS_PER_ORDER_ITEM * (order_item.quantity if order_item else 1)
    used_dl = _count_item_downloads(order, order_item) if order_item else 1

    return DownloadStatusResponse(
        download_id=record.id,
        order_id=record.order_id,
        order_item_id=record.order_item_id,
        product_id=record.product_id,
        product_name=(
            order_item.product_name_snapshot
            if order_item
            else (record.product.name if record.product else "Digital Product")
        ),
        status=record.status,
        downloaded_at=record.downloaded_at,
        downloads_used=used_dl,
        max_downloads=max_dl,
        remaining_downloads=max(0, max_dl - used_dl),
    )
