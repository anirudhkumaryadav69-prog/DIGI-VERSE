import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    ADMIN_ACCESS_COOKIE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CUSTOMER_ACCESS_COOKIE,
    decode_admin_token,
    decode_customer_token,
)
from app.models.admin import Admin
from app.models.auth import AuthSession
from app.models.customer import Customer
from app.models.enums import AccountStatus, AuthSubjectType, SellerApplicationStatus
from app.models.seller import SellerProfile

bearer_scheme = HTTPBearer(auto_error=False)
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def enforce_csrf_for_cookie_auth(request: Request) -> None:
    """Validate Double-Submit CSRF token when a state-changing request uses cookie authentication."""
    if request.method.upper() not in UNSAFE_METHODS:
        return
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid.",
        )


def _extract_token(
    request: Request,
    cookie_name: str,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> tuple[Optional[str], bool]:
    """Return (raw_jwt_token, used_cookie_auth)."""
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token, True
    if credentials and credentials.credentials:
        return credentials.credentials, False
    return None, False


def get_current_customer_with_session(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> tuple[Customer, AuthSession]:
    token, used_cookie = _extract_token(request, CUSTOMER_ACCESS_COOKIE, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_customer_token(token, expected_type="customer_access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if used_cookie:
        enforce_csrf_for_cookie_auth(request)

    try:
        customer_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
        ) from exc

    now = datetime.now(timezone.utc)
    auth_session = db.get(AuthSession, session_id)
    if (
        not auth_session
        or auth_session.subject_type != AuthSubjectType.CUSTOMER
        or auth_session.customer_id != customer_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
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

    return customer, auth_session


def get_current_customer(
    pair: tuple[Customer, AuthSession] = Depends(get_current_customer_with_session),
) -> Customer:
    """Return the authenticated active customer (phone verification may still be pending)."""
    return pair[0]


def require_verified_customer(
    customer: Customer = Depends(get_current_customer),
) -> Customer:
    """Require an authenticated customer whose phone number has been verified via OTP."""
    if not customer.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone number verification is required before accessing this feature.",
        )
    return customer


def get_current_seller_optional(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> Optional[SellerProfile]:
    """Return the authenticated customer's SellerProfile if one exists (regardless of approval status)."""
    from sqlalchemy import select

    return db.scalar(select(SellerProfile).where(SellerProfile.customer_id == customer.id))


def require_approved_seller(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> SellerProfile:
    """Centralized SELLER RBAC dependency derived strictly from authenticated backend Customer identity."""
    from sqlalchemy import select

    seller = db.scalar(select(SellerProfile).where(SellerProfile.customer_id == customer.id))
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An approved seller account is required to access seller functionality.",
        )
    if seller.application_status == SellerApplicationStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your seller account is currently suspended.",
        )
    if seller.application_status == SellerApplicationStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your seller application was rejected.",
        )
    if seller.application_status != SellerApplicationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your seller application is pending administrator approval.",
        )
    return seller


def get_current_admin_with_session(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> tuple[Admin, AuthSession]:
    token, used_cookie = _extract_token(request, ADMIN_ACCESS_COOKIE, credentials)
    if not token:
        # Check if a customer token was sent to an admin endpoint -> 403 Forbidden
        cust_token, _ = _extract_token(request, CUSTOMER_ACCESS_COOKIE, credentials)
        if cust_token and decode_customer_token(cust_token, expected_type="customer_access"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_admin_token(token, expected_type="admin_access")
    if not payload:
        # If the Bearer token is actually a valid customer token, return 403 Forbidden (role violation)
        if decode_customer_token(token, expected_type="customer_access"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired administrator token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if used_cookie:
        enforce_csrf_for_cookie_auth(request)

    try:
        admin_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed administrator token.",
        ) from exc

    now = datetime.now(timezone.utc)
    auth_session = db.get(AuthSession, session_id)
    if (
        not auth_session
        or auth_session.subject_type != AuthSubjectType.ADMIN
        or auth_session.admin_id != admin_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
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

    return admin, auth_session


def get_current_admin_allow_password_change(
    pair: tuple[Admin, AuthSession] = Depends(get_current_admin_with_session),
) -> Admin:
    """Return authenticated admin even if must_change_password is True (for /me, /change-password, /logout)."""
    return pair[0]


def require_admin(
    admin: Admin = Depends(get_current_admin_allow_password_change),
) -> Admin:
    """Centralized ADMIN RBAC dependency. Blocks all administrative actions until initial password is changed."""
    if admin.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Initial password must be changed before performing administrative operations.",
        )
    return admin
