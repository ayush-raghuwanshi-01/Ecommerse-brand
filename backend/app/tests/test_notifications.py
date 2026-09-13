"""Notification + email template tests.

Resend is exercised with a mocked transport — these tests must never hit the
network, and must not require a real API key.
"""

import json
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import ProviderNotConfiguredError
from app.models.commerce import NotificationChannel, NotificationStatus
from app.services import email_templates, notification_service
from app.services.notification_service import (
    EmailDeliveryError,
    LogEmailProvider,
    ResendEmailProvider,
    _provider_for,
    notify,
    retry_notification,
    whatsapp_link,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> Any:
        return self._payload


@pytest.fixture()
def resend_configured(monkeypatch):
    """Point settings at Resend with a fake key."""
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "email_api_key", "re_test_fake_key", raising=False)
    monkeypatch.setattr(settings, "email_from", "orders@blackhouse.example", raising=False)
    monkeypatch.setattr(settings, "email_reply_to", "support@blackhouse.example", raising=False)
    yield


@pytest.fixture()
def no_sleep(monkeypatch):
    """Backoff sleeps would make retry tests slow for no benefit."""
    monkeypatch.setattr(notification_service.time, "sleep", lambda _s: None)


# ══════════════════════════════════════════════════════════════════════════
# Provider selection
# ══════════════════════════════════════════════════════════════════════════

def test_log_provider_is_the_development_default(monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "log", raising=False)
    assert isinstance(_provider_for(NotificationChannel.email), LogEmailProvider)


def test_resend_selected_when_configured(resend_configured):
    assert isinstance(_provider_for(NotificationChannel.email), ResendEmailProvider)


def test_unknown_email_provider_is_reported_not_crashed(monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "carrier-pigeon", raising=False)
    provider = _provider_for(NotificationChannel.email)
    with pytest.raises(ProviderNotConfiguredError):
        provider.send("a@b.c", "order_placed", {})


def test_whatsapp_and_sms_are_explicitly_unconfigured():
    """The business chose manual wa.me links; automated channels must say so
    rather than silently pretending to send."""
    for channel in (NotificationChannel.whatsapp, NotificationChannel.sms):
        with pytest.raises(ProviderNotConfiguredError):
            _provider_for(channel).send("+911234567890", "order_shipped", {})


# ══════════════════════════════════════════════════════════════════════════
# Resend provider configuration guards
# ══════════════════════════════════════════════════════════════════════════

def test_resend_without_api_key_raises_with_actionable_message(monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "email_api_key", "", raising=False)
    with pytest.raises(ProviderNotConfiguredError) as exc:
        ResendEmailProvider()
    assert "EMAIL_API_KEY" in str(exc.value)


def test_resend_with_invalid_sender_raises(monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "email_api_key", "re_test_x", raising=False)
    monkeypatch.setattr(settings, "email_from", "not-an-email", raising=False)
    with pytest.raises(ProviderNotConfiguredError) as exc:
        ResendEmailProvider()
    assert "EMAIL_FROM" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════
# Resend request shape
# ══════════════════════════════════════════════════════════════════════════

def test_successful_send_returns_provider_message_id(resend_configured, monkeypatch):
    captured: dict[str, Any] = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return _FakeResponse(200, {"id": "msg_abc123"})

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = ResendEmailProvider()
    message_id = provider.send("customer@example.com", "order_placed",
                               {"order_number": "BH-1042", "total_paise": 1850000})

    assert message_id == "msg_abc123"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_fake_key"
    assert captured["json"]["to"] == ["customer@example.com"]
    assert captured["json"]["from"] == "orders@blackhouse.example"
    assert captured["json"]["reply_to"] == "support@blackhouse.example"
    assert captured["json"]["subject"] == "Order BH-1042 received"
    # Both MIME parts must be present — html-only sends hurt deliverability.
    assert "<table" in captured["json"]["html"]
    assert "BH-1042" in captured["json"]["text"]


