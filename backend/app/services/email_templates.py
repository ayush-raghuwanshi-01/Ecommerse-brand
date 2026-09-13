"""Transactional email templates.

Design constraints that shape this module:

* **Table-based HTML.** Outlook (desktop) still renders with the Word engine and
  ignores flexbox/grid. Every layout here is nested ``<table>`` with inline
  styles — verbose, but the only thing that reliably works across Gmail, Outlook,
  Apple Mail and the Android/iOS native clients.
* **Text alternative always generated.** Deliverability and accessibility both
  require a ``text/plain`` part; some clients also block HTML entirely.
* **Payloads are partial by construction.** Callers pass whatever they have
  (``order_placed`` sends a total, the staff-order path does not). Every field
  access goes through ``_get`` so a missing key degrades to "omit that row"
  rather than raising inside the request path.
* **No external images.** A remote logo would be blocked by default in most
  clients and would leak the recipient's IP to a third party.
"""

from dataclasses import dataclass
from typing import Any

from app.core.config import settings

# Brand tokens — mirrored from frontend/src/theme.ts so email and site match.
_BG = "#0b0a08"
_CARD = "#17140f"
_BORDER = "#2b2620"
_GOLD = "#c9a24b"
_TEXT = "#ece4d3"
_DIM = "#9a8f7a"


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """A ready-to-send email: subject plus both MIME bodies."""

    subject: str
    html: str
    text: str


def _get(payload: dict[str, Any], key: str, default: str = "") -> str:
    """Read a payload field, coercing to a non-None string."""
    value = payload.get(key, default)
    return default if value is None else str(value)


def _money(paise: Any) -> str | None:
    """Format integer paise as Indian rupees. ``None`` when absent."""
    if paise is None or paise == "":
        return None
    try:
        return f"₹{round(int(paise) / 100):,}"
    except (TypeError, ValueError):
        return None


def _rows(pairs: list[tuple[str, str | None]]) -> str:
    """Render label/value rows, skipping any whose value is missing."""
    out = []
    for label, value in pairs:
        if not value:
            continue
        out.append(
            f'<tr><td style="padding:6px 0;color:{_DIM};font-size:14px;">{_escape(label)}</td>'
            f'<td style="padding:6px 0;color:{_TEXT};font-size:14px;text-align:right;'
            f'font-weight:600;">{_escape(value)}</td></tr>'
        )
    return "".join(out)


def _escape(value: str) -> str:
    """Escape user- and merchant-supplied strings interpolated into HTML."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _layout(*, preheader: str, heading: str, body_html: str, cta: tuple[str, str] | None = None) -> str:
    """The shared branded shell.

    ``preheader`` is the snippet inbox previews show; it is rendered hidden so it
    does not appear twice in the body.
    """
    cta_html = ""
    if cta:
        label, url = cta
        cta_html = (
            '<tr><td align="center" style="padding:28px 0 8px;">'
            f'<a href="{_escape(url)}" style="background:{_GOLD};color:#141210;'
            'text-decoration:none;font-weight:700;font-size:15px;padding:14px 30px;'
            'border-radius:2px;display:inline-block;">'
            f"{_escape(label)}</a>"
            "</td></tr>"
        )

    brand = _escape(settings.project_name.replace(" Commerce API", "") or "Black House")
    support = _escape(settings.email_from)

    return f"""<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="x-apple-disable-message-reformatting"/>
