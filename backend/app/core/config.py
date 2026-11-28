import re
from typing import List, Optional, Union
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

POSTGRES_SCHEME_RE = re.compile(r"^(?:postgres|postgresql)://", re.IGNORECASE)
AWS_REGION_RE = re.compile(r"^[a-z]{2}(?:-[a-z]+)+-[0-9]+$")


def normalize_postgres_url(raw_url: Optional[str]) -> Optional[str]:
    """Normalize standard PostgreSQL URIs for Psycopg 3 without altering credentials or query params."""
    if raw_url is None:
        return None
    cleaned = raw_url.strip()
    if not cleaned:
        return cleaned
    if cleaned.lower().startswith("postgresql+psycopg://"):
        return f"postgresql+psycopg://{cleaned[len('postgresql+psycopg://'):]}"
    return POSTGRES_SCHEME_RE.sub("postgresql+psycopg://", cleaned, count=1)


def build_postgres_connect_args(
    database_url: str,
    *,
    db_sslmode: Optional[str] = None,
    connect_timeout: Optional[int] = None,
) -> dict[str, Union[str, int]]:
    """Build SQLAlchemy/psycopg connect_args without mutating URL query parameters."""
    connect_args: dict[str, Union[str, int]] = {}
    if connect_timeout is not None:
        connect_args["connect_timeout"] = connect_timeout
    normalized_ssl = (db_sslmode or "").strip().lower()
    if normalized_ssl:
        try:
            parsed = make_url(normalize_postgres_url(database_url) or database_url)
            has_url_ssl = "sslmode" in (parsed.query or {})
        except Exception:  # noqa: BLE001
            has_url_ssl = False
        if not has_url_ssl:
            connect_args["sslmode"] = normalized_ssl
    return connect_args


