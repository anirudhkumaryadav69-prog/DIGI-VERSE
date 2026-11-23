import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_security_event
from app.core.security import (
    create_customer_access_token,
    create_customer_refresh_token,
    decode_customer_token,
    generate_reset_token,
    generate_secure_otp,
    get_password_hash,
    hash_otp,
    hash_token,
    verify_dummy_password,
    verify_otp_hash,
    verify_password,
)
from app.models.auth import AuthSession, PasswordResetToken, PhoneOTPChallenge
from app.models.customer import Customer, CustomerActivity, LoginHistory
from app.models.enums import AccountStatus, ActivityType, AuthSubjectType, LoginStatus, OTPPurpose
from app.schemas.auth import (
    CustomerChangePasswordRequest,
    CustomerLoginRequest,
    CustomerPhoneUpdateRequest,
    CustomerProfileUpdateRequest,
    CustomerRegisterRequest,
)
from app.services.email_service import DisabledEmailProvider, EmailDeliveryError, get_email_provider
from app.services.sms_service import DisabledSMSProvider, SMSDeliveryResult, get_sms_provider


def _create_customer_session(
    db: Session,
    customer: Customer,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[AuthSession, str, str]:
    session_id = uuid.uuid4()
    family_id = uuid.uuid4()
    access_token = create_customer_access_token(customer.id, session_id)
    refresh_token, expires_at = create_customer_refresh_token(customer.id, session_id, family_id)

    auth_session = AuthSession(
        id=session_id,
        subject_type=AuthSubjectType.CUSTOMER,
        customer_id=customer.id,
        family_id=family_id,
        refresh_token_hash=hash_token(refresh_token),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.flush()
    return auth_session, access_token, refresh_token


def issue_phone_otp_challenge(
    db: Session,
    customer: Customer,
    target_phone: str,
    purpose: OTPPurpose,
) -> tuple[Optional[PhoneOTPChallenge], SMSDeliveryResult]:
    sms_provider = get_sms_provider()
    if isinstance(sms_provider, DisabledSMSProvider):
        log_security_event("auth.otp_delivery_disabled", purpose=purpose.value)
        return None, sms_provider.send_otp(
            target_phone,
            "",
            settings.OTP_EXPIRE_MINUTES,
        )

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=settings.OTP_RATE_WINDOW_MINUTES)

    recent_count = db.scalar(
        select(func.count(PhoneOTPChallenge.id)).where(
            PhoneOTPChallenge.customer_id == customer.id,
            PhoneOTPChallenge.created_at >= window_start,
        )
    )
    if (recent_count or 0) >= settings.OTP_MAX_SENDS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OTP request limit exceeded. Please wait before requesting another code.",
        )

    # Invalidate any previous unconsumed OTP challenges for this customer
    db.execute(
        update(PhoneOTPChallenge)
        .where(
            PhoneOTPChallenge.customer_id == customer.id,
            PhoneOTPChallenge.consumed_at.is_(None),
            PhoneOTPChallenge.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )

    challenge_id = uuid.uuid4()
    otp_code = generate_secure_otp(6)
    context_salt = f"{challenge_id}:{customer.id}:{target_phone}:{purpose.value}"
    otp_digest = hash_otp(otp_code, context_salt)

    challenge = PhoneOTPChallenge(
        id=challenge_id,
        customer_id=customer.id,
        phone_number=target_phone,
        purpose=purpose,
        otp_hash=otp_digest,
        attempts=0,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
        expires_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(challenge)
    db.flush()

    delivery = sms_provider.send_otp(
        target_phone,
        otp_code,
        settings.OTP_EXPIRE_MINUTES,
    )
    return challenge, delivery


def register_customer(
    db: Session,
    payload: CustomerRegisterRequest,
    ip_address: Optional[str],
    valid_inet: Optional[str],
    user_agent: Optional[str],
) -> tuple[Customer, str, str, SMSDeliveryResult]:
    existing_email = db.scalar(
        select(Customer).where(func.lower(Customer.email) == payload.email.lower())
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    existing_phone = db.scalar(
        select(Customer).where(Customer.phone_number == payload.phone_number)
    )
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this phone number already exists.",
        )

    now = datetime.now(timezone.utc)
    customer = Customer(
        full_name=payload.full_name,
        email=payload.email.lower(),
        phone_number=payload.phone_number,
        password_hash=get_password_hash(payload.password),
        is_email_verified=False,
        is_phone_verified=False,
        account_status=AccountStatus.ACTIVE,
        email_marketing_consent=payload.email_marketing_consent,
        whatsapp_marketing_consent=payload.whatsapp_marketing_consent,
        last_login_at=now,
    )
    db.add(customer)
    db.flush()

    # Automatically issue initial phone verification OTP
    _, otp_delivery = issue_phone_otp_challenge(
        db,
        customer,
        customer.phone_number,
        OTPPurpose.PHONE_VERIFY,
    )

    _, access_token, refresh_token = _create_customer_session(db, customer, ip_address, user_agent)

    db.add(
        LoginHistory(
            customer_id=customer.id,
            ip_address=valid_inet,
            browser_info=(user_agent or "")[:255] or None,
            login_status=LoginStatus.SUCCESS,
        )
    )
    db.flush()
    return customer, access_token, refresh_token, otp_delivery


def login_customer(
    db: Session,
    payload: CustomerLoginRequest,
    ip_address: Optional[str],
    valid_inet: Optional[str],
    user_agent: Optional[str],
) -> tuple[Customer, str, str]:
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    customer = db.scalar(
        select(Customer)
        .where(func.lower(Customer.email) == payload.email.lower())
        .with_for_update()
    )
    if not customer:
        verify_dummy_password(payload.password)
        log_security_event("customer.login_failed", reason="unknown_account", ip=ip_address)
        raise generic_error

    now = datetime.now(timezone.utc)
    if customer.locked_until and customer.locked_until > now:
        db.add(
            LoginHistory(
                customer_id=customer.id,
                ip_address=valid_inet,
                browser_info=(user_agent or "")[:255] or None,
                login_status=LoginStatus.LOCKED,
                failure_reason="account_locked",
            )
        )
        db.flush()
        log_security_event("customer.login_blocked_locked", customer_id=str(customer.id), ip=ip_address)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to repeated failed login attempts. Please try again later.",
        )

    if not verify_password(payload.password, customer.password_hash):
        customer.failed_login_attempts = (customer.failed_login_attempts or 0) + 1
        login_state = LoginStatus.FAILED
        reason = "invalid_password"
        if customer.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            customer.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            login_state = LoginStatus.LOCKED
            reason = "account_locked_threshold_reached"

        db.add(
            LoginHistory(
                customer_id=customer.id,
                ip_address=valid_inet,
                browser_info=(user_agent or "")[:255] or None,
                login_status=login_state,
                failure_reason=reason,
            )
        )
        db.flush()
        log_security_event(
            "customer.login_failed",
            customer_id=str(customer.id),
            reason=reason,
            attempts=customer.failed_login_attempts,
            ip=ip_address,
        )
        raise generic_error

    if customer.account_status != AccountStatus.ACTIVE:
        log_security_event("customer.login_blocked_inactive", customer_id=str(customer.id), ip=ip_address)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account is not active.",
        )

    customer.failed_login_attempts = 0
    customer.locked_until = None
    customer.last_login_at = now

    _, access_token, refresh_token = _create_customer_session(db, customer, ip_address, user_agent)

    db.add(
        LoginHistory(
            customer_id=customer.id,
            ip_address=valid_inet,
            browser_info=(user_agent or "")[:255] or None,
            login_status=LoginStatus.SUCCESS,
        )
    )
    db.flush()
    log_security_event("customer.login_success", customer_id=str(customer.id), ip=ip_address)
    return customer, access_token, refresh_token


