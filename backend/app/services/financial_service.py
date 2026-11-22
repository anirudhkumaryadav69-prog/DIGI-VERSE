"""Commission, immutable ledger posting and seller financial summaries.

Accounting assumptions for the existing checkout:
- Checkout gross is the server-side item purchase price multiplied by quantity.
- Existing discounts have already reduced purchase price before commission calculation.
- Taxes are not modeled by the existing checkout; no tax is added to or removed from commission base.
- Payment gateway fees are not currently deducted from the checkout amount and are not modeled.
- Commission is calculated on the post-discount purchase amount; refunds reverse the original snapshot
  proportionally and never increase beyond the original captured or item gross amount.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.financial import (
    CommissionConfiguration,
    CommissionHistory,
    FinancialLedgerEntry,
    FinancialTransaction,
    RefundRecord,
    SellerCommissionOverride,
)
from app.models.order import Order, OrderItem, Payment
from app.models.seller import SellerProfile


def quantize_money(amount: Decimal, precision_minor_units: int = 2) -> Decimal:
    quantum = Decimal("1").scaleb(-precision_minor_units)
    return Decimal(str(amount)).quantize(quantum, rounding=ROUND_HALF_UP)


def get_commission_configuration(db: Session) -> CommissionConfiguration:
    config = db.scalar(
        select(CommissionConfiguration).where(CommissionConfiguration.singleton_key == "default")
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Commission configuration is missing. Financial posting is disabled.",
        )
    return config


def resolve_seller_commission_rate(
    db: Session,
    seller_id: Optional[uuid.UUID],
) -> tuple[Decimal, str, CommissionConfiguration]:
    config = get_commission_configuration(db)
    if seller_id is None:
        return Decimal("0"), "platform_owned", config

    override = db.scalar(
        select(SellerCommissionOverride).where(SellerCommissionOverride.seller_id == seller_id)
    )
    if override:
        rate = Decimal(str(override.rate))
        source = "seller_override"
    else:
        rate = Decimal(str(config.default_rate))
        source = "global_default"

    maximum = Decimal(str(config.maximum_rate))
    if rate < 0 or rate > maximum:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Commission configuration is invalid. Financial posting is disabled.",
        )
    return rate, source, config


def snapshot_order_commissions(db: Session, order: Order) -> None:
    """Snapshot at checkout from server-side order-item amounts and current configuration."""
    for item in order.items:
        if item.commission_rate_snapshot is not None:
            continue
        rate, source, config = resolve_seller_commission_rate(db, item.seller_id)
        gross = quantize_money(item.purchase_price * item.quantity, config.precision_minor_units)
        if gross == 0:
            commission = Decimal("0")
        else:
            commission = quantize_money(
                gross * rate / Decimal("100"),
                config.precision_minor_units,
            )
        net = quantize_money(gross - commission, config.precision_minor_units)
        if commission < 0 or commission > gross or net < 0:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Commission calculation is invalid. Order was not posted.",
            )
        item.commission_rate_snapshot = rate
        item.commission_amount_snapshot = commission
        item.gross_amount_snapshot = gross
        item.net_amount_snapshot = net
        item.commission_currency_snapshot = order.currency
        item.commission_source_snapshot = source
        item.commission_snapshotted_at = datetime.now(timezone.utc)
    db.flush()


def _existing_transaction(db: Session, idempotency_key: str) -> Optional[FinancialTransaction]:
    return db.scalar(
        select(FinancialTransaction).where(FinancialTransaction.idempotency_key == idempotency_key)
    )


def _post_balanced_transaction(
    db: Session,
    *,
    transaction_type: str,
    idempotency_key: str,
    currency: str,
    order: Optional[Order] = None,
    payment: Optional[Payment] = None,
    refund_record: Optional[RefundRecord] = None,
    seller_id: Optional[uuid.UUID] = None,
    provider_transaction_id: Optional[str] = None,
    entries: list[dict],
    metadata: Optional[dict] = None,
) -> FinancialTransaction:
    existing = _existing_transaction(db, idempotency_key)
    if existing:
        return existing

    debit_total = quantize_money(sum(
        (Decimal(str(entry["amount"])) for entry in entries if entry["direction"] == "debit"),
        Decimal("0"),
    ))
    credit_total = quantize_money(sum(
        (Decimal(str(entry["amount"])) for entry in entries if entry["direction"] == "credit"),
        Decimal("0"),
    ))
    if debit_total != credit_total:
        raise RuntimeError("Financial journal entry is not balanced.")

    tx = FinancialTransaction(
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        status="posted",
        currency=currency,
        debit_total=debit_total,
        credit_total=credit_total,
        order_id=order.id if order else None,
        payment_id=payment.id if payment else None,
        refund_record_id=refund_record.id if refund_record else None,
        seller_id=seller_id,
        provider_transaction_id=provider_transaction_id,
        metadata_json=metadata or {},
    )
    db.add(tx)
    db.flush()

    for entry in entries:
        db.add(
            FinancialLedgerEntry(
                transaction_id=tx.id,
                idempotency_key=f"{idempotency_key}:{entry['idempotency_suffix']}",
                entry_type=entry["entry_type"],
                account_code=entry["account_code"],
                direction=entry["direction"],
                amount=quantize_money(Decimal(str(entry["amount"]))),
                currency=currency,
                order_id=order.id if order else None,
                order_item_id=entry.get("order_item_id"),
                payment_id=payment.id if payment else None,
                refund_record_id=refund_record.id if refund_record else None,
                seller_id=entry.get("seller_id"),
                description=entry["description"],
            )
        )
    db.flush()
    return tx


def post_payment_capture(db: Session, order: Order, payment: Payment) -> FinancialTransaction:
    """Post one balanced capture transaction; safe to call repeatedly from verify or webhook."""
    snapshot_order_commissions(db, order)
    idempotency_key = f"capture:{payment.id}"
    existing = _existing_transaction(db, idempotency_key)
    if existing:
        return existing

    entries: list[dict] = []
    for item in order.items:
        gross = Decimal(str(item.gross_amount_snapshot or Decimal("0")))
        commission = Decimal(str(item.commission_amount_snapshot or Decimal("0")))
        net = Decimal(str(item.net_amount_snapshot or Decimal("0")))
        if gross <= 0:
            continue

        if item.seller_id:
            seller_entries = [
                {
                    "idempotency_suffix": f"item:{item.id}:customer-debit",
                    "entry_type": "customer_payment_allocation",
                    "account_code": "CUSTOMER_PAYMENT_CLEARING",
                    "direction": "debit",
                    "amount": gross,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Seller-item customer payment allocated",
                },
            ]
            if commission > 0:
                seller_entries.extend([
                {
                    "idempotency_suffix": f"item:{item.id}:commission-credit",
                    "entry_type": "platform_commission_earnings",
                    "account_code": "PLATFORM_COMMISSION_REVENUE",
                    "direction": "credit",
                    "amount": commission,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Platform commission revenue recognized",
                },
                ])
            if net > 0:
                seller_entries.extend([
                {
                    "idempotency_suffix": f"item:{item.id}:seller-net-credit",
                    "entry_type": "seller_net_earnings",
                    "account_code": "SELLER_NET_PAYABLE",
                    "direction": "credit",
                    "amount": net,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Seller net earnings payable recognized",
                },
                ])
            entries.extend(seller_entries)
        else:
            entries.extend([
                {
                    "idempotency_suffix": f"item:{item.id}:platform-customer-debit",
                    "entry_type": "customer_payment_allocation",
                    "account_code": "CUSTOMER_PAYMENT_CLEARING",
                    "direction": "debit",
                    "amount": gross,
                    "order_item_id": item.id,
                    "seller_id": None,
                    "description": "Platform-owned item customer payment allocated",
                },
                {
                    "idempotency_suffix": f"item:{item.id}:platform-revenue-credit",
                    "entry_type": "platform_product_revenue",
                    "account_code": "PLATFORM_PRODUCT_REVENUE",
                    "direction": "credit",
                    "amount": gross,
                    "order_item_id": item.id,
                    "seller_id": None,
                    "description": "Platform-owned product revenue recognized",
                },
            ])

    if not entries:
        raise RuntimeError("Cannot post a capture transaction without order item allocations.")

    try:
        return _post_balanced_transaction(
            db,
            transaction_type="payment_capture",
            idempotency_key=idempotency_key,
            currency=payment.currency,
            order=order,
            payment=payment,
            provider_transaction_id=payment.gateway_payment_id,
            entries=entries,
            metadata={"order_number": order.order_number, "payment_status": "captured"},
        )
    except IntegrityError as exc:
        existing = _existing_transaction(db, idempotency_key)
        if existing:
            return existing
        raise exc


def _refunded_gross_by_item(db: Session, payment: Payment) -> dict[uuid.UUID, Decimal]:
    rows = db.execute(
        select(FinancialLedgerEntry.order_item_id, func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0")))
        .where(
            FinancialLedgerEntry.payment_id == payment.id,
            FinancialLedgerEntry.entry_type == "payment_reversal",
            FinancialLedgerEntry.direction == "credit",
        )
        .group_by(FinancialLedgerEntry.order_item_id)
    ).all()
    return {
        item_id: Decimal(str(amount))
        for item_id, amount in rows
        if item_id is not None
    }


def post_refund_reversal(
    db: Session,
    order: Order,
    payment: Payment,
    refund_id: str,
    refund_amount: Decimal,
    gateway_event_id: Optional[str] = None,
) -> tuple[Optional[RefundRecord], Optional[FinancialTransaction]]:
    """Post a full or partial refund reversal once, with item-level original snapshot limits."""
    refund_amount = quantize_money(refund_amount)
    if refund_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund amount must be positive.")
    if refund_amount > quantize_money(payment.amount):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Refund exceeds captured payment.")

    existing = db.scalar(select(RefundRecord).where(RefundRecord.refund_id == refund_id))
    if existing:
        if existing.status == "processed":
            tx = db.scalar(
                select(FinancialTransaction).where(
                    FinancialTransaction.refund_record_id == existing.id
                )
            )
            return existing, tx
        if existing.status == "failed":
            return existing, None

    refund = RefundRecord(
        payment_id=payment.id,
        refund_id=refund_id,
        amount=refund_amount,
        currency=payment.currency,
        status="pending",
        gateway_event_id=gateway_event_id,
    )
    db.add(refund)
    db.flush()

    already_refunded = db.scalar(
        select(func.coalesce(func.sum(RefundRecord.amount), Decimal("0"))).where(
            RefundRecord.payment_id == payment.id,
            RefundRecord.status == "processed",
        )
    ) or Decimal("0")
    if quantize_money(Decimal(str(already_refunded)) + refund_amount) > quantize_money(payment.amount):
        refund.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refund total exceeds the original captured payment.",
        )

    refunded_by_item = _refunded_gross_by_item(db, payment)
    remaining_refund = refund_amount
    entries: list[dict] = []
    for item in order.items:
        if remaining_refund <= 0:
            break
        gross = Decimal(str(item.gross_amount_snapshot or item.purchase_price * item.quantity))
        gross = quantize_money(gross)
        already = refunded_by_item.get(item.id, Decimal("0"))
        refundable = max(Decimal("0"), gross - already)
        if refundable <= 0:
            continue
        item_refund = min(refundable, remaining_refund)
        item_refund = quantize_money(item_refund)
        remaining_refund = quantize_money(remaining_refund - item_refund)

        if item.seller_id:
            original_commission = Decimal(str(item.commission_amount_snapshot or Decimal("0")))
            original_gross = gross
            commission_reversal = quantize_money(
                original_commission * item_refund / original_gross
                if original_gross > 0 else Decimal("0")
            )
            commission_reversal = min(original_commission, commission_reversal)
            net_reversal = quantize_money(item_refund - commission_reversal)

            seller_refund_entries = [
                {
                    "idempotency_suffix": f"refund:{refund.id}:item:{item.id}:customer-credit",
                    "entry_type": "payment_reversal",
                    "account_code": "CUSTOMER_PAYMENT_CLEARING",
                    "direction": "credit",
                    "amount": item_refund,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Captured customer payment reversed",
                },
            ]
            if commission_reversal > 0:
                seller_refund_entries.extend([
                    {
                    "idempotency_suffix": f"refund:{refund.id}:item:{item.id}:commission-debit",
                    "entry_type": "commission_reversal",
                    "account_code": "PLATFORM_COMMISSION_REVENUE",
                    "direction": "debit",
                    "amount": commission_reversal,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Original platform commission reversed",
                },
                ])
            if net_reversal > 0:
                seller_refund_entries.extend([
                    {
                    "idempotency_suffix": f"refund:{refund.id}:item:{item.id}:net-debit",
                    "entry_type": "seller_net_earnings",
                    "account_code": "SELLER_NET_PAYABLE",
                    "direction": "debit",
                    "amount": net_reversal,
                    "order_item_id": item.id,
                    "seller_id": item.seller_id,
                    "description": "Seller net payable reversed for refund",
                },
                ])
            entries.extend(seller_refund_entries)
        else:
            entries.extend([
                {
                    "idempotency_suffix": f"refund:{refund.id}:item:{item.id}:platform-debit",
                    "entry_type": "refund_adjustment",
                    "account_code": "PLATFORM_PRODUCT_REVENUE",
                    "direction": "debit",
                    "amount": item_refund,
                    "order_item_id": item.id,
                    "seller_id": None,
                    "description": "Platform-owned product revenue reversed",
                },
                {
                    "idempotency_suffix": f"refund:{refund.id}:item:{item.id}:customer-credit",
                    "entry_type": "payment_reversal",
                    "account_code": "CUSTOMER_PAYMENT_CLEARING",
                    "direction": "credit",
                    "amount": item_refund,
                    "order_item_id": item.id,
                    "seller_id": None,
                    "description": "Platform-owned captured payment reversed",
                },
            ])

    if remaining_refund > 0:
        refund.status = "failed"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refund amount exceeds the original refundable order-item amounts.",
        )

    tx = _post_balanced_transaction(
        db,
        transaction_type="refund_reversal",
        idempotency_key=f"refund:{refund.id}",
        currency=payment.currency,
        order=order,
        payment=payment,
        refund_record=refund,
        provider_transaction_id=refund_id,
        entries=entries,
        metadata={"refund_id": refund_id, "refund_amount": str(refund_amount)},
    )
    refund.status = "processed"
    refund.processed_at = datetime.now(timezone.utc)
    db.flush()
    return refund, tx


def update_global_commission(
    db: Session,
    admin,
    rate: Decimal,
    reason: Optional[str] = None,
) -> CommissionConfiguration:
    config = get_commission_configuration(db)
    rate = quantize_money(rate, 6)
    if rate < 0 or rate > Decimal(str(config.maximum_rate)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Commission rate must be between 0 and the configured maximum.",
        )
    old = Decimal(str(config.default_rate))
    if old == rate:
        return config
    config.default_rate = rate
    config.updated_by_admin_id = admin.id
    db.add(
        CommissionHistory(
            change_type="global_update",
            old_rate=old,
            new_rate=rate,
            currency=config.currency,
            reason=reason,
            changed_by_admin_id=admin.id,
        )
    )
    db.flush()
    return config


def set_seller_commission(
    db: Session,
    admin,
    seller,
    rate: Decimal,
    reason: Optional[str] = None,
) -> SellerCommissionOverride:
    config = get_commission_configuration(db)
    rate = quantize_money(rate, 6)
    if rate < 0 or rate > Decimal(str(config.maximum_rate)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Commission rate must be between 0 and the configured maximum.",
        )
    override = db.scalar(
        select(SellerCommissionOverride).where(SellerCommissionOverride.seller_id == seller.id)
    )
    old = Decimal(str(override.rate)) if override else None
    if override:
        override.rate = rate
        override.updated_by_admin_id = admin.id
    else:
        override = SellerCommissionOverride(
            seller_id=seller.id,
            rate=rate,
            updated_by_admin_id=admin.id,
        )
        db.add(override)
    db.add(
        CommissionHistory(
            change_type="seller_override_set",
            seller_id=seller.id,
            old_rate=old,
            new_rate=rate,
            currency=config.currency,
            reason=reason,
            changed_by_admin_id=admin.id,
        )
    )
    db.flush()
    return override


def remove_seller_commission(db: Session, admin, seller, reason: Optional[str] = None) -> None:
    config = get_commission_configuration(db)
    override = db.scalar(
        select(SellerCommissionOverride).where(SellerCommissionOverride.seller_id == seller.id)
    )
    if not override:
        return
    old = Decimal(str(override.rate))
    db.delete(override)
    db.add(
        CommissionHistory(
            change_type="seller_override_removed",
            seller_id=seller.id,
            old_rate=old,
            new_rate=None,
            currency=config.currency,
            reason=reason,
            changed_by_admin_id=admin.id,
        )
    )
    db.flush()


def get_seller_financial_summary(
    db: Session,
    seller,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    config = get_commission_configuration(db)
    commission_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
        FinancialLedgerEntry.seller_id == seller.id,
        FinancialLedgerEntry.entry_type == "platform_commission_earnings",
        FinancialLedgerEntry.direction == "credit",
    )
    net_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
        FinancialLedgerEntry.seller_id == seller.id,
        FinancialLedgerEntry.entry_type == "seller_net_earnings",
        FinancialLedgerEntry.direction == "credit",
    )
    net_refund_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
        FinancialLedgerEntry.seller_id == seller.id,
        FinancialLedgerEntry.entry_type == "seller_net_earnings",
        FinancialLedgerEntry.direction == "debit",
    )
    commission_refund_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
        FinancialLedgerEntry.seller_id == seller.id,
        FinancialLedgerEntry.entry_type == "commission_reversal",
        FinancialLedgerEntry.direction == "debit",
    )
    settled_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
        FinancialLedgerEntry.seller_id == seller.id,
        FinancialLedgerEntry.entry_type == "payout",
        FinancialLedgerEntry.direction == "debit",
    )

    queries = [
        commission_query,
        net_query,
        net_refund_query,
        commission_refund_query,
        settled_query,
    ]
    if date_from:
        queries = [query.where(FinancialLedgerEntry.posted_at >= date_from) for query in queries]
    if date_to:
        queries = [query.where(FinancialLedgerEntry.posted_at <= date_to) for query in queries]

    commission = Decimal(str(db.scalar(queries[0]) or Decimal("0")))
    net = Decimal(str(db.scalar(queries[1]) or Decimal("0")))
    net_refunds = Decimal(str(db.scalar(queries[2]) or Decimal("0")))
    commission_refunds = Decimal(str(db.scalar(queries[3]) or Decimal("0")))
    settled = Decimal(str(db.scalar(queries[4]) or Decimal("0")))
    net = net - net_refunds
    available = max(Decimal("0"), net - settled)
    pending = Decimal("0")
    commission = commission - commission_refunds
    refunded = net_refunds + commission_refunds
    gross = net + commission

    return {
        "currency": config.currency,
        "gross_sales": quantize_money(gross),
        "platform_commission": quantize_money(commission),
        "net_earnings": quantize_money(net),
        "pending_earnings": quantize_money(pending),
        "available_earnings": quantize_money(available),
        "refunded_amount": quantize_money(refunded),
        "total_settled": quantize_money(settled),
    }


def list_seller_financial_transactions(
    db: Session,
    seller: SellerProfile,
    page: int,
    page_size: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    stmt = (
        select(FinancialTransaction)
        .join(FinancialLedgerEntry, FinancialLedgerEntry.transaction_id == FinancialTransaction.id)
        .where(FinancialLedgerEntry.seller_id == seller.id)
        .distinct()
    )
    if date_from:
        stmt = stmt.where(FinancialTransaction.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(FinancialTransaction.posted_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    rows = db.scalars(
        stmt.order_by(FinancialTransaction.posted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": tx.id,
                "transaction_type": tx.transaction_type,
                "status": tx.status,
                "currency": tx.currency,
                "debit_total": quantize_money(tx.debit_total),
                "credit_total": quantize_money(tx.credit_total),
                "order_id": tx.order_id,
                "payment_id": tx.payment_id,
                "refund_record_id": tx.refund_record_id,
                "provider_transaction_id": tx.provider_transaction_id,
                "posted_at": tx.posted_at,
            }
            for tx in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def list_seller_order_commissions(
    db: Session,
    seller: SellerProfile,
    page: int,
    page_size: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    stmt = (
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            OrderItem.seller_id == seller.id,
            Order.payment_status.in_(("paid", "refunded")),
        )
        .distinct()
    )
    if date_from:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    orders = db.scalars(
        stmt.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for order in orders:
        seller_items = [item for item in order.items if item.seller_id == seller.id]
        gross = sum(
            (quantize_money(item.gross_amount_snapshot or item.purchase_price * item.quantity)
             for item in seller_items),
            Decimal("0"),
        )
        commission = sum(
            (quantize_money(item.commission_amount_snapshot or Decimal("0")) for item in seller_items),
            Decimal("0"),
        )
        net = sum(
            (quantize_money(item.net_amount_snapshot or Decimal("0")) for item in seller_items),
            Decimal("0"),
        )
        refunded = quantize_money(sum(
            (
                Decimal(str(row.amount))
                for row in db.scalars(
                    select(FinancialLedgerEntry).where(
                        FinancialLedgerEntry.seller_id == seller.id,
                        FinancialLedgerEntry.order_id == order.id,
                        FinancialLedgerEntry.entry_type == "payment_reversal",
                        FinancialLedgerEntry.direction == "credit",
                    )
                ).all()
            ),
            Decimal("0"),
        ))
        items.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "currency": order.currency,
            "gross_amount": quantize_money(gross),
            "commission_amount": quantize_money(commission),
            "net_amount": quantize_money(net),
            "refunded_amount": refunded,
            "settled_amount": Decimal("0.00"),
            "paid_at": order.paid_at,
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def list_seller_order_item_commissions(
    db: Session,
    seller: SellerProfile,
    page: int,
    page_size: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    stmt = select(OrderItem).join(Order, OrderItem.order_id == Order.id).where(
        OrderItem.seller_id == seller.id
    )
    if date_from:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    items = db.scalars(
        stmt.order_by(Order.created_at.desc(), OrderItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    response = []
    for item in items:
        order = db.get(Order, item.order_id)
        gross = quantize_money(
            item.gross_amount_snapshot or item.purchase_price * item.quantity
        )
        response.append({
            "order_id": item.order_id,
            "order_item_id": item.id,
            "order_number": order.order_number,
            "product_name_snapshot": item.product_name_snapshot,
            "gross_amount": gross,
            "commission_rate": item.commission_rate_snapshot,
            "commission_amount": quantize_money(item.commission_amount_snapshot or Decimal("0")),
            "net_amount": quantize_money(item.net_amount_snapshot or Decimal("0")),
            "commission_source": item.commission_source_snapshot,
            "commission_snapshotted_at": item.commission_snapshotted_at,
        })
    return {
        "items": response,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_admin_commission_configuration(db: Session) -> dict:
    config = get_commission_configuration(db)
    return {
        "default_rate": quantize_money(config.default_rate, 6),
        "maximum_rate": quantize_money(config.maximum_rate, 6),
        "currency": config.currency,
        "precision_minor_units": config.precision_minor_units,
        "updated_at": config.updated_at,
    }


def list_admin_seller_commissions(
    db: Session,
    page: int,
    page_size: int,
    search: Optional[str] = None,
) -> dict:
    stmt = select(SellerProfile)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (SellerProfile.store_name.ilike(pattern))
            | (SellerProfile.store_slug.ilike(pattern))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    sellers = db.scalars(
        stmt.order_by(SellerProfile.store_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    config = get_commission_configuration(db)
    items = []
    for seller in sellers:
        override = db.scalar(
            select(SellerCommissionOverride).where(SellerCommissionOverride.seller_id == seller.id)
        )
        effective = Decimal(str(override.rate)) if override else Decimal(str(config.default_rate))
        items.append({
            "seller_id": seller.id,
            "store_name": seller.store_name,
            "store_slug": seller.store_slug,
            "override_rate": quantize_money(override.rate, 6) if override else None,
            "effective_rate": quantize_money(effective, 6),
            "currency": config.currency,
            "updated_at": override.updated_at if override else None,
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_admin_seller_commission(db: Session, seller_id: uuid.UUID) -> dict:
    seller = db.get(SellerProfile, seller_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found.")
    config = get_commission_configuration(db)
    override = db.scalar(
        select(SellerCommissionOverride).where(SellerCommissionOverride.seller_id == seller.id)
    )
    effective = Decimal(str(override.rate)) if override else Decimal(str(config.default_rate))
    return {
        "seller_id": seller.id,
        "store_name": seller.store_name,
        "store_slug": seller.store_slug,
        "override_rate": quantize_money(override.rate, 6) if override else None,
        "effective_rate": quantize_money(effective, 6),
        "currency": config.currency,
        "updated_at": override.updated_at if override else None,
    }


def list_admin_financial_ledger(
    db: Session,
    page: int,
    page_size: int,
    seller_id: Optional[uuid.UUID] = None,
    order_id: Optional[uuid.UUID] = None,
    transaction_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    stmt = (
        select(FinancialLedgerEntry, FinancialTransaction.transaction_type)
        .join(FinancialTransaction, FinancialLedgerEntry.transaction_id == FinancialTransaction.id)
    )
    if seller_id:
        stmt = stmt.where(FinancialLedgerEntry.seller_id == seller_id)
    if order_id:
        stmt = stmt.where(FinancialLedgerEntry.order_id == order_id)
    if transaction_type:
        stmt = stmt.where(FinancialTransaction.transaction_type == transaction_type)
    if date_from:
        stmt = stmt.where(FinancialLedgerEntry.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(FinancialLedgerEntry.posted_at <= date_to)

    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    rows = db.execute(
        stmt.order_by(FinancialLedgerEntry.posted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for entry, tx_type in rows:
        items.append({
            "id": entry.id,
            "transaction_id": entry.transaction_id,
            "transaction_type": tx_type,
            "idempotency_key": entry.idempotency_key,
            "entry_type": entry.entry_type,
            "account_code": entry.account_code,
            "direction": entry.direction,
            "amount": quantize_money(entry.amount),
            "currency": entry.currency,
            "order_id": entry.order_id,
            "order_item_id": entry.order_item_id,
            "payment_id": entry.payment_id,
            "refund_record_id": entry.refund_record_id,
            "seller_id": entry.seller_id,
            "description": entry.description,
            "posted_at": entry.posted_at,
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_admin_commission_report(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    config = get_commission_configuration(db)
    sellers = db.scalars(select(SellerProfile).order_by(SellerProfile.store_name)).all()
    report = []
    for seller in sellers:
        gross_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller.id,
            FinancialLedgerEntry.entry_type == "seller_net_earnings",
            FinancialLedgerEntry.direction == "credit",
        )
        commission_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller.id,
            FinancialLedgerEntry.entry_type == "platform_commission_earnings",
            FinancialLedgerEntry.direction == "credit",
        )
        refund_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller.id,
            FinancialLedgerEntry.entry_type == "payment_reversal",
            FinancialLedgerEntry.direction == "credit",
        )
        commission_reversal_query = select(func.coalesce(func.sum(FinancialLedgerEntry.amount), Decimal("0"))).where(
            FinancialLedgerEntry.seller_id == seller.id,
            FinancialLedgerEntry.entry_type == "commission_reversal",
            FinancialLedgerEntry.direction == "debit",
        )
        queries = [gross_query, commission_query, refund_query, commission_reversal_query]
        if date_from:
            queries = [query.where(FinancialLedgerEntry.posted_at >= date_from) for query in queries]
        if date_to:
            queries = [query.where(FinancialLedgerEntry.posted_at <= date_to) for query in queries]
        net = Decimal(str(db.scalar(queries[0]) or Decimal("0")))
        commission = Decimal(str(db.scalar(queries[1]) or Decimal("0")))
        refunded = Decimal(str(db.scalar(queries[2]) or Decimal("0")))
        commission_reversed = Decimal(str(db.scalar(queries[3]) or Decimal("0")))
        commission = commission - commission_reversed
        gross = net + commission
        report.append({
            "seller_id": seller.id,
            "store_name": seller.store_name,
            "gross_sales": quantize_money(gross),
            "commission_amount": quantize_money(commission),
            "net_earnings": quantize_money(net),
            "refunded_amount": quantize_money(refunded),
        })
    return {
        "currency": config.currency,
        "default_rate": quantize_money(config.default_rate, 6),
        "maximum_rate": quantize_money(config.maximum_rate, 6),
        "sellers": report,
    }
