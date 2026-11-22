import uuid
from decimal import Decimal

from sqlalchemy import select
import pytest
from fastapi import HTTPException

from app.core.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.models.admin import AuditLog
from app.models.enums import SellerApplicationStatus
from app.models.financial import FinancialLedgerEntry, FinancialTransaction
from app.models.payout import (
    PayoutAccountVerificationHistory,
    PayoutExecutionAttempt,
    PayoutRequest,
    SellerPayoutAccount,
)
from app.models.seller import SellerProfile
from app.services.admin_auth_service import provision_initial_admin
from app.services.payout_service import create_payout_reservation


def _csrf(client):
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _login_admin(client, db):
    initial = "AdminInitial#2026!"
    active = "AdminActive#2027!"
    provision_initial_admin(db, initial_password_override=initial)
    response = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": initial})
    if response.status_code == 401:
        response = client.post("/api/admin/auth/login", json={"username": "Aayan", "password": active})
    assert response.status_code == 200
    if response.json()["must_change_password"]:
        response = client.post(
            "/api/admin/auth/change-password",
            json={"current_password": initial, "new_password": active},
            headers=_csrf(client),
        )
        assert response.status_code == 200
    return _csrf(client)


def _register_customer(client, name):
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "email": f"{suffix}@example.test",
            "phone_number": f"+9197{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert response.status_code == 201
    return response.json()["customer"], _csrf(client)


def _approve_seller(client, db, name, slug):
    client.cookies.clear()
    customer, headers = _register_customer(client, name)
    application = client.post(
        "/api/seller/application",
        json={
            "store_name": name,
            "store_slug": slug,
            "seller_display_name": name,
            "application_description": "Payout API test seller.",
            "contact_email": customer["email"],
            "country": "India",
            "business_type": "Independent",
            "product_categories": ["Digital"],
        },
        headers=headers,
    )
    assert application.status_code == 201
    seller_id = application.json()["id"]
    cookies = dict(client.cookies)

    client.cookies.clear()
    admin_headers = _login_admin(client, db)
    review = client.post(
        f"/api/admin/sellers/{seller_id}/review",
        json={"action": "approve"},
        headers=admin_headers,
    )
    assert review.status_code == 200

    client.cookies.clear()
    client.cookies.update(cookies)
    return db.get(SellerProfile, seller_id), _csrf(client)


def _post_net(db, seller, amount, direction="credit"):
    tx = FinancialTransaction(
        transaction_type="payment_capture",
        idempotency_key=f"api-net:{uuid.uuid4().hex}",
        status="posted",
        currency="INR",
        debit_total=Decimal(amount),
        credit_total=Decimal(amount),
        seller_id=seller.id,
        metadata_json={},
    )
    db.add(tx)
    db.flush()
    entry = FinancialLedgerEntry(
        transaction_id=tx.id,
        idempotency_key=f"api-net-entry:{uuid.uuid4().hex}",
        entry_type="seller_net_earnings",
        account_code="SELLER_NET_PAYABLE",
        direction=direction,
        amount=Decimal(amount),
        currency="INR",
        seller_id=seller.id,
        description="Payout API test net",
    )
    db.add(entry)
    db.flush()