def request_customer_phone_otp(
    db: Session,
    customer: Customer,
) -> tuple[Optional[PhoneOTPChallenge], SMSDeliveryResult]:
    if customer.pending_phone_number:
        return issue_phone_otp_challenge(
            db, customer, customer.pending_phone_number, OTPPurpose.PHONE_CHANGE
        )
    if not customer.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number is associated with this account.",
        )
    if customer.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is already verified.",
        )
    return issue_phone_otp_challenge(db, customer, customer.phone_number, OTPPurpose.PHONE_VERIFY)


def verify_customer_phone_otp(db: Session, customer: Customer, otp_code: str) -> Customer:
    challenge = db.scalar(
        select(PhoneOTPChallenge)
        .where(PhoneOTPChallenge.customer_id == customer.id)
        .order_by(
            PhoneOTPChallenge.invalidated_at.is_not(None).asc(),
            PhoneOTPChallenge.consumed_at.is_not(None).asc(),
            PhoneOTPChallenge.created_at.desc(),
        )
        .limit(1)
        .with_for_update()
    )
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP verification request found.",
        )

    if challenge.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This OTP has already been used.",
        )

    now = datetime.now(timezone.utc)
    if challenge.invalidated_at is not None or challenge.attempts >= challenge.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This OTP is no longer valid. Please request a new code.",
        )

    if challenge.expires_at <= now:
        challenge.invalidated_at = now
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new code.",
        )

    context_salt = f"{challenge.id}:{customer.id}:{challenge.phone_number}:{challenge.purpose.value}"
    if not verify_otp_hash(otp_code, context_salt, challenge.otp_hash):
        challenge.attempts += 1
        if challenge.attempts >= challenge.max_attempts:
            challenge.invalidated_at = now
            db.flush()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum OTP verification attempts exceeded. Please request a new code.",
            )
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code.",
        )

    challenge.consumed_at = now
    if challenge.purpose == OTPPurpose.PHONE_CHANGE or customer.pending_phone_number == challenge.phone_number:
        conflict = db.scalar(
            select(Customer).where(
                Customer.phone_number == challenge.phone_number,
                Customer.id != customer.id,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is already associated with another account.",
            )
        customer.phone_number = challenge.phone_number
        customer.pending_phone_number = None

    customer.is_phone_verified = True
    db.add(
        CustomerActivity(
            customer_id=customer.id,
            activity_type=ActivityType.PROFILE_UPDATE,
            details={"event": "phone_verified", "purpose": challenge.purpose.value},
        )
    )
    db.flush()
    return customer


def initiate_forgot_password(db: Session, email: str, ip_address: Optional[str]) -> None:
    email_provider = get_email_provider()
    if isinstance(email_provider, DisabledEmailProvider):
        log_security_event("auth.forgot_password_email_disabled", ip=ip_address)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery is temporarily unavailable because email delivery is not configured.",
        )

    customer = db.scalar(
        select(Customer).where(func.lower(Customer.email) == email.lower())
    )
    if not customer or customer.account_status != AccountStatus.ACTIVE:
        # Never disclose whether the email exists
        return

    now = datetime.now(timezone.utc)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.customer_id == customer.id,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )

    raw_token, token_digest = generate_reset_token()
    reset_entry = PasswordResetToken(
        customer_id=customer.id,
        token_hash=token_digest,
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        requested_ip=ip_address,
    )
    db.add(reset_entry)
    db.flush()

    email_provider.send_password_reset_email(
        customer.email, raw_token, settings.PASSWORD_RESET_EXPIRE_MINUTES
    )


