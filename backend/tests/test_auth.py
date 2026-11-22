"""Comprehensive Customer & Administrator Authentication, Authorization, OTP, Session & Provisioning Tests."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    ADMIN_ACCESS_COOKIE,
    ADMIN_REFRESH_COOKIE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CUSTOMER_ACCESS_COOKIE,
    CUSTOMER_REFRESH_COOKIE,
    verify_password,
)
from app.models.admin import Admin, AuditLog
from app.models.auth import AuthSession, PasswordResetToken, PhoneOTPChallenge
from app.models.customer import Customer
from app.services.admin_auth_service import AdminProvisioningError, provision_initial_admin
from app.services.email_service import dev_email_provider
from app.services.sms_service import dev_sms_provider


def _csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    return {CSRF_HEADER_NAME: token} if token else {}


def _register_sample_customer(client, email: str | None = None, phone: str | None = None, password: str = "StrongPass#2026"):
    suffix = uuid.uuid4().hex[:8]
    email = email or f"user-{suffix}@example.test"
    phone = phone or f"+9198{str(uuid.uuid4().int)[:8]}"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Aarav Sharma",
            "email": email,
            "phone_number": phone,
            "password": password,
            "email_marketing_consent": True,
            "whatsapp_marketing_consent": False,
        },
    )
    return res, email, phone, password


# ===========================================================================
# CUSTOMER AUTHENTICATION TESTS
# ===========================================================================


def test_customer_registration_success_and_cookies(api_client, db):
    res, email, phone, _ = _register_sample_customer(api_client)
    assert res.status_code == 201
    body = res.json()
    assert body["customer"]["email"] == email
    assert body["customer"]["phone_number"] == phone
    assert body["customer"]["is_phone_verified"] is False
    assert body["requires_phone_verification"] is True
    assert CUSTOMER_ACCESS_COOKIE in api_client.cookies
    assert CUSTOMER_REFRESH_COOKIE in api_client.cookies
    assert CSRF_COOKIE_NAME in api_client.cookies

    # Verify password and OTP are stored hashed only
    customer = db.scalar(select(Customer).where(Customer.email == email))
    assert customer is not None
    assert customer.password_hash.startswith("$2")
    challenge = db.scalar(select(PhoneOTPChallenge).where(PhoneOTPChallenge.customer_id == customer.id))
    assert challenge is not None
    otp_code = dev_sms_provider.get_last_otp(phone)
    assert otp_code is not None and len(otp_code) == 6
    assert challenge.otp_hash != otp_code


def test_customer_duplicate_email_registration_rejected(api_client):
    res1, email, _, _ = _register_sample_customer(api_client)
    assert res1.status_code == 201

    # Duplicate email with different case
    res2, _, _, _ = _register_sample_customer(api_client, email=email.upper())
    assert res2.status_code == 409


def test_customer_weak_password_and_invalid_phone_rejected(api_client):
    res = api_client.post(
        "/api/auth/register",
        json={
            "full_name": "Weak Pass",
            "email": "weak@example.test",
            "phone_number": "9876543210",  # Not E.164
            "password": "short",
        },
    )
    assert res.status_code == 422


def test_customer_login_success_and_invalid_credentials(api_client):
    _, email, _, password = _register_sample_customer(api_client)
    api_client.cookies.clear()

    # Wrong password -> generic 401
    wrong_res = api_client.post("/api/auth/login", json={"email": email, "password": "WrongPassword!123"})
    assert wrong_res.status_code == 401
    assert wrong_res.json()["detail"] == "Invalid email or password."

    # Non-existent email -> identical generic 401 (no account enumeration)
    nonexistent_res = api_client.post(
        "/api/auth/login", json={"email": "nobody@example.test", "password": "WrongPassword!123"}
    )
    assert nonexistent_res.status_code == 401
    assert nonexistent_res.json()["detail"] == wrong_res.json()["detail"]

    # Correct credentials -> 200 OK
    ok_res = api_client.post("/api/auth/login", json={"email": email, "password": password})
    assert ok_res.status_code == 200
    assert ok_res.json()["customer"]["email"] == email
    assert CUSTOMER_ACCESS_COOKIE in api_client.cookies


def test_customer_otp_verification_and_verified_access_gate(api_client):
    _, _, phone, _ = _register_sample_customer(api_client)

    # Before OTP verification, sensitive phone-verified endpoint returns 403
    unverified_access = api_client.get("/api/auth/verified-access")
    assert unverified_access.status_code == 403

    otp_code = dev_sms_provider.get_last_otp(phone)
    assert otp_code is not None

    verify_res = api_client.post(
        "/api/auth/otp/verify",
        json={"otp_code": otp_code},
        headers=_csrf_headers(api_client),
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["is_phone_verified"] is True

    # Now sensitive endpoint returns 200
    verified_access = api_client.get("/api/auth/verified-access")
    assert verified_access.status_code == 200


def test_customer_otp_reuse_prevention(api_client):
    _, _, phone, _ = _register_sample_customer(api_client)
    otp_code = dev_sms_provider.get_last_otp(phone)

    first = api_client.post(
        "/api/auth/otp/verify",
        json={"otp_code": otp_code},
        headers=_csrf_headers(api_client),
    )
    assert first.status_code == 200

    # Re-submitting the same OTP is rejected
    second = api_client.post(
        "/api/auth/otp/verify",
        json={"otp_code": otp_code},
        headers=_csrf_headers(api_client),
    )
    assert second.status_code == 400
    assert "already been used" in second.json()["detail"]


def test_customer_expired_otp_rejected(api_client, db):
    res, _, phone, _ = _register_sample_customer(api_client)
    customer_id = uuid.UUID(res.json()["customer"]["id"])
    otp_code = dev_sms_provider.get_last_otp(phone)

    challenge = db.scalar(
        select(PhoneOTPChallenge).where(PhoneOTPChallenge.customer_id == customer_id)
    )
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.flush()

    expired_res = api_client.post(
        "/api/auth/otp/verify",
        json={"otp_code": otp_code},
        headers=_csrf_headers(api_client),
    )
    assert expired_res.status_code == 400
    assert "expired" in expired_res.json()["detail"].lower()


def test_customer_otp_generation_rate_limiting(api_client):
    # Registration already consumes 1 OTP send; 2 more allowed in the window (total = 3)
    _register_sample_customer(api_client)
    headers = _csrf_headers(api_client)

    r2 = api_client.post("/api/auth/otp/send", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["delivery_status"] == "development_only"
    r3 = api_client.post("/api/auth/otp/send", headers=headers)
    assert r3.status_code == 200

    # 4th request within the window is rate-limited with 429
    r4 = api_client.post("/api/auth/otp/send", headers=headers)
    assert r4.status_code == 429


def test_customer_forgot_and_reset_password_invalidates_sessions(api_client, db):
    _, email, _, old_password = _register_sample_customer(api_client)

    # Forgot password for unknown email returns identical response (anti-enumeration)
    unknown_res = api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    known_res = api_client.post("/api/auth/forgot-password", json={"email": email})
    assert unknown_res.status_code == 200
    assert known_res.status_code == 200
    assert unknown_res.json()["message"] == known_res.json()["message"]

    raw_reset_token = dev_email_provider.get_last_reset_token(email)
    assert raw_reset_token is not None

    # Database stores only hashed token, never raw token
    stored_token = db.scalar(select(PasswordResetToken))
    assert stored_token is not None
    assert stored_token.token_hash != raw_reset_token

    new_password = "NewSecurePassword#2027"
    reset_res = api_client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset_token, "new_password": new_password},
    )
    assert reset_res.status_code == 200

    # Existing session must be revoked in DB
    active_sessions = db.scalars(
        select(AuthSession).where(AuthSession.revoked_at.is_(None))
    ).all()
    assert len(active_sessions) == 0

    # Reset token reuse prevention
    reuse_res = api_client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset_token, "new_password": "AnotherPassword#2028"},
    )
    assert reuse_res.status_code == 400
    assert "already been used" in reuse_res.json()["detail"]

    # Login with new password succeeds
    login_res = api_client.post("/api/auth/login", json={"email": email, "password": new_password})
    assert login_res.status_code == 200
    assert old_password != new_password


def test_customer_expired_reset_token_rejected(api_client, db):
    _, email, _, _ = _register_sample_customer(api_client)
    api_client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = dev_email_provider.get_last_reset_token(email)

    token_row = db.scalar(select(PasswordResetToken))
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    res = api_client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "UpdatedPassword#2027"},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_customer_refresh_token_rotation_and_reuse_detection(api_client):
    _register_sample_customer(api_client)
    old_refresh_token = api_client.cookies.get(CUSTOMER_REFRESH_COOKIE)
    assert old_refresh_token is not None

    # Rotate refresh token
    refresh_res = api_client.post("/api/auth/refresh", headers=_csrf_headers(api_client))
    assert refresh_res.status_code == 200
    new_refresh_token = api_client.cookies.get(CUSTOMER_REFRESH_COOKIE)
    assert new_refresh_token != old_refresh_token

    # Replay the old rotated-out refresh token -> reuse detected -> entire session family revoked!
    api_client.cookies.set(CUSTOMER_REFRESH_COOKIE, old_refresh_token)
    reuse_res = api_client.post("/api/auth/refresh", headers=_csrf_headers(api_client))
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()

    # Now even the new refresh token and access token are revoked
    me_res = api_client.get("/api/auth/me")
    assert me_res.status_code == 401


def test_customer_logout_revokes_session(api_client):
    _register_sample_customer(api_client)
    saved_access = api_client.cookies.get(CUSTOMER_ACCESS_COOKIE)

    logout_res = api_client.post("/api/auth/logout", headers=_csrf_headers(api_client))
    assert logout_res.status_code == 200

    # Even if an attacker replays the captured access token after logout, the server rejects it (401)
    replay_res = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {saved_access}"},
    )
    assert replay_res.status_code == 401


def test_customer_unauthorized_profile_access_and_protected_field_modification(api_client):
    # Unauthenticated profile access -> 401
    unauth = api_client.get("/api/auth/profile")
    assert unauth.status_code == 401

    _register_sample_customer(api_client)
    headers = _csrf_headers(api_client)

    # Permitted profile update -> 200
    ok_update = api_client.patch(
        "/api/auth/profile",
        json={"full_name": "Aarav Verma", "email_marketing_consent": False},
        headers=headers,
    )
    assert ok_update.status_code == 200
    assert ok_update.json()["full_name"] == "Aarav Verma"

    # Attempt to modify protected fields (role, is_phone_verified, account_status, id) -> 422 Forbidden by schema
    for forbidden_payload in [
        {"role": "ADMIN"},
        {"is_phone_verified": True},
        {"is_email_verified": True},
        {"account_status": "suspended"},
        {"id": str(uuid.uuid4())},
    ]:
        bad_res = api_client.patch("/api/auth/profile", json=forbidden_payload, headers=headers)
        assert bad_res.status_code == 422


def test_customer_phone_number_update_with_otp_reverification(api_client):
    _register_sample_customer(api_client)
    headers = _csrf_headers(api_client)
    new_phone = "+919711223344"

    change_res = api_client.post(
        "/api/auth/phone/change",
        json={"phone_number": new_phone},
        headers=headers,
    )
    assert change_res.status_code == 200
    assert change_res.json()["pending_phone_number"] == new_phone

    otp_code = dev_sms_provider.get_last_otp(new_phone)
    assert otp_code is not None

    verify_res = api_client.post(
        "/api/auth/otp/verify",
        json={"otp_code": otp_code},
        headers=headers,
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["phone_number"] == new_phone
    assert verify_res.json()["pending_phone_number"] is None
    assert verify_res.json()["is_phone_verified"] is True


# ===========================================================================
# ADMINISTRATOR AUTHENTICATION, PROVISIONING & RBAC TESTS
# ===========================================================================


def test_admin_provisioning_missing_password_fails_securely(db, monkeypatch):
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", None)

    with pytest.raises(AdminProvisioningError):
        provision_initial_admin(db)


def test_admin_one_time_provisioning_idempotency_and_password_preservation(db):
    initial_pw = "AdminInitial#2026!"
    result1 = provision_initial_admin(db, initial_password_override=initial_pw)
    assert result1["created"] is True
    assert result1["username"] == "Aayan"

    admin = db.scalar(select(Admin).where(Admin.username == "Aayan"))
    assert admin is not None
    assert admin.must_change_password is True
    assert verify_password(initial_pw, admin.password_hash) is True
    original_hash = admin.password_hash

    # Second provisioning run must be idempotent and NEVER overwrite the existing password
    result2 = provision_initial_admin(db, initial_password_override="DifferentPass#9999!")
    assert result2["created"] is False
    assert result2["already_provisioned"] is True

    db.refresh(admin)
    assert admin.password_hash == original_hash


def test_admin_login_initial_password_change_enforcement_and_audit_logs(api_client, db):
    initial_pw = "AdminInitial#2026!"
    provision_initial_admin(db, initial_password_override=initial_pw)

    # Admin login with initial password succeeds but flags must_change_password=True
    login_res = api_client.post(
        "/api/admin/auth/login",
        json={"username": "Aayan", "password": initial_pw},
    )
    assert login_res.status_code == 200
    assert login_res.json()["must_change_password"] is True
    assert ADMIN_ACCESS_COOKIE in api_client.cookies
    assert ADMIN_REFRESH_COOKIE in api_client.cookies

    # Administrative operations are blocked (403) while must_change_password is True
    blocked_res = api_client.get("/api/admin/dashboard/overview")
    assert blocked_res.status_code == 403
    assert "password must be changed" in blocked_res.json()["detail"].lower()

    # Change initial password
    new_admin_pw = "AayanNewStrong#2027!"
    change_res = api_client.post(
        "/api/admin/auth/change-password",
        json={"current_password": initial_pw, "new_password": new_admin_pw},
        headers=_csrf_headers(api_client),
    )
    assert change_res.status_code == 200
    assert change_res.json()["must_change_password"] is False

    # Now administrative operations succeed
    overview_res = api_client.get("/api/admin/dashboard/overview")
    assert overview_res.status_code == 200
    assert overview_res.json()["admin"] == "Aayan"

    # Verify audit logs recorded provisioning, login, and initial password change
    actions = set(db.scalars(select(AuditLog.action)).all())
    assert {
        "admin.initial_provisioned",
        "admin.login_success",
        "admin.initial_password_changed",
    } <= actions


def test_admin_account_lockout_after_repeated_failed_attempts(api_client, db):
    initial_pw = "AdminInitial#2026!"
    provision_initial_admin(db, initial_password_override=initial_pw)

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        fail_res = api_client.post(
            "/api/admin/auth/login",
            json={"username": "Aayan", "password": "WrongAdminPassword!1"},
        )
        assert fail_res.status_code == 401

    # Next attempt (even with the correct password!) is blocked with 423 Locked
    locked_res = api_client.post(
        "/api/admin/auth/login",
        json={"username": "Aayan", "password": initial_pw},
    )
    assert locked_res.status_code == 423
    assert "locked" in locked_res.json()["detail"].lower()


def test_rbac_customer_cannot_access_admin_endpoints(api_client, db):
    provision_initial_admin(db, initial_password_override="AdminInitial#2026!")

    # Unauthenticated request to admin endpoint -> 401
    unauth_res = api_client.get("/api/admin/dashboard/overview")
    assert unauth_res.status_code == 401

    # Register & authenticate as a customer
    _register_sample_customer(api_client)
    customer_access = api_client.cookies.get(CUSTOMER_ACCESS_COOKIE)

    # Customer cookie accessing admin endpoint -> 403 Forbidden
    cookie_forbidden = api_client.get("/api/admin/dashboard/overview")
    assert cookie_forbidden.status_code == 403

    # Customer Bearer token accessing admin endpoint -> 403 Forbidden
    bearer_forbidden = api_client.get(
        "/api/admin/dashboard/overview",
        headers={"Authorization": f"Bearer {customer_access}"},
    )
    assert bearer_forbidden.status_code == 403


def test_csrf_protection_enforced_on_cookie_authenticated_mutations(api_client):
    _register_sample_customer(api_client)

    # State-changing request with cookie auth but missing X-CSRF-Token header -> 403 Forbidden
    no_csrf_res = api_client.patch("/api/auth/profile", json={"full_name": "Blocked Name"})
    assert no_csrf_res.status_code == 403
    assert "csrf" in no_csrf_res.json()["detail"].lower()
