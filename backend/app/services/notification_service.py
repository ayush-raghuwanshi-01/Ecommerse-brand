"""Notification abstraction: email / whatsapp / sms / internal.

Providers
  * email -> "resend" (production) or "log" (development default: records + logs).
  * whatsapp -> manual wa.me link generation for staff tooling. Automated
    WhatsApp needs Business Platform access and is deliberately not implemented;
    the business chose the manual channel.
  * sms -> interface only; no provider selected.

Dispatch never breaks the request path: a provider failure is recorded on the
Notification row and logged, and the caller's transaction still commits. That is
a deliberate trade — a customer's order must not fail because Resend is down.
The row stays queryable so a worker or an operator can retry it later via
``retry_notification``.
"""

import time
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.commerce import Notification, NotificationChannel, NotificationStatus
from app.services import email_templates

log = get_logger("notifications")


class ChannelProvider(ABC):
    channel: NotificationChannel

    @abstractmethod
    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        """Return provider message id; raise ProviderNotConfiguredError when unusable."""


class EmailDeliveryError(Exception):
    """The provider rejected or could not complete the send.

    Carries the HTTP status so callers can distinguish a permanent failure
    (4xx — bad address, unverified sender) from a transient one (429/5xx).
    """

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class LogEmailProvider(ChannelProvider):
    """Development provider: renders the template and logs it. Sends nothing."""

    channel = NotificationChannel.email

    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        # Render anyway, so a broken template fails loudly in development rather
        # than only after a real provider is wired up.
        email = email_templates.render(event_type, payload)
        log.info(
            "EMAIL(to=%s, event=%s, subject=%s, html=%d bytes)",
            recipient, event_type, email.subject, len(email.html),
        )
        if settings.app_debug:
            log.debug("EMAIL BODY(to=%s)\n%s", recipient, email.text)
        return f"log-{uuid4().hex[:12]}"


class ResendEmailProvider(ChannelProvider):
    """Resend transactional email (https://resend.com).

    Retry policy is intentionally shallow: one retry on 429/5xx with a short
    backoff. Anything longer would block the request thread — a checkout must
    not sit waiting on an email vendor. Deeper retries belong to
    ``retry_notification`` driven by a worker, not to the request path.
    """

    channel = NotificationChannel.email
    API_URL = "https://api.resend.com/emails"
    MAX_ATTEMPTS = 2
    RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

    def __init__(self) -> None:
        from app.core.exceptions import ProviderNotConfiguredError

        if not settings.email_api_key:
            raise ProviderNotConfiguredError(
                "EMAIL_PROVIDER=resend but EMAIL_API_KEY is empty. "
                "Create a key at resend.com/api-keys, or set EMAIL_PROVIDER=log for local dev."
            )
        if "@" not in settings.email_from:
            raise ProviderNotConfiguredError(
                f"EMAIL_FROM={settings.email_from!r} is not a valid address. "
                "It must be on a domain you have verified in Resend."
            )
        self._api_key = settings.email_api_key
        self._sender = settings.email_from
        self._reply_to = settings.email_reply_to or settings.email_from

    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        if not recipient or "@" not in recipient:
            raise EmailDeliveryError(f"Invalid recipient address: {recipient!r}")

        email = email_templates.render(event_type, payload)
        body = {
            "from": self._sender,
            "to": [recipient],
            "subject": email.subject,
            "html": email.html,
            "text": email.text,
            "reply_to": self._reply_to,
            "headers": {
                # Lets a recipient's client thread the whole order conversation.
                "X-Entity-Ref-ID": str(payload.get("order_number") or event_type),
                "X-Event-Type": event_type,
            },
        }

        last_error: EmailDeliveryError | None = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                # Explicit timeouts: httpx would otherwise wait indefinitely on a
                # stalled connection and hold the request thread with it.
                response = httpx.post(
                    self.API_URL,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
                )
            except httpx.TimeoutException as exc:
                last_error = EmailDeliveryError(f"Resend timed out: {exc}", retryable=True)
            except httpx.HTTPError as exc:
                last_error = EmailDeliveryError(f"Resend network error: {exc}", retryable=True)
            else:
                if response.status_code in {200, 201}:
                    message_id = str(response.json().get("id") or "")
                    log.info(
                        "email sent via resend to=%s event=%s id=%s",
                        recipient, event_type, message_id,
                    )
                    return message_id

                retryable = response.status_code in self.RETRYABLE_STATUS
                last_error = EmailDeliveryError(
                    f"Resend returned {response.status_code}: {response.text[:300]}",
                    status_code=response.status_code,
                    retryable=retryable,
                )
                # 4xx other than rate limiting will not succeed on retry — the
                # sender domain is unverified or the address is rejected.
                if not retryable:
                    log.error(
                        "email permanently rejected to=%s event=%s status=%s body=%s",
                        recipient, event_type, response.status_code, response.text[:300],
                    )
                    raise last_error

            if attempt < self.MAX_ATTEMPTS and last_error and last_error.retryable:
                delay = 0.4 * attempt
                log.warning(
                    "resend attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt, self.MAX_ATTEMPTS, last_error, delay,
                )
                time.sleep(delay)

        assert last_error is not None
        raise last_error


class UnconfiguredProvider(ChannelProvider):
    def __init__(self, channel: NotificationChannel, provider_name: str):
        self.channel = channel
        self._name = provider_name

    def send(self, recipient: str, event_type: str, payload: dict[str, Any]) -> str:
        from app.core.exceptions import ProviderNotConfiguredError

        raise ProviderNotConfiguredError(f"{self._name} provider is not configured.")


def _provider_for(channel: NotificationChannel) -> ChannelProvider:
    if channel == NotificationChannel.email:
        provider = (settings.email_provider or "log").strip().lower()
        if provider in {"resend"}:
            return ResendEmailProvider()
        if provider in {"log", "console", ""}:
            return LogEmailProvider()
        return UnconfiguredProvider(channel, settings.email_provider or "email")
    if channel == NotificationChannel.whatsapp:
        return UnconfiguredProvider(channel, settings.whatsapp_provider or "whatsapp")
    if channel == NotificationChannel.sms:
        return UnconfiguredProvider(channel, settings.sms_provider or "sms")
    # `internal` is a persisted inbox row; there is nothing to deliver.
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