<title>{_escape(preheader)}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};width:100%;">
<!-- Preheader: shown in the inbox list, hidden in the body. -->
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
  {_escape(preheader)}
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{_BG};padding:32px 16px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="max-width:560px;background:{_CARD};border:1px solid {_BORDER};">
      <tr><td style="padding:28px 32px 8px;border-bottom:1px solid {_BORDER};">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:22px;
                    letter-spacing:3px;color:{_GOLD};text-transform:uppercase;">{brand}</div>
        <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2px;
                    color:{_DIM};text-transform:uppercase;padding-top:6px;">
          Small-batch outerwear · Bhopal
        </div>
      </td></tr>
      <tr><td style="padding:32px;">
        <h1 style="margin:0 0 18px;font-family:Georgia,'Times New Roman',serif;font-size:26px;
                   line-height:1.25;font-weight:400;color:{_TEXT};">{_escape(heading)}</h1>
        <div style="font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.65;
                    color:{_DIM};">
{body_html}
        </div>
        {cta_html}
      </td></tr>
      <tr><td style="padding:22px 32px;border-top:1px solid {_BORDER};
                     font-family:Helvetica,Arial,sans-serif;font-size:12px;color:{_DIM};">
        Questions? Reply to this email or write to
        <a href="mailto:{support}" style="color:{_GOLD};text-decoration:none;">{support}</a>.
        <br/><br/>
        You are receiving this because you have an account or placed an order with {brand}.
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _order_details(payload: dict[str, Any]) -> str:
    """The shared order-summary block used by most lifecycle emails."""
    total = _money(payload.get("total_paise"))
    rows = _rows(
        [
            ("Order number", _get(payload, "order_number") or None),
            ("Total", total),
            ("Payment", _get(payload, "payment_method") or None),
            ("Status", _get(payload, "status") or None),
            ("Courier", _get(payload, "courier") or None),
            ("Tracking number", _get(payload, "tracking_number") or None),
            ("Expected delivery", _get(payload, "expected_delivery") or None),
            ("Refund amount", _money(payload.get("refund_paise"))),
            ("Reason", _get(payload, "reason") or None),
        ]
    )
    if not rows:
        return ""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:22px 0;border-top:1px solid {_BORDER};border-bottom:1px solid {_BORDER};">'
        f"{rows}</table>"
    )


def _text_body(heading: str, lines: list[str], payload: dict[str, Any]) -> str:
    """Plain-text mirror: heading, prose lines, then the detail rows."""
    parts = [heading, ""]
    parts.extend(line for line in lines if line)
    detail = [
        ("Order number", _get(payload, "order_number")),
        ("Total", _money(payload.get("total_paise")) or ""),
        ("Tracking number", _get(payload, "tracking_number")),
        ("Refund amount", _money(payload.get("refund_paise")) or ""),
    ]
    shown = [(k, v) for k, v in detail if v]
    if shown:
        parts.append("")
        parts.extend(f"{k}: {v}" for k, v in shown)
    parts += ["", "— Black House, Bhopal", settings.email_from]
    return "\n".join(parts)


def _storefront_url(path: str = "") -> str:
    return f"{settings.frontend_url.rstrip('/')}/{path.lstrip('/')}"


# ── Per-event renderers ──────────────────────────────────────────────────────
# Each returns a RenderedEmail. `payload` always wins for the subject when the
# caller supplied one, so ops can override copy without a deploy.

def _account_created(p: dict[str, Any]) -> RenderedEmail:
    heading = "Welcome to Black House"
    body = (
        "<p>Your account is ready. You can now track orders, save addresses and "
        "request returns from one place.</p>"
        "<p>Every piece is cut in limited runs in Bhopal and numbered by hand — "
        "we will email you the moment anything ships.</p>"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or "Welcome to Black House",
        html=_layout(preheader="Your account is ready", heading=heading, body_html=body,
                     cta=("Visit your account", _storefront_url("account"))),
        text=_text_body(heading, ["Your Black House account is ready.",
                                  "Track orders and manage returns at:"], p),
    )


def _password_reset(p: dict[str, Any]) -> RenderedEmail:
    token = _get(p, "reset_token") or _get(p, "token")
    url = _get(p, "reset_url") or (_storefront_url(f"login?reset={token}") if token else "")
    heading = "Reset your password"
    body = (
        "<p>We received a request to reset your password. The link below expires "
        "shortly and can be used once.</p>"
        "<p style=\"color:#9a8f7a;font-size:13px;\">If you did not request this, "
        "you can safely ignore this email — your password will not change.</p>"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or "Reset your Black House password",
        html=_layout(preheader="Use this link to choose a new password", heading=heading,
                     body_html=body, cta=("Reset password", url) if url else None),
        text=_text_body(heading, ["Open this link to choose a new password:", url,
                                  "If you did not request this, ignore this email."], p),
    )


