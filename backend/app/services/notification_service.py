"""Notification abstraction: email / whatsapp / sms / internal.

v1 ships:
  * email  -> "log" provider (records + logs). Plug SMTP/Resend/etc via EmailProvider.
  * whatsapp -> requires WhatsApp Business Platform; stubbed until provider chosen.
               Manual wa.me link generation is exposed separately for staff tooling.
  * sms    -> interface only until a provider is selected.
Dispatch never breaks the request path: failures are recorded on the row.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.commerce import Notification, NotificationChannel, NotificationStatus

log = get_logger("notifications")


class ChannelProvider(ABC):
    channel: NotificationChannel

    @abstractmethod
    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        """Return provider message id; raise ProviderNotConfiguredError when unusable."""


class LogEmailProvider(ChannelProvider):
    channel = NotificationChannel.email

    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        log.info("EMAIL(to=%s, event=%s, subject=%s)", recipient, event_type, payload.get("subject", ""))
        return f"log-{uuid4().hex[:12]}"


class UnconfiguredProvider(ChannelProvider):
    def __init__(self, channel: NotificationChannel, provider_name: str):
        self.channel = channel
        self._name = provider_name

    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        from app.core.exceptions import ProviderNotConfiguredError

        raise ProviderNotConfiguredError(f"{self._name} provider is not configured.")


def _provider_for(channel: NotificationChannel) -> ChannelProvider:
    if channel == NotificationChannel.email:
        if settings.email_provider in ("log", "console", ""):
            return LogEmailProvider()
        return UnconfiguredProvider(channel, settings.email_provider or "email")
    if channel == NotificationChannel.whatsapp:
        return UnconfiguredProvider(channel, settings.whatsapp_provider or "whatsapp")
    if channel == NotificationChannel.sms:
        return UnconfiguredProvider(channel, settings.sms_provider or "sms")
    return LogEmailProvider()


# Event → default channels (email first; configurable later per business preference)
EVENT_CHANNELS: dict[str, list[NotificationChannel]] = {
    "account_created": [NotificationChannel.email],
    "password_reset_requested": [NotificationChannel.email],
    "order_placed": [NotificationChannel.email, NotificationChannel.internal],
    "payment_successful": [NotificationChannel.email, NotificationChannel.internal],
    "payment_failed": [NotificationChannel.email],
    "cod_order_confirmed": [NotificationChannel.email],
    "order_packed": [NotificationChannel.email],
    "order_shipped": [NotificationChannel.email],
    "tracking_updated": [NotificationChannel.email],
    "order_delivered": [NotificationChannel.email],
    "cancellation_approved": [NotificationChannel.email],
    "cancellation_rejected": [NotificationChannel.email],
    "return_requested": [NotificationChannel.internal],
    "return_approved": [NotificationChannel.email],
    "exchange_approved": [NotificationChannel.email],
    "refund_initiated": [NotificationChannel.email],
    "refund_completed": [NotificationChannel.email],
    "restock_alert": [NotificationChannel.email],
    "bulk_enquiry_received": [NotificationChannel.internal],
    "low_inventory": [NotificationChannel.internal],
}


def notify(
    db: Session,
    *,
    event_type: str,
    recipient: str,
    channel: NotificationChannel | None = None,
    payload: dict[str, Any] | None = None,
    dispatch: bool = True,
) -> Notification:
    channels = [channel] if channel else EVENT_CHANNELS.get(event_type, [NotificationChannel.email])
    created: Notification | None = None
    for ch in channels:
        row = Notification(
            recipient=recipient,
            channel=ch,
            event_type=event_type,
            payload_json=payload or {},
            status=NotificationStatus.pending,
        )
        db.add(row)
        db.flush()
        created = row
        if not dispatch:
            continue
        try:
            provider = _provider_for(ch)
            row.provider_message_id = provider.send(recipient, event_type, payload or {})
            row.status = NotificationStatus.sent
            from app.core.database import utcnow

            row.sent_at = utcnow()
        except Exception as exc:  # provider missing/down — record, never crash request
            row.status = NotificationStatus.failed
            row.failure_reason = str(exc)[:300]
            log.warning("notification dispatch failed channel=%s event=%s: %s", ch, event_type, exc)
    db.flush()
    assert created is not None
    return created


def retry_notification(db: Session, notification: Notification) -> Notification:
    try:
        provider = _provider_for(notification.channel)
        notification.provider_message_id = provider.send(
            notification.recipient, notification.event_type, notification.payload_json or {}
        )
        notification.status = NotificationStatus.sent
        from app.core.database import utcnow

        notification.sent_at = utcnow()
        notification.failure_reason = None
    except Exception as exc:
        notification.status = NotificationStatus.failed
        notification.retry_count += 1
        notification.failure_reason = str(exc)[:300]
    db.flush()
    return notification


def whatsapp_link(phone: str, message: str) -> str:
    """Manual staff-assist link only — NOT an automated transactional channel."""
    digits = "".join(c for c in phone if c.isdigit())
    from urllib.parse import quote

    return f"https://wa.me/{digits}?text={quote(message)}"