def test_explicit_timeout_is_always_set(resend_configured, monkeypatch):
    """httpx without a timeout can hang a request thread indefinitely."""
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["timeout"] = timeout
        return _FakeResponse(200, {"id": "x"})

    monkeypatch.setattr(httpx, "post", fake_post)
    ResendEmailProvider().send("a@b.c", "order_placed", {})

    assert isinstance(seen["timeout"], httpx.Timeout)
    assert seen["timeout"].connect == 5.0
    assert seen["timeout"].read == 15.0


def test_order_number_is_threaded_via_header(resend_configured, monkeypatch):
    captured: dict[str, Any] = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(200, {"id": "x"})

    monkeypatch.setattr(httpx, "post", fake_post)
    ResendEmailProvider().send("a@b.c", "order_shipped", {"order_number": "BH-77"})
    assert captured["json"]["headers"]["X-Entity-Ref-ID"] == "BH-77"


def test_invalid_recipient_is_rejected_before_calling_the_api(resend_configured, monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or _FakeResponse(200, {}))

    with pytest.raises(EmailDeliveryError):
        ResendEmailProvider().send("not-an-email", "order_placed", {})
    assert calls == [], "must not spend an API call on an invalid address"


# ══════════════════════════════════════════════════════════════════════════
# Retry behaviour
# ══════════════════════════════════════════════════════════════════════════

def test_retries_on_rate_limit_then_succeeds(resend_configured, no_sleep, monkeypatch):
    attempts = []

    def fake_post(url, json=None, headers=None, timeout=None):
        attempts.append(1)
        if len(attempts) == 1:
            return _FakeResponse(429, text="rate limited")
        return _FakeResponse(200, {"id": "ok"})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ResendEmailProvider().send("a@b.c", "order_placed", {}) == "ok"
    assert len(attempts) == 2


def test_retries_on_server_error_then_gives_up(resend_configured, no_sleep, monkeypatch):
    attempts = []
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: attempts.append(1) or _FakeResponse(503, text="unavailable"))

    with pytest.raises(EmailDeliveryError) as exc:
        ResendEmailProvider().send("a@b.c", "order_placed", {})
    assert exc.value.retryable is True
    assert exc.value.status_code == 503
    assert len(attempts) == ResendEmailProvider.MAX_ATTEMPTS


def test_does_not_retry_a_permanent_rejection(resend_configured, no_sleep, monkeypatch):
    """422 = unverified sender domain. Retrying wastes quota and delays the answer."""
    attempts = []
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: attempts.append(1) or _FakeResponse(422, text="domain not verified"))

    with pytest.raises(EmailDeliveryError) as exc:
        ResendEmailProvider().send("a@b.c", "order_placed", {})
    assert exc.value.retryable is False
    assert len(attempts) == 1


def test_network_timeout_is_retryable(resend_configured, no_sleep, monkeypatch):
    attempts = []

    def fake_post(*a, **k):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectTimeout("boom")
        return _FakeResponse(200, {"id": "recovered"})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ResendEmailProvider().send("a@b.c", "order_placed", {}) == "recovered"
    assert len(attempts) == 2


def test_dns_failure_is_retryable(resend_configured, no_sleep, monkeypatch):
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("dns")))
    with pytest.raises(EmailDeliveryError) as exc:
        ResendEmailProvider().send("a@b.c", "order_placed", {})
    assert exc.value.retryable is True


# ══════════════════════════════════════════════════════════════════════════
# Dispatch must never break the request path
# ══════════════════════════════════════════════════════════════════════════

def test_notify_records_failure_without_raising(clean_db, monkeypatch):
    """The critical contract: a down email vendor must not fail an order."""
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "email_api_key", "re_test_x", raising=False)
    monkeypatch.setattr(settings, "email_from", "orders@blackhouse.example", raising=False)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(500, text="boom"))
    monkeypatch.setattr(notification_service.time, "sleep", lambda _s: None)

    row = notify(clean_db, event_type="order_placed", recipient="c@example.com",
                 payload={"order_number": "BH-1"}, channel=NotificationChannel.email)

    assert row.status == NotificationStatus.failed
    assert "500" in (row.failure_reason or "")
    assert row.provider_message_id is None


