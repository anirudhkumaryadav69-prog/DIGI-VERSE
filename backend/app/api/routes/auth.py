from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import (
    enforce_csrf_for_cookie_auth,
    get_current_customer,
    get_current_customer_with_session,
    require_verified_customer,
)
from app.core.rate_limit import (
    check_identifier_rate_limit,
    get_client_ip,
    get_valid_inet_or_none,
    rate_limit,
    rate_limit_customer,
)
from app.core.security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CUSTOMER_REFRESH_COOKIE,
    clear_customer_auth_cookies,
    generate_csrf_token,
    set_customer_auth_cookies,
)
from app.models.auth import AuthSession
from app.models.customer import Customer
from app.schemas.auth import (
    CustomerAuthResponse,
    CustomerChangePasswordRequest,
    CustomerLoginRequest,
    CustomerPhoneUpdateRequest,
    CustomerProfileResponse,
    CustomerProfileUpdateRequest,
    CustomerRegisterRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    OTPVerifyRequest,
    ResetPasswordRequest,
)
from app.services.customer_auth_service import (
    change_customer_password,
    complete_password_reset,
    initiate_customer_phone_change,
    initiate_forgot_password,
    login_customer,
    register_customer,
    request_customer_phone_otp,
    revoke_all_customer_sessions,
    revoke_customer_session,
    rotate_customer_refresh_token,
    update_customer_profile,
    verify_customer_phone_otp,
)

router = APIRouter(prefix="/auth", tags=["Customer Authentication"])


@router.get("/csrf")
def get_csrf_token(response: Response) -> dict[str, str]:
    csrf = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.headers[CSRF_HEADER_NAME] = csrf
    return {"csrf_token": csrf}


