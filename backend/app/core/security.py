import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Pre-computed dummy hash used when an account does not exist to prevent timing enumeration.
_DUMMY_PASSWORD_HASH = pwd_context.hash("DigiVerseDummyTimingGuard!2026#")

JWT_ISSUER = "digiverse"
CUSTOMER_AUDIENCE = "digiverse:customer"
ADMIN_AUDIENCE = "digiverse:admin"

CUSTOMER_ACCESS_COOKIE = "dv_customer_access"
CUSTOMER_REFRESH_COOKIE = "dv_customer_refresh"
ADMIN_ACCESS_COOKIE = "dv_admin_access"
ADMIN_REFRESH_COOKIE = "dv_admin_refresh"
CSRF_COOKIE_NAME = "dv_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

E164_PHONE_REGEX = re.compile(r"^\+[1-9][0-9]{7,14}$")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def verify_dummy_password(plain_password: str) -> None:
    """Run constant-work bcrypt verification to mitigate timing side-channels."""
    pwd_context.verify(plain_password, _DUMMY_PASSWORD_HASH)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt password hash."""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> str:
    """Enforce production password complexity rules."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


def validate_e164_phone(phone_number: str) -> str:
    cleaned = phone_number.strip()
    if not E164_PHONE_REGEX.match(cleaned):
        raise ValueError("Phone number must be in E.164 format (e.g. +919876543210).")
    return cleaned


def _customer_jwt_secret() -> str:
    return settings.JWT_SECRET_KEY


def _admin_jwt_secret() -> str:
    """Cryptographically separated signing key for administrator JWTs."""
    if settings.ADMIN_JWT_SECRET_KEY:
        return settings.ADMIN_JWT_SECRET_KEY
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        b"digiverse:admin:key-separation:v1",
        hashlib.sha256,
    ).hexdigest()


def create_customer_access_token(
    customer_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    claims: Dict[str, Any] = {
        "iss": JWT_ISSUER,
        "aud": CUSTOMER_AUDIENCE,
        "sub": str(customer_id),
        "sid": str(session_id),
        "role": "CUSTOMER",
        "type": "customer_access",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(claims, _customer_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_customer_refresh_token(
    customer_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    family_id: str | uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    claims: Dict[str, Any] = {
        "iss": JWT_ISSUER,
        "aud": CUSTOMER_AUDIENCE,
        "sub": str(customer_id),
        "sid": str(session_id),
        "fid": str(family_id),
        "role": "CUSTOMER",
        "type": "customer_refresh",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    token = jwt.encode(claims, _customer_jwt_secret(), algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_customer_token(token: str, expected_type: str = "customer_access") -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            _customer_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=CUSTOMER_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        if payload.get("type") != expected_type or payload.get("role") != "CUSTOMER":
            return None
        return payload
    except JWTError:
        return None


def create_admin_access_token(
    admin_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    must_change_password: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    claims: Dict[str, Any] = {
        "iss": JWT_ISSUER,
        "aud": ADMIN_AUDIENCE,
        "sub": str(admin_id),
        "sid": str(session_id),
        "role": "ADMIN",
        "type": "admin_access",
        "mcp": bool(must_change_password),
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(claims, _admin_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_admin_refresh_token(
    admin_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    family_id: str | uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(hours=settings.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS)
    )
    claims: Dict[str, Any] = {
        "iss": JWT_ISSUER,
        "aud": ADMIN_AUDIENCE,
        "sub": str(admin_id),
        "sid": str(session_id),
        "fid": str(family_id),
        "role": "ADMIN",
        "type": "admin_refresh",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    token = jwt.encode(claims, _admin_jwt_secret(), algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_admin_token(token: str, expected_type: str = "admin_access") -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            _admin_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=ADMIN_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        if payload.get("type") != expected_type or payload.get("role") != "ADMIN":
            return None
        return payload
    except JWTError:
        return None


# Legacy helpers kept for backward compatibility
def create_access_token(
    subject: str | Any,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: Dict[str, Any] = {"exp": expire, "sub": str(subject)}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def hash_token(raw_token: str) -> str:
    """One-way SHA-256 hash for refresh tokens and password reset tokens."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_secure_otp(length: int = 6) -> str:
    """Generate a cryptographically random numeric OTP of exact length."""
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


def hash_otp(otp_code: str, context_salt: str) -> str:
    """Compute keyed HMAC-SHA256 over the OTP and challenge context."""
    key = settings.JWT_SECRET_KEY.encode("utf-8")
    msg = f"{context_salt}:{otp_code.strip()}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_otp_hash(otp_code: str, context_salt: str, expected_hash: str) -> bool:
    computed = hash_otp(otp_code, context_salt)
    return secrets.compare_digest(computed, expected_hash)


def generate_reset_token() -> tuple[str, str]:
    """Return (raw_url_safe_token, sha256_token_hash)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_customer_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: Optional[str] = None,
) -> str:
    csrf = csrf_token or generate_csrf_token()
    response.set_cookie(
        key=CUSTOMER_ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=CUSTOMER_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
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
    return csrf


def clear_customer_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=CUSTOMER_ACCESS_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=CUSTOMER_REFRESH_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)


def set_admin_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: Optional[str] = None,
) -> str:
    csrf = csrf_token or generate_csrf_token()
    response.set_cookie(
        key=ADMIN_ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=ADMIN_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.headers[CSRF_HEADER_NAME] = csrf
    return csrf


def clear_admin_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ADMIN_ACCESS_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=ADMIN_REFRESH_COOKIE, path="/", domain=settings.COOKIE_DOMAIN)
