"""Runtime business settings backed by the business_settings table,
falling back to env-configured defaults."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models.commerce import BusinessSetting

DEFAULTS: dict[str, Any] = {
    "reservation_ttl_minutes": env_settings.reservation_ttl_minutes,
    "payment_retry_cooldown_seconds": env_settings.payment_retry_cooldown_seconds,
    "return_window_days": env_settings.return_window_days,
    "low_stock_threshold": env_settings.low_stock_threshold,
    "free_shipping_threshold_paise": env_settings.free_shipping_threshold_paise,
    "default_shipping_charge_paise": env_settings.default_shipping_charge_paise,
    "pincode_mode": env_settings.pincode_mode,
    "staff_can_cancel_before_packing": env_settings.staff_can_cancel_before_packing,
    "order_number_prefix": env_settings.order_number_prefix,
    "estimated_delivery_days": "5-8",
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(BusinessSetting, key)
    if row is not None:
        return row.value_json
    return DEFAULTS.get(key)


def set_setting(db: Session, key: str, value: Any) -> None:
    row = db.get(BusinessSetting, key)
    if row is None:
        row = BusinessSetting(key=key, value_json=value)
        db.add(row)
    else:
        row.value_json = value
    db.flush()


def all_settings(db: Session) -> dict[str, Any]:
    out = dict(DEFAULTS)
    for row in db.scalars(select(BusinessSetting)):
        out[row.key] = row.value_json
    return out