@router.post(
    "/register",
    response_model=CustomerAuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                "customer_register",
                max_requests=10,
                window_seconds=60,
                unknown_ip_max_requests=120,
                unknown_ip_window_seconds=60,
            )
        )
    ],
)
def register(
    payload: CustomerRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CustomerAuthResponse:
    check_identifier_rate_limit(
        "customer_register_email",
        payload.email,
        kind="email",
        max_requests=5,
        window_seconds=300,
        db=db,
    )
    check_identifier_rate_limit(
        "customer_register_phone",
        payload.phone_number,
        kind="phone",
        max_requests=5,
        window_seconds=300,
        db=db,
    )
    try:
        customer, access_token, refresh_token, otp_delivery = register_customer(
            db=db,
            payload=payload,
            ip_address=get_client_ip(request),
            valid_inet=get_valid_inet_or_none(request),
            user_agent=request.headers.get("user-agent"),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP delivery is disabled or misconfigured.",
        ) from exc
    db.commit()
    db.refresh(customer)
    csrf = set_customer_auth_cookies(response, access_token, refresh_token)
    reg_message = (
        "Registration successful. Phone OTP verification is currently unavailable."
        if otp_delivery.status == "disabled"
        else "Registration successful. Please verify your phone number with the OTP sent."
    )
    return CustomerAuthResponse(
        message=reg_message,
        customer=CustomerProfileResponse.model_validate(customer),
        requires_phone_verification=not customer.is_phone_verified,
        csrf_token=csrf,
        otp_delivery_status=otp_delivery.status,
        otp_delivery_detail=otp_delivery.safe_detail,
    )


@router.post(
    "/login",
    response_model=CustomerAuthResponse,
    dependencies=[
        Depends(
            rate_limit(
                "customer_login",
                max_requests=15,
                window_seconds=60,
                unknown_ip_max_requests=240,
                unknown_ip_window_seconds=60,
            )
        )
    ],
)
def login(
    payload: CustomerLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CustomerAuthResponse:
    check_identifier_rate_limit(
        "customer_login_email",
        payload.email,
        kind="email",
        max_requests=15,
        window_seconds=60,
        db=db,
    )
    try:
        customer, access_token, refresh_token = login_customer(
            db=db,
            payload=payload,
            ip_address=get_client_ip(request),
            valid_inet=get_valid_inet_or_none(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        db.refresh(customer)
    except Exception:
        # Commit failed login attempt counters / lockout updates before re-raising
        db.commit()
        raise

    csrf = set_customer_auth_cookies(response, access_token, refresh_token)
    return CustomerAuthResponse(
        message="Login successful.",
        customer=CustomerProfileResponse.model_validate(customer),
        requires_phone_verification=not customer.is_phone_verified,
        csrf_token=csrf,
    )


@router.post("/refresh", response_model=CustomerAuthResponse)
def refresh_tokens(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CustomerAuthResponse:
    enforce_csrf_for_cookie_auth(request)
    raw_refresh = request.cookies.get(CUSTOMER_REFRESH_COOKIE)
    try:
        customer, new_access, new_refresh = rotate_customer_refresh_token(
            db=db,
            raw_refresh_token=raw_refresh,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        db.refresh(customer)
    except Exception:
        # Persist reuse-detection session revocations before re-raising
        db.commit()
        clear_customer_auth_cookies(response)
        raise

    csrf = set_customer_auth_cookies(response, new_access, new_refresh)
    return CustomerAuthResponse(
        message="Session refreshed.",
        customer=CustomerProfileResponse.model_validate(customer),
        requires_phone_verification=not customer.is_phone_verified,
        csrf_token=csrf,
    )


@router.post("/logout", response_model=GenericMessageResponse)
def logout(
    response: Response,
    pair: tuple[Customer, AuthSession] = Depends(get_current_customer_with_session),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    _, auth_session = pair
    revoke_customer_session(db, auth_session, reason="user_logout")
    db.commit()
    clear_customer_auth_cookies(response)
    return GenericMessageResponse(message="Logged out successfully.")


@router.post("/logout-all", response_model=GenericMessageResponse)
def logout_all_devices(
    response: Response,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    revoke_all_customer_sessions(db, customer.id, reason="logout_all_devices")
    db.commit()
    clear_customer_auth_cookies(response)
    return GenericMessageResponse(message="Logged out from all devices.")


@router.post(
    "/otp/send",
    response_model=GenericMessageResponse,
    dependencies=[
        Depends(
            rate_limit_customer(
                "customer_otp_send",
                max_requests=10,
                window_seconds=60,
                ip_max_requests=15,
                ip_window_seconds=60,
            )
        )
    ],
)
def send_phone_otp(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    try:
        _, otp_delivery = request_customer_phone_otp(db, customer)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP delivery is disabled or misconfigured.",
        ) from exc
    if otp_delivery.status == "failed":
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=otp_delivery.safe_detail or "OTP delivery provider could not accept the request.",
        )
    if otp_delivery.status == "disabled":
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP delivery is disabled.",
        )
    db.commit()
    message = (
        "Development OTP is available in the backend terminal. No WhatsApp message was sent."
        if otp_delivery.status == "development_only"
        else "A verification code has been accepted for delivery."
    )
    return GenericMessageResponse(
        message=message,
        delivery_status=otp_delivery.status,
        delivery_detail=otp_delivery.safe_detail,
    )


@router.post(
    "/otp/verify",
    response_model=CustomerProfileResponse,
    dependencies=[
        Depends(
            rate_limit_customer(
                "customer_otp_verify",
                max_requests=15,
                window_seconds=60,
                ip_max_requests=25,
                ip_window_seconds=60,
            )
        )
    ],
)
def verify_phone_otp(
    payload: OTPVerifyRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    try:
        updated = verify_customer_phone_otp(db, customer, payload.otp_code)
        db.commit()
        db.refresh(updated)
    except Exception:
        # Persist incremented attempt counter or challenge invalidation
        db.commit()
        raise
    return CustomerProfileResponse.model_validate(updated)


@router.post(
    "/forgot-password",
    response_model=GenericMessageResponse,
    dependencies=[
        Depends(
            rate_limit(
                "customer_forgot_password",
                max_requests=10,
                window_seconds=60,
                unknown_ip_max_requests=120,
                unknown_ip_window_seconds=60,
            )
        )
    ],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    check_identifier_rate_limit(
        "customer_forgot_email",
        payload.email,
        kind="email",
        max_requests=5,
        window_seconds=300,
        db=db,
    )
    initiate_forgot_password(db, payload.email, get_client_ip(request))
    db.commit()
    return GenericMessageResponse(
        message="If an account with that email exists, password reset instructions have been sent."
    )


@router.post(
    "/reset-password",
    response_model=GenericMessageResponse,
    dependencies=[
        Depends(
            rate_limit(
                "customer_reset_password",
                max_requests=10,
                window_seconds=60,
                unknown_ip_max_requests=120,
                unknown_ip_window_seconds=60,
            )
        )
    ],
)
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> GenericMessageResponse:
    check_identifier_rate_limit(
        "customer_reset_token",
        payload.token,
        kind="token",
        max_requests=5,
        window_seconds=300,
        db=db,
    )
    complete_password_reset(db, payload.token, payload.new_password)
    db.commit()
    clear_customer_auth_cookies(response)
    return GenericMessageResponse(
        message="Your password has been reset successfully. Please sign in with your new password."
    )


@router.get("/me", response_model=CustomerProfileResponse)
@router.get("/profile", response_model=CustomerProfileResponse)
def get_profile(
    customer: Customer = Depends(get_current_customer),
) -> CustomerProfileResponse:
    return CustomerProfileResponse.model_validate(customer)


@router.patch("/profile", response_model=CustomerProfileResponse)
@router.put("/profile", response_model=CustomerProfileResponse)
def update_profile(
    payload: CustomerProfileUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    updated = update_customer_profile(db, customer, payload)
    db.commit()
    db.refresh(updated)
    return CustomerProfileResponse.model_validate(updated)


@router.post("/unsubscribe", response_model=CustomerProfileResponse)
def unsubscribe_marketing(
    channel: Literal["all", "email", "whatsapp"] = Query(default="all"),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    """Allow an authenticated customer to opt out of email, WhatsApp, or all marketing campaigns."""
    payload = CustomerProfileUpdateRequest(
        email_marketing_consent=False if channel in ("all", "email") else None,
        whatsapp_marketing_consent=False if channel in ("all", "whatsapp") else None,
    )
    updated = update_customer_profile(db, customer, payload)
    db.commit()
    db.refresh(updated)
    return CustomerProfileResponse.model_validate(updated)


@router.post("/phone/change", response_model=CustomerProfileResponse)
def request_phone_number_change(
    payload: CustomerPhoneUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    try:
        updated = initiate_customer_phone_change(db, customer, payload)
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP delivery is disabled or misconfigured.",
        ) from exc
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(updated)
    return CustomerProfileResponse.model_validate(updated)


@router.post("/change-password", response_model=CustomerAuthResponse)
def change_password(
    payload: CustomerChangePasswordRequest,
    request: Request,
    response: Response,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerAuthResponse:
    access_token, refresh_token = change_customer_password(
        db=db,
        customer=customer,
        payload=payload,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(customer)
    csrf = set_customer_auth_cookies(response, access_token, refresh_token)
    return CustomerAuthResponse(
        message="Password changed successfully. All previous sessions have been revoked.",
        customer=CustomerProfileResponse.model_validate(customer),
        requires_phone_verification=not customer.is_phone_verified,
        csrf_token=csrf,
    )


@router.get("/verified-access", response_model=GenericMessageResponse)
def check_verified_customer_access(
    customer: Customer = Depends(require_verified_customer),
) -> GenericMessageResponse:
    """Protected endpoint verifying that phone-verified customer status is enforced for sensitive actions."""
    return GenericMessageResponse(
        message=f"Verified customer access granted for {customer.email}."
    )