def _order_placed(p: dict[str, Any]) -> RenderedEmail:
    number = _get(p, "order_number")
    heading = f"Order {number} received" if number else "Your order is received"
    body = (
        "<p>Thank you — we have your order and it is being prepared. "
        "Small-batch pieces are cut and finished to order, so please allow the "
        "handling time shown at checkout.</p>"
        "<p>We will email you again as soon as it ships, with tracking.</p>"
        f"{_order_details(p)}"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader="We have received your order", heading=heading, body_html=body,
                     cta=("View your order", _storefront_url("orders"))),
        text=_text_body(heading, ["Thank you — we have your order.",
                                  "We will email you when it ships."], p),
    )


def _payment_successful(p: dict[str, Any]) -> RenderedEmail:
    number = _get(p, "order_number")
    heading = f"Payment received for {number}" if number else "Payment received"
    body = (
        "<p>Your payment was successful and your order is confirmed. "
        "A GST invoice is available from your order page.</p>"
        f"{_order_details(p)}"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader="Payment confirmed", heading=heading, body_html=body,
                     cta=("View receipt", _storefront_url("orders"))),
        text=_text_body(heading, ["Your payment was successful."], p),
    )


def _payment_failed(p: dict[str, Any]) -> RenderedEmail:
    number = _get(p, "order_number")
    heading = f"Payment failed for {number}" if number else "Payment failed"
    body = (
        "<p>We could not process your payment. Your items are still reserved, but "
        "only for a short window — after that they are released back to stock.</p>"
        "<p>No money has been taken. You can retry from your order page, or choose "
        "cash on delivery if that is available for your PIN code.</p>"
        f"{_order_details(p)}"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader="Your payment did not go through — your items are held briefly",
                     heading=heading, body_html=body,
                     cta=("Retry payment", _storefront_url("orders"))),
        text=_text_body(heading, ["We could not process your payment.",
                                  "Your items are reserved for a short window.",
                                  "Retry from your order page."], p),
    )


def _order_shipped(p: dict[str, Any]) -> RenderedEmail:
    number = _get(p, "order_number")
    heading = f"Order {number} has shipped" if number else "Your order has shipped"
    tracking = _get(p, "tracking_number")
    track_url = _get(p, "tracking_url")
    body = (
        "<p>Your order is on its way. Tracking appears below and usually updates "
        "within a few hours of dispatch.</p>"
        f"{_order_details(p)}"
    )
    cta = ("Track shipment", track_url) if track_url else ("View your order", _storefront_url("orders"))
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader=f"Tracking {tracking}" if tracking else "Your order is on its way",
                     heading=heading, body_html=body, cta=cta),
        text=_text_body(heading, ["Your order is on its way."], p),
    )


def _order_delivered(p: dict[str, Any]) -> RenderedEmail:
    heading = "Your order has been delivered"
    days = settings.return_window_days
    body = (
        "<p>We hope it fits perfectly. If it does not, you can request a return or "
        f"exchange within {days} days of delivery from your order page.</p>"
        "<p>Sale items can be exchanged or replaced but are not eligible for a cash "
        "refund — the policy is stated on every product page.</p>"
        f"{_order_details(p)}"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader=f"Returns open for {days} days", heading=heading, body_html=body,
                     cta=("Manage this order", _storefront_url("orders"))),
        text=_text_body(heading, [f"Delivered. Returns are open for {days} days."], p),
    )


def _refund(p: dict[str, Any]) -> RenderedEmail:
    initiated = p.get("_refund_stage") != "completed"
    amount = _money(p.get("refund_paise"))
    heading = "Refund initiated" if initiated else "Refund completed"

    # Built without nested f-strings: the project supports 3.11 as well as 3.12,
    # and nested same-quote f-strings only parse on 3.12+.
    amount_phrase = f" of {_escape(amount)}" if amount else ""
    if initiated:
        lead = (
            f"<p>Your refund{amount_phrase} has been initiated and is on its way back "
            "to the original payment method. Banks and card issuers typically take "
            "5–7 working days to post it.</p>"
        )
    else:
        lead = (
            f"<p>Your refund{amount_phrase} has been completed. It should now be "
            "visible with your bank or card issuer.</p>"
        )
    body = lead + _order_details(p)
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader=heading, heading=heading, body_html=body,
                     cta=("View refund status", _storefront_url("orders"))),
        text=_text_body(heading, ["Refund status updated on your order."], p),
    )