def complete_password_reset(db: Session, raw_token: str, new_password: str) -> None:
    token_digest = hash_token(raw_token)
    reset_entry = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_digest)
        .with_for_update()
    )
    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    if reset_entry.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset token has already been used.",
        )

    now = datetime.now(timezone.utc)
    if reset_entry.invalidated_at is not None or reset_entry.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired.",
        )

    customer = db.get(Customer, reset_entry.customer_id)
    if not customer or customer.account_status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to reset password for this account.",
        )

    customer.password_hash = get_password_hash(new_password)
    customer.failed_login_attempts = 0
    customer.locked_until = None
    reset_entry.consumed_at = now

    # Revoke all existing sessions for this customer upon password reset
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.customer_id == customer.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoke_reason="password_reset")
    )
    db.flush()


def rotate_customer_refresh_token(
    db: Session,
    raw_refresh_token: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[Customer, str, str]:
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token was not provided.",
        )

    payload = decode_customer_token(raw_refresh_token, expected_type="customer_refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    try:
        customer_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token.",
        ) from exc

    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    )
    if (
        not auth_session
        or auth_session.subject_type != AuthSubjectType.CUSTOMER
        or auth_session.customer_id != customer_id
        or (payload.get("fid") and str(auth_session.family_id) != str(payload.get("fid")))
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found.",
        )

    now = datetime.now(timezone.utc)
    presented_hash = hash_token(raw_refresh_token)

    # Refresh-token reuse detection: if a rotated-out token is re-presented, revoke the entire family
    if not secrets.compare_digest(auth_session.refresh_token_hash, presented_hash):
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.family_id == auth_session.family_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoke_reason="refresh_token_reuse_detected")
        )
        db.flush()
        log_security_event(
            "customer.refresh_token_reuse_detected",
            customer_id=str(customer_id),
            session_id=str(auth_session.id),
            family_id=str(auth_session.family_id),
            ip=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. Session has been revoked.",
        )

    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked.",
        )

    customer = db.get(Customer, customer_id)
    if not customer or customer.account_status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account is not active.",
        )

    new_access_token = create_customer_access_token(customer.id, auth_session.id)
    new_refresh_token, new_expires_at = create_customer_refresh_token(
        customer.id, auth_session.id, auth_session.family_id
    )

    auth_session.previous_token_hash = auth_session.refresh_token_hash
    auth_session.refresh_token_hash = hash_token(new_refresh_token)
    auth_session.expires_at = new_expires_at
    auth_session.last_used_at = now
    auth_session.ip_address = ip_address
    if user_agent:
        auth_session.user_agent = user_agent[:512]

    db.flush()
    return customer, new_access_token, new_refresh_token


