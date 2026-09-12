"""Application configuration (pydantic-settings). Secrets are never committed."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_debug: bool = True
    project_name: str = "Black House Commerce API"
    api_v1_str: str = "/api/v1"
    secret_key: str = "dev-only-insecure-secret"
    database_url: str = "sqlite:///./blackhouse.db"
    redis_url: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Auth
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    # Payments
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = "whsec_dev"

    # Notifications
    email_provider: str = "log"
    email_api_key: str = ""
    email_from: str = "orders@blackhouse.example"
    sms_provider: str = ""
    sms_api_key: str = ""
    whatsapp_provider: str = ""
    whatsapp_api_key: str = ""
    whatsapp_business_number: str = "910000000000"

    # Storage
    storage_provider: Literal["local", "s3", "cloudinary"] = "local"
    storage_bucket: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = ""
    storage_local_path: str = "./storage/uploads"

    # Geography / commerce defaults
    warehouse_city: str = "Bhopal"
    warehouse_state: str = "Madhya Pradesh"
    warehouse_country: str = "IN"
    default_currency: str = "INR"

    # Business rules (overridable at runtime via BusinessSetting)
    reservation_ttl_minutes: int = 30
    payment_retry_cooldown_seconds: int = 120
    return_window_days: int = 7
    low_stock_threshold: int = 3
    free_shipping_threshold_paise: int | None = None
    default_shipping_charge_paise: int = 9900
    pincode_mode: Literal["allowlist", "denylist"] = "denylist"
    staff_can_cancel_before_packing: bool = True
    order_number_prefix: str = "BH"
    rate_limit_per_minute: int = 30

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