def _return_approved(p: dict[str, Any]) -> RenderedEmail:
    heading = "Your return request is approved"
    body = (
        "<p>We have approved your return. Pickup details and the address to send "
        "the piece to are on your order page.</p>"
        "<p>Please keep the garment unworn with tags attached, and use the original "
        "packaging if you still have it.</p>"
        f"{_order_details(p)}"
    )
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader="Return approved — pickup details inside", heading=heading,
                     body_html=body, cta=("View return", _storefront_url("orders"))),
        text=_text_body(heading, ["Your return request has been approved."], p),
    )


def _cancellation(p: dict[str, Any]) -> RenderedEmail:
    approved = _get(p, "decision").lower() != "rejected"
    heading = "Cancellation approved" if approved else "Cancellation request declined"
    if approved:
        lead = (
            "<p>Your order has been cancelled. Any amount paid is refunded to the "
            "original payment method within 5–7 working days.</p>"
        )
    else:
        lead = (
            "<p>We were unable to cancel this order — it has already progressed too "
            "far in fulfilment. You can still request a return once it is delivered, "
            "within the return window.</p>"
        )
    body = lead + _order_details(p)
    return RenderedEmail(
        subject=_get(p, "subject") or heading,
        html=_layout(preheader=heading, heading=heading, body_html=body,
                     cta=("View order", _storefront_url("orders"))),
        text=_text_body(heading, ["Cancellation decision recorded on your order."], p),
    )


def _generic(p: dict[str, Any]) -> RenderedEmail:
    """Fallback for events without a bespoke template.

    Never raises: an unmapped event must still produce a sendable email rather
    than silently dropping a customer notification.
    """
    event = _get(p, "event_type") or "update"
    heading = _get(p, "subject") or f"An update on your order ({event})"
    body = f"<p>{_escape(_get(p, 'message') or 'There is an update on your account.')}</p>{_order_details(p)}"
    return RenderedEmail(
        subject=heading,
        html=_layout(preheader=heading[:90], heading=heading, body_html=body,
                     cta=("Visit Black House", _storefront_url())),
        text=_text_body(heading, [_get(p, "message") or "There is an update on your account."], p),
    )


# event_type → renderer. Anything absent falls through to _generic.
TEMPLATES = {
    "account_created": _account_created,
    "password_reset_requested": _password_reset,
    "order_placed": _order_placed,
    "payment_successful": _payment_successful,
    "payment_failed": _payment_failed,
    "cod_order_confirmed": _order_placed,
    "order_packed": _order_placed,
    "order_shipped": _order_shipped,
    "tracking_updated": _order_shipped,
    "order_delivered": _order_delivered,
    "cancellation_approved": _cancellation,
    "cancellation_rejected": _cancellation,
    "return_approved": _return_approved,
    "exchange_approved": _return_approved,
    "refund_initiated": _refund,
    "refund_completed": _refund,
    "return_requested": _generic,
    "restock_alert": _generic,
}


def render(event_type: str, payload: dict[str, Any]) -> RenderedEmail:
    """Render an event into a sendable email. Always returns something usable."""
    renderer = TEMPLATES.get(event_type, _generic)
    merged = {**payload, "event_type": event_type}
    # refund_completed and refund_initiated share a renderer; tag the stage.
    if event_type == "refund_completed":
        merged["_refund_stage"] = "completed"
    try:
        return renderer(merged)
    except Exception:  # pragma: no cover - template bugs must not break dispatch
        from app.core.logging import get_logger

        get_logger("email_templates").exception("template %r failed; using generic", event_type)
        return _generic(merged)
