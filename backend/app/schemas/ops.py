from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PaymentOut(ORMModel):
    id: str
    order_id: str
    provider: str
    provider_order_id: str | None
    provider_payment_id: str | None
    amount_paise: int
    currency: str
    method: str
    status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RetryPaymentRequest(BaseModel):
    order_id: str


class AdjustmentRequest(BaseModel):
    """qty_change must be non-zero; sign conventions enforced per adjustment type."""

    variant_id: str
    adjustment_type: str = Field(pattern="^(increase|decrease|return|damage|defect|correction)$")
    qty_change: int
    reason: str | None = None

    @field_validator("qty_change")
    @classmethod
    def _nonzero(cls, v):
        if v == 0:
            raise ValueError("qty_change must not be zero")
        return v


class AdjustmentOut(ORMModel):
    id: str
    variant_id: str
    adjustment_type: str
    qty_before: int
    qty_change: int
    qty_after: int
    reason: str | None
    reference_type: str | None
    created_at: datetime


class VariantStockOut(ORMModel):
    variant_id: str
    sku: str
    product_name: str
    size: str
    stock_qty: int
    reserved_qty: int
    available_qty: int
    sold_qty: int
    damaged_qty: int
    defective_qty: int
    returned_qty: int
    is_low_stock: bool


class ShipmentCreate(BaseModel):
    order_id: str
    provider: str = "manual"
    tracking_number: str | None = None
    tracking_url: str | None = None


class ShipmentUpdate(BaseModel):
    status: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    note: str | None = None


class ShipmentOut(ORMModel):
    id: str
    order_id: str
    direction: str
    provider: str
    tracking_number: str | None
    tracking_url: str | None
    status: str
    pickup_date: datetime | None
    shipped_date: datetime | None
    delivered_date: datetime | None
    return_tracking_number: str | None


class ReturnCreate(BaseModel):
    order_id: str
    order_item_id: str | None = None
    return_type: str = Field(pattern="^(refund|size_exchange|product_exchange|replacement)$")
    reason: str = Field(
        pattern="^(size_issue|wrong_product|damaged_product|defective_product|changed_mind|quality_issue|other)$"
    )
    notes: str | None = None
    exchange_variant_id: str | None = None


class ReturnOut(ORMModel):
    id: str
    order_id: str
    order_item_id: str | None
    return_type: str
    reason: str
    status: str
    notes: str | None
    staff_notes: str | None
    company_pays_shipping: bool
    exchange_variant_id: str | None
    created_at: datetime
    completed_at: datetime | None


class ReturnStatusUpdate(BaseModel):
    status: str
    staff_notes: str | None = None
    accept_items: bool = True  # on inspect: restock accepted units


class RefundApproveRequest(BaseModel):
    refund_id: str
    approve: bool
    note: str | None = None


class RefundOut(ORMModel):
    id: str
    order_id: str
    return_request_id: str | None
    amount_paise: int
    status: str
    provider_refund_id: str | None
    initiated_by: str | None
    approved_by: str | None
    completed_at: datetime | None
    created_at: datetime


class CouponCreate(BaseModel):
    code: str
    discount_type: str = "fixed"
    discount_value: int = Field(ge=1)
    max_discount_paise: int | None = None
    min_order_paise: int = 0
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    per_customer_limit: int | None = Field(default=None, ge=1)
    eligible_product_ids: list[str] | None = None


class CouponUpdate(BaseModel):
    is_active: bool | None = None
    discount_value: int | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = None


class CouponOut(ORMModel):
    id: str
    code: str
    discount_type: str
    discount_value: int
    max_discount_paise: int | None
    min_order_paise: int
    starts_at: datetime | None
    expires_at: datetime | None
    usage_limit: int | None
    per_customer_limit: int | None
    is_active: bool
    eligible_product_ids: list | None
    times_used: int = 0


class RestockSubscribeRequest(BaseModel):
    variant_id: str
    phone: str | None = None


class RestockSubscriptionOut(ORMModel):
    id: str
    variant_id: str
    email: str
    phone: str | None
    status: str
    created_at: datetime


class BulkEnquiryCreate(BaseModel):
    name: str
    business_name: str | None = None
    email: str
    phone: str
    product_interest: str
    estimated_qty: int | None = Field(default=None, ge=1)
    message: str | None = None


class BulkEnquiryUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(new|contacted|in_progress|quoted|closed|cancelled)$")
    staff_notes: str | None = None


class BulkEnquiryOut(ORMModel):
    id: str
    name: str
    business_name: str | None
    email: str
    phone: str
    product_interest: str
    estimated_qty: int | None
    message: str | None
    status: str
    staff_notes: str | None
    created_at: datetime


class NotificationOut(ORMModel):
    id: str
    recipient: str
    channel: str
    event_type: str
    status: str
    provider_message_id: str | None
    retry_count: int
    sent_at: datetime | None
    failure_reason: str | None
    created_at: datetime


class AuditLogOut(ORMModel):
    id: str
    user_id: str | None
    role: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before_json: dict | None
    after_json: dict | None
    ip: str | None
    created_at: datetime


class ShippingRuleCreate(BaseModel):
    kind: str = Field(pattern="^(serviceable|blocked|rate_pincode|rate_state)$")
    pincode_from: str | None = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    pincode_to: str | None = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    state: str | None = None
    charge_paise: int | None = Field(default=None, ge=0)


class ShippingRuleOut(ORMModel):
    id: str
    kind: str
    pincode_from: str | None
    pincode_to: str | None
    state: str | None
    charge_paise: int | None
    is_active: bool


class SettingsOut(BaseModel):
    settings: dict


class SettingsUpdate(BaseModel):
    settings: dict


class ReportsOut(BaseModel):
    period_days: int
    orders_total: int
    revenue_paise: int
    aov_paise: int
    units_sold: int
    orders_by_status: dict
    revenue_by_source: dict
    low_stock_variants: list[VariantStockOut]
