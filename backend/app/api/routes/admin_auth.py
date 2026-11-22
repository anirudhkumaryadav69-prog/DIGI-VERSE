from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import (
    enforce_csrf_for_cookie_auth,
    get_current_admin_allow_password_change,
    get_current_admin_with_session,
    require_admin,
)
from app.core.rate_limit import get_client_ip, rate_limit
from app.core.security import (
    ADMIN_REFRESH_COOKIE,
    clear_admin_auth_cookies,
    set_admin_auth_cookies,
)
from app.models.admin import Admin
from app.models.auth import AuthSession
from app.schemas.auth import (
    AdminAuthResponse,
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminProfileResponse,
    GenericMessageResponse,
)
from app.services.admin_auth_service import (
    change_admin_password,
    login_admin,
    revoke_admin_session,
    rotate_admin_refresh_token,
)
from app.services.operations_service import get_advanced_dashboard_overview

router = APIRouter(prefix="/admin", tags=["Administrator Authentication & Portal"])


@router.post(
    "/auth/login",
    response_model=AdminAuthResponse,
    dependencies=[Depends(rate_limit("admin_login", max_requests=15, window_seconds=60))],
)
def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminAuthResponse:
    try:
        admin, access_token, refresh_token = login_admin(
            db=db,
            payload=payload,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        db.refresh(admin)
    except Exception:
        # Commit audit logs and failed attempt / lockout state before re-raising
        db.commit()
        raise

    csrf = set_admin_auth_cookies(response, access_token, refresh_token)
    msg = (
        "Initial password change is required before accessing administrative functions."
        if admin.must_change_password
        else "Administrator login successful."
    )
    return AdminAuthResponse(
        message=msg,
        admin=AdminProfileResponse.model_validate(admin),
        must_change_password=admin.must_change_password,
        csrf_token=csrf,
    )


@router.post("/auth/refresh", response_model=AdminAuthResponse)
def admin_refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminAuthResponse:
    enforce_csrf_for_cookie_auth(request)
    raw_refresh = request.cookies.get(ADMIN_REFRESH_COOKIE)
    try:
        admin, new_access, new_refresh = rotate_admin_refresh_token(
            db=db,
            raw_refresh_token=raw_refresh,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        db.refresh(admin)
    except Exception:
        db.commit()
        clear_admin_auth_cookies(response)
        raise

    csrf = set_admin_auth_cookies(response, new_access, new_refresh)
    return AdminAuthResponse(
        message="Administrator session refreshed.",
        admin=AdminProfileResponse.model_validate(admin),
        must_change_password=admin.must_change_password,
        csrf_token=csrf,
    )


@router.post("/auth/logout", response_model=GenericMessageResponse)
def admin_logout(
    request: Request,
    response: Response,
    pair: tuple[Admin, AuthSession] = Depends(get_current_admin_with_session),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    admin, auth_session = pair
    revoke_admin_session(db, admin, auth_session, ip_address=get_client_ip(request))
    db.commit()
    clear_admin_auth_cookies(response)
    return GenericMessageResponse(message="Administrator logged out successfully.")


@router.get("/auth/me", response_model=AdminProfileResponse)
def admin_me(
    admin: Admin = Depends(get_current_admin_allow_password_change),
) -> AdminProfileResponse:
    return AdminProfileResponse.model_validate(admin)


@router.post("/auth/change-password", response_model=AdminAuthResponse)
def admin_change_password(
    payload: AdminChangePasswordRequest,
    request: Request,
    response: Response,
    admin: Admin = Depends(get_current_admin_allow_password_change),
    db: Session = Depends(get_db),
) -> AdminAuthResponse:
    try:
        updated, access_token, refresh_token = change_admin_password(
            db=db,
            admin=admin,
            payload=payload,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        db.refresh(updated)
    except Exception:
        db.commit()
        raise

    csrf = set_admin_auth_cookies(response, access_token, refresh_token)
    return AdminAuthResponse(
        message="Administrator password updated successfully.",
        admin=AdminProfileResponse.model_validate(updated),
        must_change_password=updated.must_change_password,
        csrf_token=csrf,
    )


@router.get("/dashboard/overview")
def admin_dashboard_overview(
    days_window: int = Query(default=30, ge=1, le=365),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Protected administrative dashboard overview backed entirely by live PostgreSQL aggregates."""
    return get_advanced_dashboard_overview(db=db, admin=admin, days_window=days_window)

