"""GST-inclusive pricing, discount allocation and order totals.

All money is integer paise. Displayed prices include GST; the tax component is
derived per line: taxable = gross / (1 + gst%), tax = gross - taxable.
"""

from dataclasses import dataclass, field

from app.core.config import settings
from app.models.catalog import ProductVariant


@dataclass
class PricedLine:
    variant: ProductVariant
    qty: int
    unit_price_paise: int
    line_gross_paise: int = 0
    discount_paise: int = 0
    tax_paise: int = 0
    total_paise: int = 0
    is_preorder: bool = False
    eligible_for_coupon: bool = True
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.line_gross_paise = self.unit_price_paise * self.qty


def line_tax_paise(gross_paise: int, gst_percentage: float) -> int:
    """GST-inclusive extraction."""
    pct = float(gst_percentage)
    taxable = int(round(gross_paise * 100 / (100 + pct)))
    return gross_paise - taxable


def allocate_discount(lines: list[PricedLine], discount_paise: int) -> None:
    """Spread a coupon discount pro-rata over eligible lines (largest-remainder safe)."""
    eligible = [ln for ln in lines if ln.eligible_for_coupon]
    if not eligible or discount_paise <= 0:
        return
    eligible_total = sum(ln.line_gross_paise for ln in eligible)
    if eligible_total <= 0:
        return
    discount_paise = min(discount_paise, eligible_total)
    allocated = 0
    for ln in eligible[:-1]:
        share = int(discount_paise * ln.line_gross_paise // eligible_total)
        ln.discount_paise += share
        allocated += share
    eligible[-1].discount_paise += discount_paise - allocated


def finalize(lines: list[PricedLine], *, discount_paise: int, shipping_paise: int) -> dict:
    """Compute per-line tax/total and the order totals block."""
    allocate_discount(lines, discount_paise)
    subtotal = 0
    tax_total = 0
    for ln in lines:
        net = ln.line_gross_paise - ln.discount_paise
        ln.tax_paise = line_tax_paise(net, float(ln.variant.gst_percentage))
        ln.total_paise = net
        subtotal += ln.line_gross_paise
        tax_total += ln.tax_paise
    grand = subtotal - discount_paise + shipping_paise
    return {
        "subtotal_paise": subtotal,
        "discount_paise": discount_paise,
        "shipping_paise": shipping_paise,
        "tax_paise": tax_total,
        "grand_total_paise": max(grand, 0),
        "currency": settings.default_currency,
    }
