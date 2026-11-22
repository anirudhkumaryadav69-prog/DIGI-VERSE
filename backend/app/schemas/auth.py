import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import validate_e164_phone, validate_password_strength
from app.models.enums import AccountStatus, SellerApplicationStatus

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")


def normalize_and_validate_email(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned or len(cleaned) > 255 or not EMAIL_REGEX.match(cleaned):
        raise ValueError("Enter a valid email address.")
    return cleaned


class StrictRequestModel(BaseModel):
    """Base request schema that forbids unexpected or protected fields (anti-mass-assignment)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Customer Authentication & Profile Schemas
# ---------------------------------------------------------------------------


class CustomerRegisterRequest(StrictRequestModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., max_length=255)
    phone_number: str = Field(..., max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    email_marketing_consent: bool = False
    whatsapp_marketing_consent: bool = False

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return normalize_and_validate_email(v)

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return validate_e164_phone(v)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class CustomerLoginRequest(StrictRequestModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return normalize_and_validate_email(v)


class CustomerProfileResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone_number: Optional[str] = None
    pending_phone_number: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    account_status: AccountStatus
    email_marketing_consent: bool
    whatsapp_marketing_consent: bool
    role: str = "CUSTOMER"
    is_seller: bool = False
    seller_status: Optional[SellerApplicationStatus] = None
    seller_store_slug: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerAuthResponse(BaseModel):
    message: str
    customer: CustomerProfileResponse
    requires_phone_verification: bool
    csrf_token: str
    otp_delivery_status: Optional[str] = None
    otp_delivery_detail: Optional[str] = None


class CustomerProfileUpdateRequest(StrictRequestModel):
    """Permitted profile fields only. Protected fields (role, verification flags, id, status) are forbidden."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    email_marketing_consent: Optional[bool] = None
    whatsapp_marketing_consent: Optional[bool] = None


class CustomerPhoneUpdateRequest(StrictRequestModel):
    phone_number: str = Field(..., max_length=20)

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return validate_e164_phone(v)


class CustomerChangePasswordRequest(StrictRequestModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class OTPVerifyRequest(StrictRequestModel):
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordRequest(StrictRequestModel):
    email: str = Field(..., max_length=255)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return normalize_and_validate_email(v)


class ResetPasswordRequest(StrictRequestModel):
    token: str = Field(..., min_length=16, max_length=256)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


# ---------------------------------------------------------------------------
# Administrator Authentication Schemas
# ---------------------------------------------------------------------------


class AdminLoginRequest(StrictRequestModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class AdminChangePasswordRequest(StrictRequestModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class AdminProfileResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    must_change_password: bool
    role: str = "ADMIN"
    password_changed_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminAuthResponse(BaseModel):
    message: str
    admin: AdminProfileResponse
    must_change_password: bool
    csrf_token: str


class GenericMessageResponse(BaseModel):
    message: str
    delivery_status: Optional[str] = None
    delivery_detail: Optional[str] = None