def test_notify_records_success(clean_db, monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "resend", raising=False)
    monkeypatch.setattr(settings, "email_api_key", "re_test_x", raising=False)
    monkeypatch.setattr(settings, "email_from", "orders@blackhouse.example", raising=False)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, {"id": "msg_ok"}))

    row = notify(clean_db, event_type="payment_successful", recipient="c@example.com",
                 payload={"order_number": "BH-2"}, channel=NotificationChannel.email)

    assert row.status == NotificationStatus.sent
    assert row.provider_message_id == "msg_ok"
    assert row.sent_at is not None


def test_retry_notification_clears_previous_failure(clean_db, monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "log", raising=False)
    row = notify(clean_db, event_type="order_placed", recipient="c@example.com",
                 payload={}, channel=NotificationChannel.email, dispatch=False)
    row.status = NotificationStatus.failed
    row.failure_reason = "transient"

    retried = retry_notification(clean_db, row)
    assert retried.status == NotificationStatus.sent
    assert retried.failure_reason is None


def test_dispatch_false_persists_without_sending(clean_db, monkeypatch):
    """Lets a worker send later instead of blocking the request."""
    calls = []
    monkeypatch.setattr(settings, "email_provider", "log", raising=False)
    monkeypatch.setattr(LogEmailProvider, "send", lambda *a, **k: calls.append(1) or "x")

    row = notify(clean_db, event_type="order_placed", recipient="c@example.com",
                 payload={}, channel=NotificationChannel.email, dispatch=False)
    assert row.status == NotificationStatus.pending
    assert calls == []


# ══════════════════════════════════════════════════════════════════════════
# Templates
# ══════════════════════════════════════════════════════════════════════════

def test_every_mapped_event_renders_both_mime_parts():
    for event in email_templates.TEMPLATES:
        rendered = email_templates.render(event, {"order_number": "BH-1", "total_paise": 100000})
        assert rendered.subject, f"{event} produced no subject"
        assert rendered.html.startswith("<!doctype html>"), f"{event} html is malformed"
        assert rendered.text.strip(), f"{event} produced no text part"


def test_every_event_channel_has_a_template_or_falls_back_safely():
    for event in notification_service.EVENT_CHANNELS:
        rendered = email_templates.render(event, {})
        assert rendered.subject and rendered.html


def test_paise_are_formatted_as_rupees():
    rendered = email_templates.render("order_placed", {"total_paise": 1850000})
    assert "₹18,500" in rendered.text
    assert "₹18,500" in rendered.html


def test_payload_subject_overrides_the_template():
    """Ops can retarget copy without a deploy."""
    rendered = email_templates.render("order_placed", {"subject": "Diwali order confirmed"})
    assert rendered.subject == "Diwali order confirmed"


def test_html_escapes_injected_values():
    rendered = email_templates.render(
        "order_placed", {"order_number": '"><script>alert(1)</script>'}
    )
    assert "<script>alert(1)</script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html


def test_missing_fields_omit_rows_rather_than_rendering_empty_labels():
    rendered = email_templates.render("order_shipped", {})
    assert "Tracking number" not in rendered.html


def test_template_bug_cannot_break_dispatch(monkeypatch):
    """A raising renderer must degrade to the generic template."""
    def boom(_payload):
        raise RuntimeError("template exploded")

    monkeypatch.setitem(email_templates.TEMPLATES, "order_placed", boom)
    rendered = email_templates.render("order_placed", {"order_number": "BH-1"})
    assert rendered.subject  # generic fallback still produced something sendable


def test_return_window_in_delivered_email_matches_settings():
    rendered = email_templates.render("order_delivered", {})
    assert str(settings.return_window_days) in rendered.html


# ══════════════════════════════════════════════════════════════════════════
# Manual WhatsApp links (the channel the business actually uses)
# ══════════════════════════════════════════════════════════════════════════

def test_whatsapp_link_strips_formatting_and_encodes_message():
    link = whatsapp_link("+91 98765-43210", "Hello, order BH-1 is ready & packed")
    assert link.startswith("https://wa.me/919876543210?text=")
    assert "%20" in link and "%26" in link  # spaces and ampersand encoded


def test_whatsapp_link_handles_bare_digits():
    assert whatsapp_link("9876543210", "hi").startswith("https://wa.me/9876543210")