def revoke_customer_session(db: Session, auth_session: AuthSession, reason: str = "user_logout") -> None:
    now = datetime.now(timezone.utc)
    auth_session.revoked_at = now
    auth_session.revoke_reason = reason
    db.flush()


def revoke_all_customer_sessions(db: Session, customer_id: uuid.UUID, reason: str = "logout_all_devices") -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.customer_id == customer_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoke_reason=reason)
    )
    db.flush()


def update_customer_profile(
    db: Session,
    customer: Customer,
    payload: CustomerProfileUpdateRequest,
) -> Customer:
    changed = {}
    if payload.full_name is not None:
        customer.full_name = payload.full_name
        changed["full_name"] = True
    if payload.email_marketing_consent is not None:
        customer.email_marketing_consent = payload.email_marketing_consent
        changed["email_marketing_consent"] = payload.email_marketing_consent
    if payload.whatsapp_marketing_consent is not None:
        if payload.whatsapp_marketing_consent and not customer.phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A verified phone number is required to enable WhatsApp marketing notifications.",
            )
        customer.whatsapp_marketing_consent = payload.whatsapp_marketing_consent
        changed["whatsapp_marketing_consent"] = payload.whatsapp_marketing_consent

    if changed:
        db.add(
            CustomerActivity(
                customer_id=customer.id,
                activity_type=ActivityType.PROFILE_UPDATE,
                details=changed,
            )
        )
        db.flush()
    return customer


def initiate_customer_phone_change(
    db: Session,
    customer: Customer,
    payload: CustomerPhoneUpdateRequest,
) -> Customer:
    if payload.phone_number == customer.phone_number and customer.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already verified on your account.",
        )

    if isinstance(get_sms_provider(), DisabledSMSProvider):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Phone number verification via OTP is currently unavailable.",
        )

    conflict = db.scalar(
        select(Customer).where(
            Customer.phone_number == payload.phone_number,
            Customer.id != customer.id,
        )
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already associated with another account.",
        )

    customer.pending_phone_number = payload.phone_number
    db.flush()

    issue_phone_otp_challenge(db, customer, payload.phone_number, OTPPurpose.PHONE_CHANGE)
    return customer


def change_customer_password(
    db: Session,
    customer: Customer,
    payload: CustomerChangePasswordRequest,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[str, str]:
    if not verify_password(payload.current_password, customer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    customer.password_hash = get_password_hash(payload.new_password)

    # Revoke all prior sessions across all devices and issue a fresh session
    revoke_all_customer_sessions(db, customer.id, reason="password_changed")
    _, access_token, refresh_token = _create_customer_session(db, customer, ip_address, user_agent)
    db.flush()
    return access_token, refresh_token
