import re
from typing import List, Optional, Union
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    PROJECT_NAME: str = "DIGI-VERSE"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # Database (no default credentials: must be supplied via backend/.env or environment)
    DATABASE_URL: str
    TEST_DATABASE_URL: Optional[str] = None
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

    # Media & Image Upload Storage
    UPLOAD_DIR: str = "uploads/images"
    MAX_IMAGE_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Private Digital Asset Storage & Binary Delivery
    ASSET_STORAGE_BACKEND: str = "local"  # "local" | "s3"
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
    PAYMENT_PROVIDER: str = "razorpay"  # "razorpay" | "mock" (mock allowed only in test/development)
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    MAX_DOWNLOADS_PER_ORDER_ITEM: int = 5
    SIGNED_DOWNLOAD_TOKEN_EXPIRE_SECONDS: int = 300  # 5 minutes

    # Marketing & Communications Providers (credentials strictly via env)
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

    # CORS & Trusted Hosts
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOWED_HOSTS: Union[List[str], str] = ["localhost", "127.0.0.1", "testserver"]

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
        if storage_backend not in {"local", "s3"}:
            issues.append("ASSET_STORAGE_BACKEND must be 'local' or 's3'.")
        if storage_backend == "s3":
            if not (self.ASSET_STORAGE_BUCKET or "").strip():
                issues.append("ASSET_STORAGE_BUCKET must be configured when using s3 storage.")
            if not (self.ASSET_STORAGE_ACCESS_KEY or "").strip():
                issues.append("ASSET_STORAGE_ACCESS_KEY must be configured when using s3 storage.")
            if not (self.ASSET_STORAGE_SECRET_KEY or "").strip():
                issues.append("ASSET_STORAGE_SECRET_KEY must be configured when using s3 storage.")
            if not (self.ASSET_STORAGE_ENDPOINT_URL or "").strip() and not (self.ASSET_STORAGE_REGION or "").strip():
                issues.append("ASSET_STORAGE_ENDPOINT_URL or ASSET_STORAGE_REGION must be set for s3 storage.")
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
            sslmode = str((db_url.query or {}).get("sslmode", "")).strip().lower()
            if sslmode not in {"require", "verify-ca", "verify-full"}:
                issues.append(
                    "DATABASE_URL must require TLS (sslmode=require, verify-ca, or verify-full) in production."
                )

        # 2. HTTPS-only CORS origins; reject localhost/loopback
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

        # 3. Reverse-proxy header trust
        if not self.TRUST_PROXY_HEADERS:
            issues.append("TRUST_PROXY_HEADERS must be True in production.")

        # 4. Private S3-compatible object storage (no local ephemeral disk, no placeholders)
        if (self.ASSET_STORAGE_BACKEND or "").strip().lower() != "s3":
            issues.append("ASSET_STORAGE_BACKEND must be 's3' in production.")
        else:
            if (self.ASSET_STORAGE_BUCKET or "").strip() == "your_private_asset_bucket_name":
                issues.append("ASSET_STORAGE_BUCKET cannot use a placeholder value in production.")
            if (self.ASSET_STORAGE_ACCESS_KEY or "").strip() == "your_s3_access_key_placeholder":
                issues.append("ASSET_STORAGE_ACCESS_KEY cannot use a placeholder value in production.")
            if (self.ASSET_STORAGE_SECRET_KEY or "").strip() == "your_s3_secret_key_placeholder":
                issues.append("ASSET_STORAGE_SECRET_KEY cannot use a placeholder value in production.")
            s3_endpoint = (self.ASSET_STORAGE_ENDPOINT_URL or "").strip()
            if s3_endpoint == "https://your-s3-compatible-endpoint.example.com":
                issues.append("ASSET_STORAGE_ENDPOINT_URL cannot use a placeholder value in production.")
            elif s3_endpoint and not s3_endpoint.startswith("https://"):
                issues.append("ASSET_STORAGE_ENDPOINT_URL must use HTTPS in production.")

        # 5. Razorpay live credentials and webhook secret
        payment_provider = (self.PAYMENT_PROVIDER or "").strip().lower()
        if payment_provider != "razorpay":
            if payment_provider != "mock":  # 'mock' already flagged by _validate_deployed_common
                issues.append("PAYMENT_PROVIDER must be 'razorpay' in production.")
        else:
            rzp_key = (self.RAZORPAY_KEY_ID or "").strip()
            rzp_secret = (self.RAZORPAY_KEY_SECRET or "").strip()
            rzp_wh = (self.RAZORPAY_WEBHOOK_SECRET or "").strip()
            if not rzp_key or rzp_key == "your_razorpay_key_id_placeholder" or not rzp_key.startswith("rzp_live_"):
                issues.append("RAZORPAY_KEY_ID must be a live Razorpay key ('rzp_live_...') in production.")
            if not rzp_secret or rzp_secret == "your_razorpay_key_secret_placeholder":
                issues.append("RAZORPAY_KEY_SECRET must be configured in production.")
            if not rzp_wh or rzp_wh == "your_razorpay_webhook_secret_placeholder":
                issues.append("RAZORPAY_WEBHOOK_SECRET must be configured in production.")

        # 6. OTP & WhatsApp configuration consistency
        if self.ENABLE_DEV_OTP:
            issues.append("ENABLE_DEV_OTP must be False in production.")
        otp_provider = (self.OTP_DELIVERY_PROVIDER or "").strip().lower()
        if otp_provider != "whatsapp":
            issues.append("OTP_DELIVERY_PROVIDER must be 'whatsapp' in production.")
        if not self.WHATSAPP_OTP_ENABLED:
            issues.append("WHATSAPP_OTP_ENABLED must be True in production.")

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

        # 7. Resend production email and webhook configuration
        # ProductionEmailProvider is unconditionally active in production for password resets & order emails.
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
