from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        return self._validate_deployed_common("production")

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
        return issues

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
