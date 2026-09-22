from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, Totals


class CartItemOut(ORMModel):
    id: str
    variant_id: str
    product_id: str
    product_name: str
    variant_name: str
    sku: str
    size: str
    image_url: str | None
    qty: int
    unit_price_paise_snapshot: int
    current_unit_price_paise: int
    price_changed: bool
    is_available: bool
    is_preorder: bool
    available_qty: int
    line_total_paise: int


class CartOut(BaseModel):
    id: str
    items: list[CartItemOut]
    coupon_code: str | None = None
    totals: Totals
    checkout_blocked: bool
    block_reasons: list[str] = []


class CartAddRequest(BaseModel):
    variant_id: str
    qty: int = Field(default=1, ge=1, le=10)


class CartUpdateRequest(BaseModel):
    qty: int = Field(ge=0, le=10)


class CouponApplyRequest(BaseModel):
    code: str


class PincodeCheck(BaseModel):
    postal_code: str = Field(pattern=r"^[1-9][0-9]{5}$")
    subtotal_paise: int | None = Field(default=None, ge=0)


class PincodeCheckOut(BaseModel):
    postal_code: str
    serviceable: bool
    shipping_charge_paise: int
    estimated_delivery_days: str = "5-8"
    reason: str | None = None


class CheckoutPreview(BaseModel):
    items: list[CartItemOut]
    totals: Totals
    price_changes: list[dict] = []
    unavailable_items: list[dict] = []
    checkout_blocked: bool
    block_reasons: list[str] = []
    shipping: PincodeCheckOut | None = None


class GuestOrderLine(BaseModel):
    variant_id: str
    qty: int = Field(ge=1, le=10)


class GuestAddressInput(BaseModel):
    full_name: str
    phone: str
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str = "Madhya Pradesh"
    postal_code: str = Field(pattern=r"^[1-9][0-9]{5}$")
    country: str = "IN"


class GuestPlaceOrderRequest(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    shipping_address: GuestAddressInput
    items: list[GuestOrderLine] = Field(min_length=1)
    customer_notes: str | None = None


class PlaceOrderRequest(BaseModel):
    shipping_address_id: str
    billing_address_id: str | None = None  # defaults to shipping
    payment_method: str = Field(pattern="^(razorpay|upi|cod)$")
    customer_notes: str | None = None
    postal_code_override: str | None = None  # validate a PIN not on the address


class PaymentSessionOut(BaseModel):
    provider: str
    provider_order_id: str
    key_id: str
    amount_paise: int
    currency: str
    order_number: str
    mock: bool
    notes: dict = {}


class OrderItemOut(ORMModel):
    id: str
    product_id: str
    variant_id: str
    product_name: str
    variant_name: str
    sku: str
    product_image_url: str | None
    unit_price_paise: int
    gst_percentage: float
    tax_paise: int
    qty: int
    discount_paise: int
    total_paise: int
    is_preorder: bool
    estimated_fulfillment_note: str | None


class OrderStatusEvent(ORMModel):
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class OrderOut(ORMModel):
    id: str
    number: str
    status: str
    payment_method: str
    payment_status: str
    fulfillment_status: str
    order_source: str
    currency: str
    subtotal_paise: int
    discount_paise: int
    shipping_paise: int
    tax_paise: int
    grand_total_paise: int
    is_preorder: bool
    customer_notes: str | None
    internal_notes: str | None = None
    billing_address: dict
    shipping_address: dict
    items: list[OrderItemOut] = []
    history: list[OrderStatusEvent] = []
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None = None
    cancellation_reason: str | None = None


class GuestPlaceOrderOut(BaseModel):
    order: OrderOut
    message: str = "Order placed successfully. Our team will call you shortly to confirm your order."
    whatsapp_link: str


class PlaceOrderOut(BaseModel):
    order: OrderOut
    payment_session: PaymentSessionOut | None = None
    requires_payment: bool


class StaffOrderLine(BaseModel):
    variant_id: str
    qty: int = Field(ge=1, le=50)


class StaffAddressInput(BaseModel):
    full_name: str
    phone: str
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str
    postal_code: str = Field(pattern=r"^[1-9][0-9]{5}$")
    country: str = "IN"


class StaffOrderCreateRequest(BaseModel):
    customer_id: str | None = None  # existing customer
    new_customer: dict | None = None  # {email, full_name, phone} auto-creates
    order_source: str = Field(pattern="^(whatsapp|instagram|physical_store|staff_manual)$")
    lines: list[StaffOrderLine] = Field(min_length=1)
    shipping_address: StaffAddressInput
    billing_address: StaffAddressInput | None = None
    payment_method: str = Field(pattern="^(cod|razorpay|upi)$", default="cod")
    internal_notes: str | None = None
    customer_notes: str | None = None
    coupon_code: str | None = None


class OrderEditRequest(BaseModel):
    shipping_address: StaffAddressInput | None = None
    billing_address: StaffAddressInput | None = None
    customer_notes: str | None = None
    line_updates: list[dict] | None = None  # [{order_item_id, qty?, variant_id?}]


class CancelRequest(BaseModel):
    reason: str
    note: str | None = None


class CancelDecision(BaseModel):
    approve: bool
    note: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str
    note: str | None = None


class NoteRequest(BaseModel):
    note: str


class CollectPaymentRequest(BaseModel):
    collected: bool = True
    method_note: str | None = None  # cash / upi / bank transfer recorded as metadata
