"""Order lifecycle: transactional checkout, staff orders, edits, cancellations,
status transitions, reservation expiry sweep.

Checkout runs in a single DB transaction with conditional-update stock guards so
concurrent checkouts can never oversell.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import utcnow
from app.core.exceptions import (
    InsufficientStockError,
    NotFoundError,
    PermissionDeniedError,
    PolicyError,
    PriceChangedError,
    ValidationError,
)
from app.models.cart import Cart
from app.models.commerce import Coupon
from app.models.order import (
    CancellationReason,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    OrderStatusHistory,
    PACKED_AND_BEYOND,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import Address, User
from app.services import (
    audit_service,
    cart_service,
    coupon_service,
    inventory_service,
    notification_service,
    pricing_service,
    settings_service,
    shipping_service,
)
from app.services.pricing_service import PricedLine

FULFILLMENT_CHAIN = [
    OrderStatus.confirmed,
    OrderStatus.processing,
    OrderStatus.packed,
    OrderStatus.shipped,
    OrderStatus.delivered,
    OrderStatus.completed,
]


def next_order_number(db: Session) -> str:
    from sqlalchemy import update as sa_update

    from app.models.commerce import Counter

    prefix = settings_service.get_setting(db, "order_number_prefix") or "BH"
    db.execute(
        sa_update(Counter).where(Counter.name == "order").values(value=Counter.value + 1)
    )
    row = db.get(Counter, "order")
    if row is None:
        db.add(Counter(name="order", value=1))
        db.flush()
        seq = 1
    else:
        seq = row.value
    return f"{prefix}-{seq:05d}"


def _snapshot_lines(db: Session, lines: list[PricedLine], coupon: Coupon | None, discount: int):
    """Validate availability + price stability; return priced lines ready to persist."""
    issues = []
    for ln in lines:
        variant = ln.variant
        if not ln.is_preorder and variant.available_qty < ln.qty:
            issues.append(
                {
                    "sku": variant.sku,
                    "requested": ln.qty,
                    "available": variant.available_qty,
                }
            )
        snapshot = ln.extra.get("snapshot_price")
        if snapshot is not None and snapshot != variant.price_paise:
            raise PriceChangedError(
                "Prices changed since this cart was last reviewed. Please confirm the new totals.",
                details={
                    "changes": [
                        {
                            "sku": variant.sku,
                            "was_paise": snapshot,
                            "now_paise": variant.price_paise,
                        }
                    ]
                },
            )
    if issues:
        raise InsufficientStockError(
            "Some items are no longer available in the requested quantity.",
            details={"items": issues},
        )
    return lines


def _address_snapshot(db: Session, user: User, address_id: str | None, fallback: dict | None) -> dict:
    if fallback is not None:
        return dict(fallback)
    if address_id is None:
        raise ValidationError("A shipping address is required.")
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise NotFoundError("Address not found.")
    return address.snapshot()


def _create_order_record(
    db: Session,
    *,
    customer: User | None,
    staff: User | None,
    source: OrderSource,
    lines: list[PricedLine],
    totals: dict,
    coupon: Coupon | None,
    payment_method: PaymentMethod,
    shipping_snap: dict,
    billing_snap: dict,
    customer_notes: str | None,
    internal_notes: str | None,
) -> Order:
    order = Order(
        number=next_order_number(db),
        customer_id=customer.id if customer else None,
        created_by_staff_id=staff.id if staff else None,
        order_source=source,
        payment_method=payment_method,
        payment_status=PaymentStatus.pending_cod if payment_method == PaymentMethod.cod else PaymentStatus.created,
        status=OrderStatus.confirmed if payment_method == PaymentMethod.cod else OrderStatus.pending_payment,
        currency=totals["currency"],
        subtotal_paise=totals["subtotal_paise"],
        discount_paise=totals["discount_paise"],
        shipping_paise=totals["shipping_paise"],
        tax_paise=totals["tax_paise"],
        grand_total_paise=totals["grand_total_paise"],
        coupon_id=coupon.id if coupon else None,
        billing_address=billing_snap,
        shipping_address=shipping_snap,
        customer_notes=customer_notes,
        internal_notes=internal_notes,
        is_preorder=any(ln.is_preorder for ln in lines),
        confirmed_at=utcnow() if payment_method == PaymentMethod.cod else None,
    )
    db.add(order)
    db.flush()

    for ln in lines:
        variant = ln.variant
        product = variant.product
        primary = next((i for i in product.images if i.is_primary), None)
        image = primary or (product.images[0] if product.images else None)
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                variant_id=variant.id,
                product_name=product.name,
                variant_name=f"Size {variant.size.value}",
                sku=variant.sku,
                product_image_url=image.url if image else None,
                unit_price_paise=ln.unit_price_paise,
                gst_percentage=float(variant.gst_percentage),
                tax_paise=ln.tax_paise,
                qty=ln.qty,
                discount_paise=ln.discount_paise,
                total_paise=ln.total_paise,
                is_preorder=ln.is_preorder,
                estimated_fulfillment_note=product.preorder_fulfillment_note if ln.is_preorder else None,
            )
        )
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status=order.status.value,
            changed_by=staff.id if staff else (customer.id if customer else None),
            note="order created",
        )
    )
    return order


def _reserve_all(db: Session, order: Order, lines: list[PricedLine]) -> None:
    ttl = settings_service.get_setting(db, "reservation_ttl_minutes") or 30
    for ln in lines:
        inventory_service.reserve(
            db, ln.variant, ln.qty, reference_id=order.id, is_preorder_line=ln.is_preorder
        )
    if order.payment_method != PaymentMethod.cod:
        order.reserved_until = utcnow() + timedelta(minutes=ttl)


def place_order(
    db: Session,
    *,
    customer: User,
    cart: Cart,
    shipping_address_id: str,
    billing_address_id: str | None,
    payment_method: str,
    customer_notes: str | None = None,
    source: OrderSource = OrderSource.website,
    staff: User | None = None,
) -> Order:
    """Steps 1-19 of the checkout contract, in one transaction."""
    if not cart.items:
        raise ValidationError("Your cart is empty.")

    shipping_snap = _address_snapshot(db, customer, shipping_address_id, None)
    billing_snap = (
        _address_snapshot(db, customer, billing_address_id, None)
        if billing_address_id
        else dict(shipping_snap)
    )

    provider = shipping_service.get_provider()
    serviceability = provider.check_serviceability(db, shipping_snap["postal_code"])
    if not serviceability.serviceable:
        raise PolicyError(
            serviceability.reason or "Address not serviceable.",
            details={"postal_code": shipping_snap["postal_code"]},
        )

    lines = cart_service.build_lines(db, cart)
    _snapshot_lines(db, lines, None, 0)

    coupon = cart_service.coupon_for(db, cart)
    discount = 0
    if coupon:
        discount = coupon_service.validate_coupon(db, coupon, lines, customer_id=customer.id)

    shipping_charge = provider.get_shipping_rate(
        db, shipping_snap["postal_code"], shipping_snap.get("state", ""), sum(
            ln.line_gross_paise for ln in lines
        )
    )
    totals = pricing_service.finalize(lines, discount_paise=discount, shipping_paise=shipping_charge)

    order = _create_order_record(
        db,
        customer=customer,
        staff=staff,
        source=source,
        lines=lines,
        totals=totals,
        coupon=coupon,
        payment_method=PaymentMethod(payment_method),
        shipping_snap=shipping_snap,
        billing_snap=billing_snap,
        customer_notes=customer_notes,
        internal_notes=None,
    )
    _reserve_all(db, order, lines)

    from app.models.payment import Payment, PaymentProvider
    from app.core.config import settings as env_settings

    db.add(
        Payment(
            order_id=order.id,
            provider=PaymentProvider.razorpay if env_settings.razorpay_enabled else PaymentProvider.mock,
            amount_paise=totals["grand_total_paise"],
            method=payment_method,
            status=_created_status(),
        )
    )
    if coupon:
        coupon_service.record_usage(db, coupon, order.id, customer.id)

    cart_service.clear_cart(db, customer)
    db.flush()

    notification_service.notify(
        db,
        event_type="order_placed",
        recipient=customer.email,
        payload={"subject": f"Order {order.number} received", "order_number": order.number,
                 "total_paise": order.grand_total_paise},
    )
    return order


def _cod_status():
    from app.models.payment import PaymentRecordStatus

    return PaymentRecordStatus.created


def _created_status():
    from app.models.payment import PaymentRecordStatus

    return PaymentRecordStatus.created


def staff_create_order(
    db: Session,
    *,
    staff: User,
    customer: User | None,
    new_customer: dict | None,
    source: OrderSource,
    lines_spec: list[dict],
    shipping_address: dict,
    billing_address: dict | None,
    payment_method: str,
    internal_notes: str | None,
    customer_notes: str | None,
    coupon_code: str | None,
) -> Order:
    if customer is None and new_customer:
        from app.services.auth_service import create_customer_record

        customer = create_customer_record(
            db,
            email=new_customer["email"],
            full_name=new_customer.get("full_name", shipping_address["full_name"]),
            phone=new_customer.get("phone"),
        )
    if customer is None:
        raise ValidationError("Provide customer_id or new_customer.")

    lines: list[PricedLine] = []
    for spec in lines_spec:
        variant = inventory_service.get_variant(db, spec["variant_id"])
        if variant.product is None or not variant.product.publicly_visible:
            if variant.product is None or variant.product.status.value == "archived":
                raise ValidationError("Archived products cannot be ordered.", details={"sku": variant.sku})
        lines.append(
            PricedLine(
                variant=variant,
                qty=spec["qty"],
                unit_price_paise=variant.price_paise,
                is_preorder=bool(variant.is_preorder or variant.product.preorder_open),
                extra={"snapshot_price": variant.price_paise},
            )
        )
    _snapshot_lines(db, lines, None, 0)

    coupon = coupon_service.get_coupon_by_code(db, coupon_code) if coupon_code else None
    discount = 0
    if coupon:
        discount = coupon_service.validate_coupon(db, coupon, lines, customer_id=customer.id)

    provider = shipping_service.get_provider()
    svc = provider.check_serviceability(db, shipping_address["postal_code"])
    if not svc.serviceable:
        raise PolicyError(svc.reason or "Address not serviceable.")
    shipping_charge = provider.get_shipping_rate(
        db, shipping_address["postal_code"], shipping_address.get("state", ""),
        sum(ln.line_gross_paise for ln in lines),
    )
    totals = pricing_service.finalize(lines, discount_paise=discount, shipping_paise=shipping_charge)

    order = _create_order_record(
        db,
        customer=customer,
        staff=staff,
        source=source,
        lines=lines,
        totals=totals,
        coupon=coupon,
        payment_method=PaymentMethod(payment_method),
        shipping_snap=dict(shipping_address),
        billing_snap=dict(billing_address or shipping_address),
        customer_notes=customer_notes,
        internal_notes=internal_notes,
    )
    _reserve_all(db, order, lines)

    from app.core.config import settings as env_settings
    from app.models.payment import Payment, PaymentProvider

    db.add(
        Payment(
            order_id=order.id,
            provider=PaymentProvider.razorpay if env_settings.razorpay_enabled else PaymentProvider.mock,
            amount_paise=totals["grand_total_paise"],
            method=payment_method,
            status=_cod_status() if payment_method == "cod" else _created_status(),
        )
    )
    if coupon:
        coupon_service.record_usage(db, coupon, order.id, customer.id)
    db.flush()

    audit_service.record(
        db, user=staff, action="order.create_staff", entity_type="order", entity_id=order.id,
        after={"number": order.number, "source": source.value, "total": totals["grand_total_paise"]},
    )
    notification_service.notify(
        db, event_type="order_placed", recipient=customer.email,
        payload={"subject": f"Order {order.number} received", "order_number": order.number},
    )
    return order


# ── Status transitions ──────────────────────────────────────────────────────

def _commit_stock_for(db: Session, order: Order) -> None:
    for item in order.items:
        variant = inventory_service.get_variant(db, item.variant_id)
        inventory_service.commit_reservation(
            db, variant, item.qty, reference_id=order.id, is_preorder_line=item.is_preorder
        )


def _release_stock_for(db: Session, order: Order) -> None:
    for item in order.items:
        variant = inventory_service.get_variant(db, item.variant_id)
        inventory_service.release(db, variant, item.qty, reference_id=order.id)


def set_status(
    db: Session,
    order: Order,
    new_status: OrderStatus,
    *,
    actor: User,
    note: str | None = None,
) -> Order:
    old = order.status
    is_staff_only = actor.role.value in ("staff",)
    if new_status == old:
        return order

    if new_status in FULFILLMENT_CHAIN and old in FULFILLMENT_CHAIN:
        if FULFILLMENT_CHAIN.index(new_status) != FULFILLMENT_CHAIN.index(old) + 1:
            raise ValidationError(
                "Invalid status transition.",
                details={"from": old.value, "to": new_status.value},
            )
        if is_staff_only and old in PACKED_AND_BEYOND:
            raise PermissionDeniedError("Staff cannot move orders after packing; manager approval required.")

    # COD stock commits when staff confirm fulfillment start (confirmed → processing)
    if (
        old == OrderStatus.confirmed
        and new_status == OrderStatus.processing
        and order.payment_method == PaymentMethod.cod
        and order.payment_status == PaymentStatus.pending_cod
    ):
        _commit_stock_for(db, order)

    if new_status == OrderStatus.shipped:
        from app.models.returns import Shipment

        shipment = db.scalar(select(Shipment).where(Shipment.order_id == order.id, Shipment.direction == "forward"))
        if shipment is None:
            shipping_service.get_provider().create_shipment(db, order)

    if new_status == OrderStatus.delivered:
        order.delivered_at = utcnow()
        if order.payment_method == PaymentMethod.cod and order.payment_status == PaymentStatus.pending_cod:
            _mark_payment(db, order, PaymentStatus.paid, note="collected on delivery")

    if new_status == OrderStatus.cancelled:
        if old not in (OrderStatus.cancel_requested,) and actor.role.value == "staff":
            if old in PACKED_AND_BEYOND or not (
                settings_service.get_setting(db, "staff_can_cancel_before_packing")
            ):
                raise PermissionDeniedError("Manager approval is required for this cancellation.")
        _release_stock_for(db, order)
        if order.payment_status == PaymentStatus.paid:
            from app.services.refund_service import request_refund

            request_refund(db, order, order.grand_total_paise, actor, reason="order cancelled")

    order.status = new_status
    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=old.value, to_status=new_status.value,
            changed_by=actor.id, note=note,
        )
    )
    if actor.role.value in ("manager", "admin") or new_status in (
        OrderStatus.cancelled, OrderStatus.cancel_requested,
    ):
        audit_service.record(
            db, user=actor, action="order.status_change", entity_type="order", entity_id=order.id,
            before={"status": old.value}, after={"status": new_status.value, "note": note},
        )
    _notify_status(db, order, new_status)
    db.flush()
    return order


def _mark_payment(db: Session, order: Order, status: PaymentStatus, note: str | None = None) -> None:
    from app.models.payment import Payment

    payment = db.scalar(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc())
    )
    if payment:
        payment.status = status.value
        meta = dict(payment.metadata_json or {})
        if note:
            meta["note"] = note
        payment.metadata_json = meta
    order.payment_status = status
    db.flush()


def _notify_status(db: Session, order: Order, status: OrderStatus) -> None:
    customer = order.customer
    if not customer:
        return
    mapping = {
        OrderStatus.packed: "order_packed",
        OrderStatus.shipped: "order_shipped",
        OrderStatus.delivered: "order_delivered",
        OrderStatus.cancelled: "cancellation_approved",
    }
    event = mapping.get(status)
    if event:
        notification_service.notify(
            db, event_type=event, recipient=customer.email,
            payload={"order_number": order.number, "subject": f"Order {order.number} update"},
        )


def request_cancellation(db: Session, order: Order, *, actor: User, reason: str, note: str | None) -> Order:
    if order.status in PACKED_AND_BEYOND:
        raise PolicyError("Orders cannot be cancelled after packing. Please request a return after delivery.")
    if order.status in (OrderStatus.cancel_requested, OrderStatus.cancelled):
        raise ValidationError("This order is already in a cancellation flow.")
    order.status = OrderStatus.cancel_requested
    order.cancellation_reason = CancellationReason(reason)
    order.cancellation_requested_by = actor.id
    order.cancellation_requested_at = utcnow()
    order.cancellation_decision_note = note
    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=None, to_status=OrderStatus.cancel_requested.value,
            changed_by=actor.id, note=note or reason,
        )
    )
    audit_service.record(
        db, user=actor, action="order.cancel_request", entity_type="order", entity_id=order.id,
        after={"reason": reason, "note": note},
    )
    db.flush()
    return order


def decide_cancellation(db: Session, order: Order, *, approver: User, approve: bool, note: str | None) -> Order:
    if order.status != OrderStatus.cancel_requested:
        raise ValidationError("Order has no pending cancellation request.")
    if approve:
        set_status(db, order, OrderStatus.cancelled, actor=approver, note=note or "cancellation approved")
        audit_service.record(
            db, user=approver, action="order.cancel_approve", entity_type="order", entity_id=order.id,
            after={"note": note},
        )
    else:
        prior = db.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order.id)
            .where(OrderStatusHistory.to_status != OrderStatus.cancel_requested.value)
            .order_by(OrderStatusHistory.created_at.desc())
        ).first()
        restored = OrderStatus(prior.to_status) if prior else OrderStatus.confirmed
        from_status = order.status
        order.status = restored
        order.cancellation_decision_note = note
        db.add(
            OrderStatusHistory(
                order_id=order.id, from_status=from_status.value,
                to_status=restored.value, changed_by=approver.id, note=note or "cancellation rejected",
            )
        )
        audit_service.record(
            db, user=approver, action="order.cancel_reject", entity_type="order", entity_id=order.id,
            after={"note": note},
        )
        if order.customer:
            notification_service.notify(
                db, event_type="cancellation_rejected", recipient=order.customer.email,
                payload={"order_number": order.number},
            )
    db.flush()
    return order


def edit_order(db: Session, order: Order, *, actor: User, changes: dict) -> Order:
    """Controlled post-placement edits. Never silent: audit + history always."""
    before = {
        "shipping_address": order.shipping_address,
        "billing_address": order.billing_address,
        "customer_notes": order.customer_notes,
        "items": [(i.sku, i.qty) for i in order.items],
    }
    packed = order.status in PACKED_AND_BEYOND
    if packed and actor.role.value not in ("manager", "admin"):
        raise PermissionDeniedError("Only managers/admins can edit orders after packing.")

    if changes.get("shipping_address"):
        order.shipping_address = dict(changes["shipping_address"])
    if changes.get("billing_address"):
        order.billing_address = dict(changes["billing_address"])
    if "customer_notes" in changes:
        order.customer_notes = changes["customer_notes"]

    for line_change in changes.get("line_updates") or []:
        item = db.get(OrderItem, line_change["order_item_id"])
        if item is None or item.order_id != order.id:
            raise NotFoundError("Order item not found.")
        variant = inventory_service.get_variant(db, item.variant_id)
        new_qty = line_change.get("qty", item.qty)
        new_variant = inventory_service.get_variant(db, line_change["variant_id"]) if line_change.get("variant_id") else variant
        delta = new_qty - item.qty
        if delta > 0:
            inventory_service.reserve(
                db, new_variant, delta, reference_id=order.id, is_preorder_line=item.is_preorder
            )
        elif delta < 0:
            inventory_service.release(db, variant, -delta, reference_id=order.id)
        if new_variant is not variant:
            item.variant_id = new_variant.id
            item.sku = new_variant.sku
            item.variant_name = f"Size {new_variant.size.value}"
            item.unit_price_paise = new_variant.price_paise
            item.gst_percentage = float(new_variant.gst_percentage)
        item.qty = new_qty
        item.total_paise = item.unit_price_paise * new_qty - item.discount_paise
        item.tax_paise = pricing_service.line_tax_paise(item.total_paise, item.gst_percentage)

    if changes.get("line_updates") or changes.get("shipping_address"):
        # recalculate totals from current item rows
        subtotal = sum(i.unit_price_paise * i.qty for i in order.items)
        discount = order.discount_paise
        shipping = order.shipping_paise
        if changes.get("shipping_address"):
            shipping = shipping_service.get_provider().get_shipping_rate(
                db, order.shipping_address["postal_code"], order.shipping_address.get("state", ""), subtotal
            )
            order.shipping_paise = shipping
        tax = sum(pricing_service.line_tax_paise(i.total_paise, float(i.gst_percentage)) for i in order.items)
        order.subtotal_paise = subtotal
        order.tax_paise = tax
        order.grand_total_paise = subtotal - discount + shipping

    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=order.status.value, to_status=order.status.value,
            changed_by=actor.id, note="order edited",
        )
    )
    audit_service.record(
        db, user=actor, action="order.edit", entity_type="order", entity_id=order.id,
        before=before,
        after={
            "shipping_address": order.shipping_address,
            "billing_address": order.billing_address,
            "customer_notes": order.customer_notes,
            "items": [(i.sku, i.qty) for i in order.items],
            "grand_total_paise": order.grand_total_paise,
        },
    )
    db.flush()
    return order


def add_internal_note(db: Session, order: Order, *, actor: User, note: str) -> Order:
    existing = order.internal_notes or ""
    stamp = utcnow().strftime("%Y-%m-%d %H:%M")
    order.internal_notes = f"{existing}\n[{stamp} {actor.full_name}] {note}".strip()
    db.flush()
    return order


def sweep_expired_reservations(db: Session) -> int:
    """Worker tick: unpaid prepaid orders past TTL release their stock."""
    now = utcnow()
    expired = db.scalars(
        select(Order)
        .where(Order.status == OrderStatus.pending_payment, Order.reserved_until.is_not(None))
        .where(Order.reserved_until < now)
        .options(joinedload(Order.items))
    ).unique().all()
    for order in expired:
        _release_stock_for(db, order)
        order.status = OrderStatus.cancelled
        order.payment_status = PaymentStatus.expired
        order.cancellation_reason = CancellationReason.payment_issue
        db.add(
            OrderStatusHistory(
                order_id=order.id, from_status=OrderStatus.pending_payment.value,
                to_status=OrderStatus.cancelled.value, changed_by=None,
                note="payment window expired; reservation released",
            )
        )
    db.flush()
    return len(expired)


def get_order_for_user(db: Session, order_id: str, user: User) -> Order:
    order = db.scalar(
        select(Order).options(joinedload(Order.items), joinedload(Order.history))
        .where(Order.id == order_id)
    )
    if order is None:
        raise NotFoundError("Order not found.")
    if user.role.value == "customer" and order.customer_id != user.id:
        raise NotFoundError("Order not found.")
    return order
