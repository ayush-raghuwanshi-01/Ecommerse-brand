"""Application configuration (pydantic-settings). Secrets are never committed.

Every value can be supplied by environment variable or by a `.env` file in the
backend directory (see `.env.example`). Environment variables win over `.env`.

Two configuration layers exist on purpose:

* **Deploy-time (this module)** — infrastructure and credentials: database URL,
  Redis, JWT secret, payment gateway keys, storage backend, CORS.
* **Run-time (`services/settings_service.py` + `business_settings` table)** —
  commercial policy an operator can change without a redeploy: return window,
  free-shipping threshold, low-stock threshold, PIN-code mode, order prefix.

The values below are the *defaults* that run-time settings are seeded from.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholders that must never reach a non-development environment.
_INSECURE_SECRETS = {
    "dev-only-insecure-secret",
    "change-me-to-a-long-random-string",
    "",
    "secret",
    "changeme",
}
_INSECURE_WEBHOOK_SECRETS = {"whsec_dev", "", "changeme"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_debug: bool = True
    project_name: str = "Black House Commerce API"
    api_v1_str: str = "/api/v1"
    secret_key: str = "dev-only-insecure-secret"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # `json` for platform log aggregation (one parseable line per event);
    # `text` for human-readable local development.
    log_format: Literal["json", "text"] = "text"
    # Optional. When set, unhandled exceptions and error-level logs are reported.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    # Run the reservation sweep inside the API process. True is convenient for
    # single-container and local development; set false in production once the
    # standalone worker (scripts/worker.py) is deployed, so web traffic and
    # background work do not compete for the same pool.
    run_inline_sweep: bool = True

    # Public origin of this API and of the storefront, used to build absolute
    # links (webhook callbacks, wa.me messages, email deep links).
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # ── Database ────────────────────────────────────────────────────────────
    # PostgreSQL in every deployed environment; SQLite is a dev/test mirror.
    #   postgresql+psycopg://user:password@host:5432/dbname
    #   sqlite:///./blackhouse.db
    database_url: str = "sqlite:///./blackhouse.db"
    database_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800

    # Optional. Used only for rate limiting / shared ephemeral state when set;
    # the app falls back to an in-process limiter otherwise.
    redis_url: str | None = None

    # ── CORS ────────────────────────────────────────────────────────────────
    # Accepts a JSON list (["https://a.com","https://b.com"]) or a plain
    # comma-separated list. Wildcards are rejected in production because the app
    # sends credentials.
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ── Auth ────────────────────────────────────────────────────────────────
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    # ── Payments (Razorpay) ─────────────────────────────────────────────────
    # Leave the keys empty to run the built-in mock gateway (dev/test only).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = "whsec_dev"

    # ── Notifications ───────────────────────────────────────────────────────
    # Provider registry: "log" records + logs only. Wire a real provider in
    # services/notification_service.py and set the matching *_PROVIDER value.
    email_provider: str = "log"
    email_api_key: str = ""
    email_from: str = "orders@blackhouse.example"
    # Where replies land. Defaults to email_from; set this to a monitored inbox
    # (support@…) so customer replies reach a human rather than a no-reply alias.
    email_reply_to: str = ""
    sms_provider: str = ""
    sms_api_key: str = ""
    whatsapp_provider: str = ""
    whatsapp_api_key: str = ""
    whatsapp_business_number: str = "910000000000"

    # ── Object storage ──────────────────────────────────────────────────────
    storage_provider: Literal["local", "s3", "cloudinary"] = "local"
    storage_bucket: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = ""
    storage_local_path: str = "./storage/uploads"
    # Public prefix for locally stored uploads (mounted at /static/uploads).
    storage_public_base_url: str = "/static/uploads"
    # Cloudinary: either the individual fields or a single CLOUDINARY_URL of the
    # form cloudinary://<key>:<secret>@<cloud_name>
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_url: str = ""
    # S3/CDN: public base URL prepended to object keys (CloudFront, Spaces CDN…).
    storage_cdn_base_url: str = ""
    # Custom S3 endpoint for non-AWS stores (DigitalOcean Spaces, Wasabi, MinIO).
    # Leave empty for AWS S3 itself.
    storage_endpoint_url: str = ""
    # Image delivery: JPEG/PNG/WebP/AVIF are accepted; SVG/HTML are rejected
    # outright because they can carry script (see app/core/uploads.py).
    image_max_upload_bytes: int = 8 * 1024 * 1024
    image_quality: int = 80
    # Minimum edge length accepted for a *primary* product image. Undersized
    # artwork is warned about rather than rejected, so it never blocks an upload.
    image_min_width: int = 800

    @field_validator("cloudinary_url", mode="before")
    @classmethod
    def _empty_cloudinary_url(cls, v):
        return (v or "").strip()

    # ── Geography / commerce defaults ───────────────────────────────────────
    warehouse_city: str = "Bhopal"
    warehouse_state: str = "Madhya Pradesh"
    warehouse_country: str = "IN"
    default_currency: str = "INR"

    # ── Business rules (seed values; overridable at runtime via BusinessSetting)
    reservation_ttl_minutes: int = 30
    payment_retry_cooldown_seconds: int = 120
    return_window_days: int = 7
    low_stock_threshold: int = 3
    free_shipping_threshold_paise: int | None = None
    default_shipping_charge_paise: int = 9900
    pincode_mode: Literal["allowlist", "denylist"] = "denylist"
    staff_can_cancel_before_packing: bool = True
    order_number_prefix: str = "BH"

    # ── Rate limiting ───────────────────────────────────────────────────────
    # Two tiers. `rate_limit_per_minute` is the strict, opt-in limit applied by
    # the `rate_limit()` dependency to abuse-prone endpoints (login, register,
    # password reset). `rate_limit_default_per_minute` is the blanket limit the
    # middleware applies to every other /api/ route, so a new endpoint is
    # protected by default instead of only if someone remembers the decorator.
    rate_limit_per_minute: int = 30
    rate_limit_default_per_minute: int = 120
    rate_limit_enabled: bool = True

    # ── Proxy trust ─────────────────────────────────────────────────────────
    # See app/core/net.py. Must stay True on a PaaS (the TCP peer is the
    # platform proxy); set False if the container is exposed directly, or the
    # X-Forwarded-For header becomes a rate-limit bypass.
    trust_proxy_headers: bool = True

    # ── Metrics ─────────────────────────────────────────────────────────────
    # /metrics leaks traffic shape and internal route names, so it is gated.
    # METRICS_TOKEN, when set, requires `Authorization: Bearer <token>`; a
    # scraper on the same private network can then be authorised without
    # exposing the endpoint to the public internet.
    metrics_enabled: bool = True
    metrics_token: str = ""

    # ── Normalisers ─────────────────────────────────────────────────────────
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        """Accept a JSON array or a comma-separated string."""
        if isinstance(v, str):
            import json

            text = v.strip()
            if not text:
                return []
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return [o.strip().rstrip("/") for o in text.split(",") if o.strip()]
        return v

    @field_validator("api_base_url", "frontend_url", "storage_public_base_url", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/") if v.startswith("http") or v.startswith("/") else v

    # ── Derived flags ───────────────────────────────────────────────────────
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def razorpay_enabled(self) -> bool:
        """True when a real gateway is configured; otherwise the mock runs."""
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    # ── Fail-fast guards ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        """Refuse to boot a production instance with development-grade config.

        These are deliberately loud: a mis-set SECRET_KEY silently invalidates
        every issued token and, worse, lets an attacker forge them.
        """
        if self.app_env in {"production", "staging"}:
            problems: list[str] = []

            if self.secret_key.strip().lower() in _INSECURE_SECRETS or len(self.secret_key) < 32:
                problems.append(
                    "SECRET_KEY is missing or too short — generate one with "
                    '`python -c "import secrets; print(secrets.token_urlsafe(48))"`'
                )
            if self.is_sqlite:
                problems.append("DATABASE_URL points at SQLite; use PostgreSQL in deployed environments")
            if self.app_debug:
                problems.append("APP_DEBUG must be false outside development")
            if "*" in self.cors_origins or not self.cors_origins:
                problems.append("CORS_ORIGINS must list explicit origins (credentials are sent)")
            if self.razorpay_webhook_secret.strip().lower() in _INSECURE_WEBHOOK_SECRETS:
                problems.append("RAZORPAY_WEBHOOK_SECRET is unset — webhooks cannot be trusted")
            if self.storage_provider == "local":
                problems.append(
                    "STORAGE_PROVIDER=local is not durable across container restarts; use s3/cloudinary"
                )

            if problems:
                raise ValueError(
                    f"Unsafe configuration for APP_ENV={self.app_env}:\n  - " + "\n  - ".join(problems)
                )

        if (
            self.razorpay_enabled
            and self.razorpay_webhook_secret.strip().lower() in _INSECURE_WEBHOOK_SECRETS
        ):
            raise ValueError(
                "RAZORPAY_WEBHOOK_SECRET must be set when Razorpay keys are configured, "
                "otherwise gateway callbacks cannot be signature-verified."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — import `settings` for normal use, call this in tests."""
    return Settings()


settings = get_settings()