class Settings(BaseSettings):
    PROJECT_NAME: str = "DIGI-VERSE"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # Database (no default credentials: must be supplied via backend/.env or environment)
    DATABASE_URL: str
    TEST_DATABASE_URL: Optional[str] = None
    DB_SSLMODE: Optional[str] = None
    DB_CONNECT_TIMEOUT: int = 5
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # JWT Security (Customer & Admin tokens use distinct audiences and signing keys)
    JWT_SECRET_KEY: str = "change_me_in_env"
    ADMIN_JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    ADMIN_REFRESH_TOKEN_EXPIRE_HOURS: int = 12

    # Cookie & CSRF Security
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: Optional[str] = None

    # OTP, Password Reset & Lockout Policy
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_MAX_SENDS_PER_WINDOW: int = 3
    OTP_RATE_WINDOW_MINUTES: int = 10
    OTP_DELIVERY_PROVIDER: str = "development"
    ENABLE_DEV_OTP: bool = False
    WHATSAPP_OTP_ENABLED: bool = False
    WHATSAPP_TEMPLATE_NAME: str = "verification_code"
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en_US"
    WHATSAPP_REQUEST_TIMEOUT_SECONDS: float = 10.0
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Initial Administrator Provisioning (never hardcoded; password read only from env)
    INITIAL_ADMIN_USERNAME: str = "Aayan"
    INITIAL_ADMIN_EMAIL: str = "aayan@digiverse.internal"
    INITIAL_ADMIN_PASSWORD: Optional[str] = None

    # Media & Image Upload Storage ("local" | "s3" | "disabled")
    UPLOAD_DIR: str = "uploads/images"
    MAX_IMAGE_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024  # 10 MB
    IMAGE_STORAGE_BACKEND: str = "local"
    IMAGE_STORAGE_BUCKET: Optional[str] = None
    IMAGE_STORAGE_REGION: Optional[str] = None
    IMAGE_STORAGE_ENDPOINT_URL: Optional[str] = None
    IMAGE_STORAGE_ACCESS_KEY: Optional[str] = None
    IMAGE_STORAGE_SECRET_KEY: Optional[str] = None
    IMAGE_STORAGE_USE_PATH_STYLE: Optional[bool] = None
    IMAGE_STORAGE_PREFIX: str = "public-images"
    IMAGE_STORAGE_TIMEOUT_SECONDS: Optional[int] = None

    # Private Digital Asset Storage & Binary Delivery ("local" | "s3" | "disabled")
    ASSET_STORAGE_BACKEND: str = "local"
    ASSET_STORAGE_LOCAL_ROOT: str = "private_storage/assets"
    MAX_ASSET_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MB
    ASSET_DOWNLOAD_CHUNK_BYTES: int = 64 * 1024  # 64 KB
    ASSET_STORAGE_BUCKET: Optional[str] = None
    ASSET_STORAGE_REGION: str = "auto"
    ASSET_STORAGE_ENDPOINT_URL: Optional[str] = None
    ASSET_STORAGE_ACCESS_KEY: Optional[str] = None
    ASSET_STORAGE_SECRET_KEY: Optional[str] = None
    ASSET_STORAGE_USE_PATH_STYLE: bool = True
    ASSET_STORAGE_TIMEOUT_SECONDS: int = 60

    # Payment Gateway & Digital Delivery Configuration
    STORE_CURRENCY: str = "INR"
    PAYMENTS_ENABLED: bool = True
    PAYMENT_PROVIDER: str = "razorpay"  # "razorpay" | "disabled" | "mock" (mock allowed only in test/development)
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    MAX_DOWNLOADS_PER_ORDER_ITEM: int = 5
    SIGNED_DOWNLOAD_TOKEN_EXPIRE_SECONDS: int = 300  # 5 minutes

    # Marketing & Communications Providers (credentials strictly via env)
    EMAIL_ENABLED: bool = True
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "DIGI-VERSE <noreply@digiverse.internal>"
    RESEND_FROM_NAME: str = "DIGI-VERSE"
    RESEND_WEBHOOK_SECRET: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_GRAPH_API_VERSION: str = "v20.0"
    WHATSAPP_APP_SECRET: Optional[str] = None
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: Optional[str] = None

    # Persistent Campaign Worker & Webhook Configuration
    CAMPAIGN_WORKER_POLL_INTERVAL_SECONDS: int = 30
    CAMPAIGN_WORKER_BATCH_SIZE: int = 50
    CAMPAIGN_WORKER_STALE_LOCK_SECONDS: int = 300
    CAMPAIGN_MAX_RETRY_ATTEMPTS: int = 5
    CAMPAIGN_RETRY_BASE_SECONDS: int = 30
    CAMPAIGN_RETRY_MAX_BACKOFF_SECONDS: int = 1800
    CAMPAIGN_PROVIDER_TIMEOUT_SECONDS: float = 10.0
    WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: int = 300
    MAX_WEBHOOK_PAYLOAD_BYTES: int = 1024 * 1024  # 1 MB

    # Rate Limiting & Proxy Trust
    RATE_LIMIT_USE_DB: bool = True
    TRUST_PROXY_HEADERS: bool = False
    TRUST_CLOUDFLARE_HEADERS: bool = False

    # CORS & Trusted Hosts
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOWED_HOSTS: Union[List[str], str] = ["localhost", "127.0.0.1", "testserver"]

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_urls(cls, v: Optional[str]) -> Optional[str]:
        return normalize_postgres_url(v)

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_list_setting(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return (self.ENVIRONMENT or "").strip().lower() in {"production", "prod"}

    @property
    def is_staging(self) -> bool:
        return (self.ENVIRONMENT or "").strip().lower() == "staging"

    def resolve_image_s3_settings(self) -> dict[str, Union[str, bool, int]]:
        """Resolve independent public image R2/S3 settings (never inherits private asset credentials)."""
        return {
            "bucket": (self.IMAGE_STORAGE_BUCKET or "").strip(),
            "region": (self.IMAGE_STORAGE_REGION or "auto").strip() or "auto",
            "endpoint_url": (self.IMAGE_STORAGE_ENDPOINT_URL or "").strip(),
            "access_key": (self.IMAGE_STORAGE_ACCESS_KEY or "").strip(),
            "secret_key": (self.IMAGE_STORAGE_SECRET_KEY or "").strip(),
            "use_path_style": (
                self.IMAGE_STORAGE_USE_PATH_STYLE
                if self.IMAGE_STORAGE_USE_PATH_STYLE is not None
                else True
            ),
            "timeout_seconds": self.IMAGE_STORAGE_TIMEOUT_SECONDS or self.ASSET_STORAGE_TIMEOUT_SECONDS,
            "prefix": (self.IMAGE_STORAGE_PREFIX or "public-images").strip("/ "),
        }

    def get_payment_provider_state(self) -> str:
        """Return explicit payment capability state: 'disabled', 'mock', 'test', 'live', or 'misconfigured'."""
        provider = (self.PAYMENT_PROVIDER or "razorpay").strip().lower()
        if provider == "mock":
            return "mock"
        if not self.PAYMENTS_ENABLED or provider == "disabled":
            return "disabled"
        if provider != "razorpay":
            return "misconfigured"

        rzp_key = (self.RAZORPAY_KEY_ID or "").strip()
        rzp_secret = (self.RAZORPAY_KEY_SECRET or "").strip()
        rzp_wh = (self.RAZORPAY_WEBHOOK_SECRET or "").strip()
        if (
            not rzp_key
            or rzp_key == "your_razorpay_key_id_placeholder"
            or not rzp_secret
            or rzp_secret == "your_razorpay_key_secret_placeholder"
        ):
            return "misconfigured"
        if rzp_key.startswith("rzp_test_"):
            return "test"
        if rzp_key.startswith("rzp_live_"):
            if not rzp_wh or rzp_wh == "your_razorpay_webhook_secret_placeholder":
                return "misconfigured"
            return "live"
        return "misconfigured"

    def get_email_provider_state(self) -> str:
        """Return email capability state: 'disabled', 'development', 'live', or 'misconfigured'."""
        if not self.EMAIL_ENABLED:
            return "disabled"
        key = (self.RESEND_API_KEY or "").strip()
        if not self.is_production and key in {"", "your_resend_api_key_placeholder"}:
            return "development"
        resend_from = (self.RESEND_FROM_EMAIL or "").strip()
        resend_wh = (self.RESEND_WEBHOOK_SECRET or "").strip()
        if (
            not key
            or key == "your_resend_api_key_placeholder"
            or not resend_from
            or "@" not in resend_from
            or "digiverse.internal" in resend_from.lower()
            or "your-domain.example.com" in resend_from.lower()
            or not resend_wh
            or resend_wh == "whsec_your_resend_webhook_secret_placeholder"
            or not resend_wh.startswith("whsec_")
        ):
            return "misconfigured"
        return "live"

    def get_whatsapp_provider_state(self) -> str:
        """Return WhatsApp OTP state: 'disabled', 'development', 'live', or 'misconfigured'."""
        otp_provider = (self.OTP_DELIVERY_PROVIDER or "development").strip().lower()
        if otp_provider == "disabled" and not self.WHATSAPP_OTP_ENABLED:
            return "disabled"
        if not self.is_production and otp_provider == "development":
            return "development"
        if otp_provider != "whatsapp" or not self.WHATSAPP_OTP_ENABLED:
            return "misconfigured"
        wa_placeholders = {
            "",
            "your_whatsapp_cloud_api_token_placeholder",
            "your_whatsapp_phone_number_id_placeholder",
        }
        token = (self.WHATSAPP_ACCESS_TOKEN or "").strip()
        phone_id = (self.WHATSAPP_PHONE_NUMBER_ID or "").strip()
        tpl = (self.WHATSAPP_TEMPLATE_NAME or "").strip()
        graph_ver = (self.WHATSAPP_GRAPH_API_VERSION or "").strip()
        if (
            token in wa_placeholders
            or phone_id in wa_placeholders
            or not tpl
            or tpl.startswith("your_")
            or not re.match(r"^v[0-9]+\.[0-9]+$", graph_ver)
        ):
            return "misconfigured"
        return "live"

    def get_asset_storage_state(self) -> str:
        backend = (self.ASSET_STORAGE_BACKEND or "local").strip().lower()
        if backend in {"local", "disabled"}:
            return backend
        if backend == "s3":
            if self._validate_s3_config_issues(
                prefix="ASSET_STORAGE",
                bucket=self.ASSET_STORAGE_BUCKET,
                access_key=self.ASSET_STORAGE_ACCESS_KEY,
                secret_key=self.ASSET_STORAGE_SECRET_KEY,
                endpoint_url=self.ASSET_STORAGE_ENDPOINT_URL,
                region=self.ASSET_STORAGE_REGION,
                require_https_endpoint=self.is_production,
                require_strict_endpoint=True,
            ):
                return "misconfigured"
            return "s3"
        return "misconfigured"

    def get_image_storage_state(self) -> str:
        backend = (self.IMAGE_STORAGE_BACKEND or "local").strip().lower()
        if backend in {"local", "disabled"}:
            return backend
        if backend == "s3":
            cfg = self.resolve_image_s3_settings()
            if self._validate_s3_config_issues(
                prefix="IMAGE_STORAGE",
                bucket=str(cfg["bucket"]),
                access_key=str(cfg["access_key"]),
                secret_key=str(cfg["secret_key"]),
                endpoint_url=str(cfg["endpoint_url"]),
                region=str(cfg["region"]),
                require_https_endpoint=self.is_production,
                require_strict_endpoint=True,
            ):
                return "misconfigured"
            return "s3"
        return "misconfigured"

    @staticmethod
    def _validate_s3_config_issues(
        *,
        prefix: str,
        bucket: Optional[str],
        access_key: Optional[str],
        secret_key: Optional[str],
        endpoint_url: Optional[str],
        region: Optional[str],
        require_https_endpoint: bool,
        require_strict_endpoint: bool = False,
    ) -> list[str]:
        issues: list[str] = []
        bucket_val = (bucket or "").strip()
        ak_val = (access_key or "").strip()
        sk_val = (secret_key or "").strip()
        ep_val = (endpoint_url or "").strip()
        reg_val = (region or "").strip()

        placeholder_buckets = {"your_private_asset_bucket_name", "your_public_image_bucket_name"}
        if not bucket_val:
            issues.append(f"{prefix}_BUCKET must be configured when using s3 storage.")
        elif bucket_val in placeholder_buckets:
            issues.append(f"{prefix}_BUCKET cannot use a placeholder value in production.")

        if not ak_val:
            issues.append(f"{prefix}_ACCESS_KEY must be configured when using s3 storage.")
        elif ak_val == "your_s3_access_key_placeholder":
            issues.append(f"{prefix}_ACCESS_KEY cannot use a placeholder value in production.")

        if not sk_val:
            issues.append(f"{prefix}_SECRET_KEY must be configured when using s3 storage.")
        elif sk_val == "your_s3_secret_key_placeholder":
            issues.append(f"{prefix}_SECRET_KEY cannot use a placeholder value in production.")

        if ep_val:
            if ep_val == "https://your-s3-compatible-endpoint.example.com":
                issues.append(f"{prefix}_ENDPOINT_URL cannot use a placeholder value in production.")
            else:
                parsed_ep = urlparse(ep_val)
                ep_host = (parsed_ep.hostname or "").strip().lower()
                has_spaces = any(ch.isspace() for ch in ep_val)
                if has_spaces or not parsed_ep.netloc or not ep_host or parsed_ep.scheme not in {"http", "https"}:
                    issues.append(f"{prefix}_ENDPOINT_URL must be a valid HTTP(S) URL.")
                elif require_https_endpoint:
                    if parsed_ep.scheme != "https":
                        issues.append(f"{prefix}_ENDPOINT_URL must use HTTPS in production.")
                    elif (
                        ep_host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
                        or ep_host.endswith(".local")
                        or ep_host.endswith(".localhost")
                    ):
                        issues.append(f"{prefix}_ENDPOINT_URL cannot reference localhost or loopback addresses in production.")
        elif require_strict_endpoint:
            if not reg_val or reg_val.lower() == "auto":
                issues.append(
                    f"{prefix}_ENDPOINT_URL must be configured with a valid HTTPS URL when {prefix}_REGION is 'auto' (Cloudflare R2)."
                )
            elif not AWS_REGION_RE.match(reg_val.lower()):
                issues.append(
                    f"{prefix}_ENDPOINT_URL must be configured or {prefix}_REGION must be a valid AWS region (e.g. 'ap-south-1')."
                )
        elif not reg_val:
            issues.append(f"{prefix}_ENDPOINT_URL or {prefix}_REGION must be set for s3 storage.")
        return issues

    def _validate_deployed_common(self, env_label: str) -> list[str]:
        issues: list[str] = []
        if self.DEBUG:
            issues.append(f"DEBUG must be False in {env_label}.")
        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "change_me_in_env" or len(self.JWT_SECRET_KEY) < 32:
            issues.append(f"JWT_SECRET_KEY must be a strong secret of at least 32 characters in {env_label}.")
        if not self.ADMIN_JWT_SECRET_KEY or len(self.ADMIN_JWT_SECRET_KEY) < 32:
            issues.append(f"ADMIN_JWT_SECRET_KEY must be configured separately in {env_label}.")
        elif self.ADMIN_JWT_SECRET_KEY == self.JWT_SECRET_KEY:
            issues.append(f"ADMIN_JWT_SECRET_KEY must be distinct from JWT_SECRET_KEY in {env_label}.")
        if not self.COOKIE_SECURE:
            issues.append(f"COOKIE_SECURE must be True in {env_label}.")
        if (self.PAYMENT_PROVIDER or "").strip().lower() == "mock":
            issues.append(f"PAYMENT_PROVIDER cannot be 'mock' in {env_label}.")
        if "*" in self.CORS_ORIGINS:
            issues.append(f"CORS_ORIGINS cannot contain wildcard '*' in {env_label}.")
        if "*" in self.ALLOWED_HOSTS:
            issues.append(f"ALLOWED_HOSTS cannot contain wildcard '*' in {env_label}.")
        if not self.RATE_LIMIT_USE_DB:
            issues.append(f"RATE_LIMIT_USE_DB must be True in {env_label}.")
        storage_backend = (self.ASSET_STORAGE_BACKEND or "").strip().lower()
        if storage_backend not in {"local", "s3", "disabled"}:
            issues.append("ASSET_STORAGE_BACKEND must be 'local', 's3', or 'disabled'.")
        if storage_backend == "s3":
            issues.extend(
                self._validate_s3_config_issues(
                    prefix="ASSET_STORAGE",
                    bucket=self.ASSET_STORAGE_BUCKET,
                    access_key=self.ASSET_STORAGE_ACCESS_KEY,
                    secret_key=self.ASSET_STORAGE_SECRET_KEY,
                    endpoint_url=self.ASSET_STORAGE_ENDPOINT_URL,
                    region=self.ASSET_STORAGE_REGION,
                    require_https_endpoint=env_label == "production",
                    require_strict_endpoint=env_label == "production",
                )
            )
        image_backend = (self.IMAGE_STORAGE_BACKEND or "local").strip().lower()
        if image_backend not in {"local", "s3", "disabled"}:
            issues.append("IMAGE_STORAGE_BACKEND must be 'local', 's3', or 'disabled'.")
        if image_backend == "s3":
            img_cfg = self.resolve_image_s3_settings()
            issues.extend(
                self._validate_s3_config_issues(
                    prefix="IMAGE_STORAGE",
                    bucket=str(img_cfg["bucket"]),
                    access_key=str(img_cfg["access_key"]),
                    secret_key=str(img_cfg["secret_key"]),
                    endpoint_url=str(img_cfg["endpoint_url"]),
                    region=str(img_cfg["region"]),
                    require_https_endpoint=env_label == "production",
                    require_strict_endpoint=env_label == "production",
                )
            )
            if (
                img_cfg["bucket"]
                and (self.ASSET_STORAGE_BUCKET or "").strip()
                and str(img_cfg["bucket"]) == (self.ASSET_STORAGE_BUCKET or "").strip()
            ):
                issues.append("IMAGE_STORAGE_BUCKET must be separate from ASSET_STORAGE_BUCKET.")
        return issues

    def validate_production_readiness(self) -> list[str]:
        """Return a list of configuration violations when running in production."""
        if not self.is_production:
            return []
        issues = self._validate_deployed_common("production")

        # 1. Production database must not point to localhost and must require TLS
        try:
            db_url = make_url(self.DATABASE_URL)
        except Exception:  # noqa: BLE001
            issues.append("DATABASE_URL is invalid in production.")
            db_url = None
        if db_url is not None:
            db_host = (db_url.host or "").strip().lower()
            if (
                not db_host
                or db_host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
                or db_host.endswith(".local")
            ):
                issues.append("DATABASE_URL cannot reference localhost or loopback addresses in production.")
            sslmode = str(
                (db_url.query or {}).get("sslmode") or self.DB_SSLMODE or ""
            ).strip().lower()
            if sslmode not in {"require", "verify-ca", "verify-full"}:
                issues.append(
                    "DATABASE_URL must require TLS (sslmode=require, verify-ca, or verify-full) in production."
                )

        # 2. HTTPS-only CORS origins & explicit TrustedHost ALLOWED_HOSTS
        if not self.CORS_ORIGINS:
            issues.append("CORS_ORIGINS must include at least one HTTPS origin in production.")
        else:
            for origin in self.CORS_ORIGINS:
                if origin == "*":
                    continue  # Already flagged by _validate_deployed_common
                parsed_origin = urlparse(origin)
                origin_host = (parsed_origin.hostname or "").strip().lower()
                if parsed_origin.scheme != "https" or not origin_host:
                    issues.append("CORS_ORIGINS in production must use valid HTTPS URLs.")
                    break
                if (
                    origin_host in {"localhost", "127.0.0.1", "::1"}
                    or origin_host.endswith(".localhost")
                    or origin_host.endswith(".local")
                    or "localhost" in origin.lower()
                    or "127.0.0.1" in origin
                ):
                    issues.append("CORS_ORIGINS in production cannot reference localhost or loopback addresses.")
                    break
        if not self.ALLOWED_HOSTS:
            issues.append("ALLOWED_HOSTS must include the production backend hostname(s) in production.")

        # 3. Reverse-proxy header trust
        if not self.TRUST_PROXY_HEADERS:
            issues.append("TRUST_PROXY_HEADERS must be True in production.")

        # 4. Object storage policy: never silently allow local ephemeral disk in production
        asset_backend = (self.ASSET_STORAGE_BACKEND or "").strip().lower()
        if asset_backend == "local":
            issues.append(
                "ASSET_STORAGE_BACKEND cannot be 'local' in production (set 's3' or explicitly 'disabled')."
            )
        image_backend = (self.IMAGE_STORAGE_BACKEND or "local").strip().lower()
        if image_backend == "local":
            issues.append(
                "IMAGE_STORAGE_BACKEND cannot be 'local' in production (set 's3' or explicitly 'disabled')."
            )

        # 5. Payment capability policy: never allow mock or test-as-live; allow explicit disabled mode
        payment_provider = (self.PAYMENT_PROVIDER or "").strip().lower()
        if not self.PAYMENTS_ENABLED or payment_provider == "disabled":
            pass  # Live checkout and refunds intentionally disabled; payment endpoints fail closed (503).
        elif payment_provider != "razorpay":
            if payment_provider != "mock":  # 'mock' already flagged by _validate_deployed_common
                issues.append("PAYMENT_PROVIDER must be 'razorpay' or 'disabled' in production.")
        else:
            rzp_key = (self.RAZORPAY_KEY_ID or "").strip()
            rzp_secret = (self.RAZORPAY_KEY_SECRET or "").strip()
            rzp_wh = (self.RAZORPAY_WEBHOOK_SECRET or "").strip()
            if not rzp_key or rzp_key == "your_razorpay_key_id_placeholder" or not rzp_key.startswith("rzp_live_"):
                issues.append(
                    "RAZORPAY_KEY_ID must be a live Razorpay key ('rzp_live_...') in production "
                    "(test credentials cannot enable live checkout)."
                )
            if not rzp_secret or rzp_secret == "your_razorpay_key_secret_placeholder":
                issues.append("RAZORPAY_KEY_SECRET must be configured in production.")
            if not rzp_wh or rzp_wh == "your_razorpay_webhook_secret_placeholder":
                issues.append("RAZORPAY_WEBHOOK_SECRET must be configured in production.")

        # 6. Optional OTP & WhatsApp configuration (must never enable dev OTP; 'disabled' is explicit)
        if self.ENABLE_DEV_OTP:
            issues.append("ENABLE_DEV_OTP must be False in production.")
        otp_provider = (self.OTP_DELIVERY_PROVIDER or "").strip().lower()
        if otp_provider not in {"whatsapp", "disabled"}:
            issues.append("OTP_DELIVERY_PROVIDER must be 'whatsapp' or 'disabled' in production.")
        if otp_provider == "disabled":
            if self.WHATSAPP_OTP_ENABLED:
                issues.append("WHATSAPP_OTP_ENABLED must be False when OTP_DELIVERY_PROVIDER is 'disabled' in production.")
        elif not self.WHATSAPP_OTP_ENABLED:
            issues.append(
                "WHATSAPP_OTP_ENABLED must be True in production when OTP_DELIVERY_PROVIDER is not 'disabled'."
            )

        wa_placeholders = {
            "",
            "your_whatsapp_cloud_api_token_placeholder",
            "your_whatsapp_phone_number_id_placeholder",
            "your_meta_app_secret_placeholder",
            "your_whatsapp_webhook_verify_token_placeholder",
        }
        wa_app_secret = (self.WHATSAPP_APP_SECRET or "").strip()
        wa_verify_token = (self.WHATSAPP_WEBHOOK_VERIFY_TOKEN or "").strip()
        wa_webhook_partially_set = bool(wa_app_secret or wa_verify_token)
        wa_enabled = bool(self.WHATSAPP_OTP_ENABLED or otp_provider == "whatsapp" or wa_webhook_partially_set)
        if wa_enabled:
            token = (self.WHATSAPP_ACCESS_TOKEN or "").strip()
            if token in wa_placeholders:
                issues.append("WHATSAPP_ACCESS_TOKEN must be configured when WhatsApp is enabled in production.")
            phone_id = (self.WHATSAPP_PHONE_NUMBER_ID or "").strip()
            if phone_id in wa_placeholders:
                issues.append("WHATSAPP_PHONE_NUMBER_ID must be configured when WhatsApp is enabled in production.")
            tpl_name = (self.WHATSAPP_TEMPLATE_NAME or "").strip()
            if not tpl_name or tpl_name.startswith("your_"):
                issues.append("WHATSAPP_TEMPLATE_NAME must be configured when WhatsApp is enabled in production.")
            graph_ver = (self.WHATSAPP_GRAPH_API_VERSION or "").strip()
            if not re.match(r"^v[0-9]+\.[0-9]+$", graph_ver):
                issues.append("WHATSAPP_GRAPH_API_VERSION must follow 'v<major>.<minor>' format in production.")
            if wa_webhook_partially_set:
                if wa_app_secret in wa_placeholders:
                    issues.append("WHATSAPP_APP_SECRET must be configured when WhatsApp webhooks are configured.")
                if wa_verify_token in wa_placeholders:
                    issues.append(
                        "WHATSAPP_WEBHOOK_VERIFY_TOKEN must be configured when WhatsApp webhooks are configured."
                    )

        # 7. Optional Resend email configuration (explicit EMAIL_ENABLED=False allows startup safely)
        if self.EMAIL_ENABLED:
            resend_key = (self.RESEND_API_KEY or "").strip()
            resend_from = (self.RESEND_FROM_EMAIL or "").strip()
            resend_wh = (self.RESEND_WEBHOOK_SECRET or "").strip()
            if not resend_key or resend_key == "your_resend_api_key_placeholder":
                issues.append("RESEND_API_KEY must be configured in production.")
            if (
                not resend_from
                or "@" not in resend_from
                or "digiverse.internal" in resend_from.lower()
                or "your-domain.example.com" in resend_from.lower()
            ):
                issues.append("RESEND_FROM_EMAIL must use a verified non-internal domain in production.")
            if resend_wh == "whsec_your_resend_webhook_secret_placeholder":
                issues.append("RESEND_WEBHOOK_SECRET cannot use a placeholder value in production.")
            elif resend_wh and not resend_wh.startswith("whsec_"):
                issues.append("RESEND_WEBHOOK_SECRET must be a valid Svix secret starting with 'whsec_'.")
            elif resend_key and resend_key != "your_resend_api_key_placeholder" and not resend_wh:
                issues.append("RESEND_WEBHOOK_SECRET must be configured when Resend email delivery is enabled in production.")

        return issues

    def validate_staging_readiness(self) -> list[str]:
        """Return staging-specific configuration violations (TLS, test-mode gateways, private S3)."""
        if not self.is_staging:
            return ["ENVIRONMENT must be set to 'staging'."]
        issues = self._validate_deployed_common("staging")
        if (self.ASSET_STORAGE_BACKEND or "").strip().lower() != "s3":
            issues.append("ASSET_STORAGE_BACKEND should be 's3' (private bucket) for staging.")
        rzp_key = (self.RAZORPAY_KEY_ID or "").strip()
        if not rzp_key.startswith("rzp_test_"):
            issues.append("RAZORPAY_KEY_ID in staging must use a Razorpay test-mode key ('rzp_test_...'), never live keys.")
        for origin in self.CORS_ORIGINS:
            if "localhost" in origin or "127.0.0.1" in origin:
                issues.append(f"CORS_ORIGINS in staging must not reference localhost/127.0.0.1 ({origin}).")
            elif not origin.startswith("https://"):
                issues.append(f"CORS_ORIGINS in staging must use HTTPS ({origin}).")
        if self.ENABLE_DEV_OTP:
            issues.append("ENABLE_DEV_OTP must be False outside development.")
        if self.WHATSAPP_OTP_ENABLED:
            token = (self.WHATSAPP_ACCESS_TOKEN or "").strip()
            if not token or token == "your_whatsapp_cloud_api_token_placeholder":
                issues.append("WHATSAPP_ACCESS_TOKEN must be configured when WhatsApp OTP is enabled.")
            phone_id = (self.WHATSAPP_PHONE_NUMBER_ID or "").strip()
            if not phone_id or phone_id == "your_whatsapp_phone_number_id_placeholder":
                issues.append("WHATSAPP_PHONE_NUMBER_ID must be configured when WhatsApp OTP is enabled.")
            if not (self.WHATSAPP_TEMPLATE_NAME or "").strip():
                issues.append("WHATSAPP_TEMPLATE_NAME must be configured when WhatsApp OTP is enabled.")
        return issues

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
