import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_security_event
from app.core.security import (
    create_admin_access_token,
    create_admin_refresh_token,
    decode_admin_token,
    get_password_hash,
    hash_token,
    validate_password_strength,
    verify_dummy_password,
    verify_password,
)
from app.models.admin import Admin, AuditLog
from app.models.auth import AuthSession
from app.models.enums import AuthSubjectType
from app.models.settings import StoreSetting
from app.schemas.auth import AdminChangePasswordRequest, AdminLoginRequest

PROVISIONING_SETTING_KEY = "system.initial_admin_provisioned"
PROVISIONING_ADVISORY_LOCK_ID = 7291045
PLACEHOLDER_PASSWORDS = {
    "",
    "change_me_in_env",
    "replace_with_initial_admin_password_only_for_one_time_provisioning",
}


class AdminProvisioningError(RuntimeError):
    """Raised when initial administrator provisioning fails validation or lacks required secrets."""


def _create_admin_session(
    db: Session,
    admin: Admin,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[AuthSession, str, str]:
    session_id = uuid.uuid4()
    family_id = uuid.uuid4()
    access_token = create_admin_access_token(
        admin.id, session_id, must_change_password=admin.must_change_password
    )
    refresh_token, expires_at = create_admin_refresh_token(admin.id, session_id, family_id)

    auth_session = AuthSession(
        id=session_id,
        subject_type=AuthSubjectType.ADMIN,
        admin_id=admin.id,
        family_id=family_id,
        refresh_token_hash=hash_token(refresh_token),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.flush()
    return auth_session, access_token, refresh_token


def provision_initial_admin(
    db: Session,
    initial_password_override: Optional[str] = None,
    username_override: Optional[str] = None,
    email_override: Optional[str] = None,
) -> dict[str, Any]:
    """Secure, idempotent, one-time provisioning of the initial administrator account (`Aayan`).

    - Acquires a PostgreSQL transaction-scoped advisory lock for concurrency safety.
    - Never resets or modifies an existing administrator's password.
    - Permanently records completion in `store_settings` to disable further provisioning.
    - Fails securely if `INITIAL_ADMIN_PASSWORD` is missing or weak when provisioning is needed.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": PROVISIONING_ADVISORY_LOCK_ID})

    target_username = username_override or settings.INITIAL_ADMIN_USERNAME
    target_email = (email_override or settings.INITIAL_ADMIN_EMAIL).lower()

    lock_setting = db.scalar(
        select(StoreSetting).where(StoreSetting.key == PROVISIONING_SETTING_KEY)
    )
    existing_admin = db.scalar(
        select(Admin).where(Admin.username == target_username)
    )

    now = datetime.now(timezone.utc)
    if (lock_setting and lock_setting.value.get("provisioned") is True) or existing_admin is not None:
        # Ensure the permanent one-time lock flag is recorded without touching the existing admin's password
        if not lock_setting:
            db.add(
                StoreSetting(
                    key=PROVISIONING_SETTING_KEY,
                    value={
                        "provisioned": True,
                        "username": target_username,
                        "locked_at": now.isoformat(),
                    },
                )
            )
            db.flush()
        return {
            "created": False,
            "already_provisioned": True,
            "username": target_username,
        }

    raw_password = (
        initial_password_override
        if initial_password_override is not None
        else (os.environ.get("INITIAL_ADMIN_PASSWORD") or settings.INITIAL_ADMIN_PASSWORD)
    )
    if not raw_password or raw_password.strip() in PLACEHOLDER_PASSWORDS:
        raise AdminProvisioningError(
            "INITIAL_ADMIN_PASSWORD environment variable is missing or invalid. "
            "Provisioning aborted securely."
        )

    try:
        validate_password_strength(raw_password)
    except ValueError as exc:
        raise AdminProvisioningError(f"INITIAL_ADMIN_PASSWORD does not meet security policy: {exc}") from exc

    admin = Admin(
        username=target_username,
        email=target_email,
        password_hash=get_password_hash(raw_password),
        is_active=True,
        must_change_password=True,
        failed_login_attempts=0,
    )
    db.add(admin)
    db.flush()

    db.add(
        StoreSetting(
            key=PROVISIONING_SETTING_KEY,
            value={
                "provisioned": True,
                "username": admin.username,
                "admin_id": str(admin.id),
                "provisioned_at": now.isoformat(),
            },
        )
    )
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="admin.initial_provisioned",
            entity_type="admin",
            entity_id=str(admin.id),
            details={"username": admin.username, "must_change_password": True},
        )
    )
    db.flush()

    return {
        "created": True,
        "already_provisioned": False,
        "username": admin.username,
        "admin_id": str(admin.id),
    }


def login_admin(
    db: Session,
    payload: AdminLoginRequest,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[Admin, str, str]:
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid administrator credentials.",
    )

    admin = db.scalar(select(Admin).where(Admin.username == payload.username).with_for_update())
    if not admin:
        verify_dummy_password(payload.password)
        log_security_event("admin.login_failed", reason="unknown_username", ip=ip_address)
        raise generic_error

    now = datetime.now(timezone.utc)
    if admin.locked_until and admin.locked_until > now:
        db.add(
            AuditLog(
                admin_id=admin.id,
                action="admin.login_blocked_locked",
                entity_type="admin",
                entity_id=str(admin.id),
                details={"ip": ip_address},
            )
        )
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Administrator account is temporarily locked due to repeated failed login attempts.",
        )

    if not verify_password(payload.password, admin.password_hash):
        admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
        action = "admin.login_failed"
        if admin.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            admin.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            action = "admin.account_locked"

        db.add(
            AuditLog(
                admin_id=admin.id,
                action=action,
                entity_type="admin",
                entity_id=str(admin.id),
                details={
                    "failed_attempts": admin.failed_login_attempts,
                    "ip": ip_address,
                },
            )
        )
        db.flush()
        raise generic_error

    if not admin.is_active:
        db.add(
            AuditLog(
                admin_id=admin.id,
                action="admin.login_blocked_inactive",
                entity_type="admin",
                entity_id=str(admin.id),
                details={"ip": ip_address},
            )
        )
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is disabled.",
        )

    admin.failed_login_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now

    auth_session, access_token, refresh_token = _create_admin_session(
        db, admin, ip_address, user_agent
    )
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="admin.login_success",
            entity_type="admin",
            entity_id=str(admin.id),
            details={
                "session_id": str(auth_session.id),
                "must_change_password": admin.must_change_password,
                "ip": ip_address,
            },
        )
    )
    db.flush()
    return admin, access_token, refresh_token


def change_admin_password(
    db: Session,
    admin: Admin,
    payload: AdminChangePasswordRequest,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[Admin, str, str]:
    if not verify_password(payload.current_password, admin.password_hash):
        db.add(
            AuditLog(
                admin_id=admin.id,
                action="admin.password_change_failed",
                entity_type="admin",
                entity_id=str(admin.id),
                details={"reason": "invalid_current_password", "ip": ip_address},
            )
        )
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    now = datetime.now(timezone.utc)
    was_initial_change = admin.must_change_password
    admin.password_hash = get_password_hash(payload.new_password)
    admin.must_change_password = False
    admin.password_changed_at = now

    # Revoke all existing admin sessions before issuing a new session
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.admin_id == admin.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoke_reason="admin_password_changed")
    )

    _, access_token, refresh_token = _create_admin_session(db, admin, ip_address, user_agent)
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="admin.initial_password_changed" if was_initial_change else "admin.password_changed",
            entity_type="admin",
            entity_id=str(admin.id),
            details={"ip": ip_address},
        )
    )
    db.flush()
    return admin, access_token, refresh_token


def rotate_admin_refresh_token(
    db: Session,
    raw_refresh_token: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[Admin, str, str]:
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator refresh token was not provided.",
        )

    payload = decode_admin_token(raw_refresh_token, expected_type="admin_refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired administrator refresh token.",
        )

    try:
        admin_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed administrator refresh token.",
        ) from exc

    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    )
    if (
        not auth_session
        or auth_session.subject_type != AuthSubjectType.ADMIN
        or auth_session.admin_id != admin_id
        or (payload.get("fid") and str(auth_session.family_id) != str(payload.get("fid")))
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator session not found.",
        )

    now = datetime.now(timezone.utc)
    presented_hash = hash_token(raw_refresh_token)

    if not secrets.compare_digest(auth_session.refresh_token_hash, presented_hash):
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.family_id == auth_session.family_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoke_reason="admin_refresh_token_reuse_detected")
        )
        db.add(
            AuditLog(
                admin_id=admin_id,
                action="admin.refresh_token_reuse_detected",
                entity_type="admin",
                entity_id=str(admin_id),
                details={"session_id": str(auth_session.id), "ip": ip_address},
            )
        )
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. Administrator session has been revoked.",
        )

    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator session has expired or been revoked.",
        )

    admin = db.get(Admin, admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is disabled.",
        )

    new_access_token = create_admin_access_token(
        admin.id, auth_session.id, must_change_password=admin.must_change_password
    )
    new_refresh_token, new_expires_at = create_admin_refresh_token(
        admin.id, auth_session.id, auth_session.family_id
    )

    auth_session.previous_token_hash = auth_session.refresh_token_hash
    auth_session.refresh_token_hash = hash_token(new_refresh_token)
    auth_session.expires_at = new_expires_at
    auth_session.last_used_at = now
    auth_session.ip_address = ip_address
    if user_agent:
        auth_session.user_agent = user_agent[:512]

    db.flush()
    return admin, new_access_token, new_refresh_token


def revoke_admin_session(
    db: Session,
    admin: Admin,
    auth_session: AuthSession,
    ip_address: Optional[str],
) -> None:
    now = datetime.now(timezone.utc)
    auth_session.revoked_at = now
    auth_session.revoke_reason = "admin_logout"
    db.add(
        AuditLog(
            admin_id=admin.id,
            action="admin.logout",
            entity_type="admin",
            entity_id=str(admin.id),
            details={"session_id": str(auth_session.id), "ip": ip_address},
        )
    )
    db.flush()