def test_seller_account_balance_request_cancel_and_duplicate(api_client, db):
    seller, headers = _approve_seller(api_client, db, "Payout Seller A", "payout-seller-a")
    _post_net(db, seller, "1000.00")

    balance = api_client.get("/api/seller/payouts/balance", headers=headers)
    assert balance.status_code == 200
    assert Decimal(balance.json()["seller_net_payable_signed"]) == Decimal("1000.00")
    assert Decimal(balance.json()["available_amount"]) == Decimal("1000.00")

    account = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "upi",
            "display_name": "Primary UPI",
            "masked_identifier": "sell***@upi",
            "provider_account_reference": "token_reference_1",
            "is_default": True,
        },
        headers=headers,
    )
    assert account.status_code == 200
    assert account.json()["masked_identifier"] == "sell***@upi"
    assert "provider_account_reference" not in account.json()
    account_id = account.json()["id"]

    unverified_request = api_client.post(
        "/api/seller/payouts/requests",
        json={"payout_account_id": account_id, "amount": "600.00", "idempotency_key": "dup-api-payout-1"},
        headers=headers,
    )
    assert unverified_request.status_code == 409

    payout_account = db.get(SellerPayoutAccount, uuid.UUID(account_id))
    payout_account.verification_status = "verified"
    db.flush()

    created = api_client.post(
        "/api/seller/payouts/requests",
        json={"payout_account_id": account_id, "amount": "600.00", "idempotency_key": "dup-api-payout-1"},
        headers=headers,
    )
    assert created.status_code == 200
    payout_id = created.json()["id"]

    duplicate = api_client.post(
        "/api/seller/payouts/requests",
        json={"payout_account_id": account_id, "amount": "600.00", "idempotency_key": "dup-api-payout-1"},
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == payout_id

    reserved_balance = api_client.get("/api/seller/payouts/balance", headers=headers)
    assert Decimal(reserved_balance.json()["reserved_amount"]) == Decimal("600.00")
    assert Decimal(reserved_balance.json()["available_amount"]) == Decimal("400.00")

    detail = api_client.get(f"/api/seller/payouts/requests/{payout_id}", headers=headers)
    assert detail.status_code == 200

    cancelled = api_client.post(
        f"/api/seller/payouts/requests/{payout_id}/cancel",
        json={"reason": "Seller cancelled before review"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["reservation_status"] == "released"

    released = api_client.get("/api/seller/payouts/balance", headers=headers)
    assert Decimal(released.json()["reserved_amount"]) == Decimal("0")
    assert Decimal(released.json()["available_amount"]) == Decimal("1000.00")


def test_negative_balance_and_cross_seller_isolation(api_client, db):
    seller_a, headers_a = _approve_seller(api_client, db, "Payout Seller A2", "payout-seller-a2")
    _post_net(db, seller_a, "500.00")
    _post_net(db, seller_a, "700.00", direction="debit")

    balance = api_client.get("/api/seller/payouts/balance", headers=headers_a)
    assert balance.status_code == 200
    assert Decimal(balance.json()["seller_net_payable_signed"]) == Decimal("-200.00")
    assert Decimal(balance.json()["seller_net_payable"]) == Decimal("0")
    assert Decimal(balance.json()["debt_amount"]) == Decimal("200.00")
    assert Decimal(balance.json()["available_amount"]) == Decimal("0")

    seller_b, headers_b = _approve_seller(api_client, db, "Payout Seller B", "payout-seller-b")
    seller_b_request = api_client.get("/api/seller/payouts/requests", headers=headers_b)
    assert seller_b_request.status_code == 200
    assert seller_b_request.json()["total"] == 0


def test_admin_review_approval_rejection_and_audit(api_client, db):
    seller, seller_headers = _approve_seller(api_client, db, "Payout Admin Seller", "payout-admin-seller")
    _post_net(db, seller, "2000.00")

    account_response = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "bank",
            "display_name": "Settlement Account",
            "bank_name": "Test Bank",
            "masked_identifier": "XXXX-1234",
            "is_default": True,
        },
        headers=seller_headers,
    )
    assert account_response.status_code == 200
    account = db.get(SellerPayoutAccount, uuid.UUID(account_response.json()["id"]))
    account.verification_status = "verified"
    db.flush()

    created = api_client.post(
        "/api/seller/payouts/requests",
        json={
            "payout_account_id": str(account.id),
            "amount": "700.00",
            "idempotency_key": "admin-payout-api-1",
        },
        headers=seller_headers,
    )
    assert created.status_code == 200
    payout_id = created.json()["id"]

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    reviewed = api_client.post(
        f"/api/admin/payouts/{payout_id}/review",
        json={"action": "under_review", "reason": "Manual eligibility review"},
        headers=admin_headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "under_review"

    approved = api_client.post(
        f"/api/admin/payouts/{payout_id}/approve",
        json={"reason": "Eligibility verified"},
        headers=admin_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    executed = api_client.post(
        f"/api/admin/payouts/{payout_id}/execute",
        json={"scenario": "success", "idempotency_key": "api-execute-success-1"},
        headers=admin_headers,
    )
    assert executed.status_code == 200
    assert executed.json()["outcome"] == "success"
    assert executed.json()["simulated"] is True

    attempts = api_client.get(
        f"/api/admin/payouts/{payout_id}/attempts",
        headers=admin_headers,
    )
    assert attempts.status_code == 200
    assert len(attempts.json()) == 1

    invalid_approve = api_client.post(
        f"/api/admin/payouts/{payout_id}/approve",
        json={},
        headers=admin_headers,
    )
    assert invalid_approve.status_code == 409

    rejected = api_client.post(
        f"/api/admin/payouts/{payout_id}/reject",
        json={"reason": "Destination documentation incomplete"},
        headers=admin_headers,
    )
    assert rejected.status_code == 409

    missing_reason = api_client.post(
        f"/api/admin/payouts/{payout_id}/reject",
        json={"reason": ""},
        headers=admin_headers,
    )
    assert missing_reason.status_code == 422

    report = api_client.get("/api/admin/payouts/reports", headers=admin_headers)
    assert report.status_code == 200

    audit_count = db.scalar(
        select(AuditLog.id).where(AuditLog.action.in_((
            "payout.request.review",
            "payout.request.approve",
            "payout.request.reject",
        ))).limit(1)
    )
    assert audit_count is not None


def test_customer_and_cross_role_payout_authorization(api_client):
    registration = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "Ordinary Customer",
            "email": f"ordinary-{uuid.uuid4().hex[:8]}@example.test",
            "phone_number": f"+9198{str(uuid.uuid4().int)[:8]}",
            "password": "CustomerPass#2026!",
        },
    )
    assert registration.status_code == 201
    seller_forbidden = api_client.get("/api/seller/payouts/balance")
    assert seller_forbidden.status_code == 403
    admin_forbidden = api_client.get("/api/admin/payouts")
    assert admin_forbidden.status_code == 403


def test_admin_account_verification_approval_rejection_history_and_eligibility(api_client, db):
    seller, seller_headers = _approve_seller(
        api_client,
        db,
        "Verification Seller",
        "verification-seller",
    )
    account_response = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "upi",
            "display_name": "Verification UPI",
            "masked_identifier": "verify***@upi",
            "is_default": True,
        },
        headers=seller_headers,
    )
    assert account_response.status_code == 200
    assert account_response.json()["verification_status"] == "pending"
    account_id = account_response.json()["id"]

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)

    approval = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/approve",
        json={"administrative_notes": "Manual administrator review completed."},
        headers=admin_headers,
    )
    assert approval.status_code == 200
    assert approval.json()["verification_status"] == "verified"
    assert approval.json()["verified_at"] is not None

    duplicate = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/approve",
        json={},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409

    rejection = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/reject",
        json={"reason": "Masked identifier could not be reviewed.", "administrative_notes": "Correction required."},
        headers=admin_headers,
    )
    assert rejection.status_code == 200
    assert rejection.json()["verification_status"] == "rejected"
    assert rejection.json()["verification_reason"] == "Masked identifier could not be reviewed."

    reapproval = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/approve",
        json={"administrative_notes": "Corrected account re-reviewed."},
        headers=admin_headers,
    )
    assert reapproval.status_code == 200
    assert reapproval.json()["verification_status"] == "verified"

    history = api_client.get(
        f"/api/admin/payout-accounts/{account_id}/history?page=1&page_size=20",
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert history.json()["total"] == 3
    assert all("provider_account_reference" not in str(row) for row in history.json()["items"])

    queue = api_client.get(
        "/api/admin/payout-accounts/verification?status=verified",
        headers=admin_headers,
    )
    assert queue.status_code == 200
    assert queue.json()["total"] >= 1


def test_rejection_reason_pending_eligibility_and_seller_authorization(api_client, db):
    seller, seller_headers = _approve_seller(
        api_client,
        db,
        "Verification Seller 2",
        "verification-seller-2",
    )
    account_response = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "bank",
            "display_name": "Review Bank",
            "bank_name": "Test Bank",
            "masked_identifier": "XXXX-9999",
            "is_default": True,
        },
        headers=seller_headers,
    )
    account_id = account_response.json()["id"]

    forbidden = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/approve",
        json={},
        headers=seller_headers,
    )
    assert forbidden.status_code in (401, 403)

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)
    missing_reason = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/reject",
        json={"reason": ""},
        headers=admin_headers,
    )
    assert missing_reason.status_code == 422

    rejected = api_client.post(
        f"/api/admin/payout-accounts/{account_id}/reject",
        json={"reason": "The bank details need correction."},
        headers=admin_headers,
    )
    assert rejected.status_code == 200

    account = db.get(SellerPayoutAccount, uuid.UUID(account_id))
    assert account.verification_status == "rejected"
    assert account.verification_reason == "The bank details need correction."

    _post_net(db, seller, "1000.00")
    with pytest.raises(HTTPException) as exc:
        create_payout_reservation(
            db,
            seller=seller,
            payout_account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key=f"rejected-account-{uuid.uuid4().hex}",
        )
    assert exc.value.status_code == 409


def test_admin_reconciliation_queue_detail_summary_and_resolution(api_client, db):
    seller, seller_headers = _approve_seller(
        api_client,
        db,
        "Reconciliation API Seller",
        "reconciliation-api-seller",
    )
    _post_net(db, seller, "1000.00")
    account_response = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "upi",
            "display_name": "Reconciliation UPI",
            "masked_identifier": "rec***@upi",
            "is_default": True,
        },
        headers=seller_headers,
    )
    account = db.get(SellerPayoutAccount, uuid.UUID(account_response.json()["id"]))
    account.verification_status = "verified"
    db.flush()

    created = api_client.post(
        "/api/seller/payouts/requests",
        json={
            "payout_account_id": str(account.id),
            "amount": "500.00",
            "idempotency_key": "reconciliation-api-payout-1",
        },
        headers=seller_headers,
    )
    assert created.status_code == 200
    payout_id = created.json()["id"]

    api_client.cookies.clear()
    admin_headers = _login_admin(api_client, db)

    queue = api_client.get(
        "/api/admin/payouts/reconciliation",
        headers=admin_headers,
    )
    assert queue.status_code == 200
    assert queue.json()["total"] >= 1

    summary = api_client.get(
        "/api/admin/payouts/reconciliation/summary",
        headers=admin_headers,
    )
    assert summary.status_code == 200
    assert Decimal(summary.json()["total_requested_amount"]) >= Decimal("500.00")

    detail = api_client.get(
        f"/api/admin/payouts/{payout_id}/reconciliation",
        headers=admin_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["payout_id"] == payout_id
    assert detail.json()["classification"] in {
        "consistent",
        "pending",
        "uncertain",
        "failed",
        "settlement_missing",
        "unexpected_settlement",
        "duplicate_settlement",
        "ledger_mismatch",
        "status_mismatch",
        "requires_manual_review",
    }

    payout_detail = api_client.get(
        f"/api/admin/payouts/{payout_id}/detail",
        headers=admin_headers,
    )
    assert payout_detail.status_code == 200
    assert payout_detail.json()["destination"]["masked_identifier"] == "rec***@upi"

    resolved = api_client.post(
        f"/api/admin/payouts/{payout_id}/reconciliation/resolve",
        json={
            "resolution_action": "investigate",
            "resolution_reason": "Exception requires follow-up review.",
            "evidence_reference": "ticket-reconcile-1",
            "expected_classification": detail.json()["classification"],
        },
        headers=admin_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["previous_classification"] == detail.json()["classification"]


def test_seller_payout_attempt_history_is_owned_and_sensitive_data_is_hidden(api_client, db):
    seller, headers = _approve_seller(
        api_client,
        db,
        "Seller Attempt Owner",
        "seller-attempt-owner",
    )
    _post_net(db, seller, "1000.00")
    account_response = api_client.post(
        "/api/seller/payouts/accounts",
        json={
            "account_type": "upi",
            "display_name": "Owner UPI",
            "masked_identifier": "owner***@upi",
            "provider_account_reference": "internal_provider_reference_do_not_return",
            "is_default": True,
        },
        headers=headers,
    )
    account = db.get(SellerPayoutAccount, uuid.UUID(account_response.json()["id"]))
    account.verification_status = "verified"
    db.flush()

    created = api_client.post(
        "/api/seller/payouts/requests",
        json={
            "payout_account_id": str(account.id),
            "amount": "500.00",
            "idempotency_key": "seller-attempt-history-1",
        },
        headers=headers,
    )
    assert created.status_code == 200
    payout_id = created.json()["id"]
    payout = db.get(PayoutRequest, uuid.UUID(payout_id))
    attempt = PayoutExecutionAttempt(
        payout_request_id=payout.id,
        attempt_no=1,
        idempotency_key="seller-attempt-hidden-provider-1",
        provider_name="mock",
        provider_reference="secret_provider_reference",
        status="failed",
        outcome="failed",
        retryable=True,
        uncertain=False,
        sanitized_error="Simulated payout failure.",
        simulated=True,
    )
    db.add(attempt)
    db.flush()

    response = api_client.get(
        f"/api/seller/payouts/requests/{payout_id}/attempts",
        headers=headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert "provider_reference" not in response.text
    assert "idempotency_key" not in response.text
    assert "secret_provider_reference" not in response.text
    assert response.json()[0]["sanitized_error"] == "Simulated payout failure."

    _, other_headers = _approve_seller(
        api_client,
        db,
        "Other Seller",
        "other-seller-attempt",
    )
    forbidden = api_client.get(
        f"/api/seller/payouts/requests/{payout_id}/attempts",
        headers=other_headers,
    )
    assert forbidden.status_code == 404
