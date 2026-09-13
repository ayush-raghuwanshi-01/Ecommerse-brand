"""Shipping: PIN-code serviceability, rates, and the courier abstraction.

v1 ships ManualShippingProvider (staff-entered tracking). A courier aggregator
can be added later by implementing ShippingProvider — nothing else changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.commerce import ShippingRule, ShippingRuleKind
from app.models.order import Order
from app.models.returns import Shipment, ShipmentStatus
from app.services import settings_service


@dataclass
class ServiceabilityResult:
    serviceable: bool
    charge_paise: int
    reason: str | None = None
    estimated_delivery_days: str = "5-8"


class ShippingProvider(ABC):
    """Courier abstraction (get rate / serviceability / shipment lifecycle)."""

    @abstractmethod
    def get_shipping_rate(self, db: Session, postal_code: str, state: str, subtotal_paise: int) -> int: ...

    @abstractmethod
    def check_serviceability(self, db: Session, postal_code: str) -> ServiceabilityResult: ...

    @abstractmethod
    def create_shipment(self, db: Session, order: Order, **kwargs) -> Shipment: ...

    @abstractmethod
    def cancel_shipment(self, db: Session, shipment: Shipment) -> Shipment: ...

    @abstractmethod
    def get_tracking_status(self, db: Session, shipment: Shipment) -> str: ...


class ManualShippingProvider(ShippingProvider):
    """Rule-based rates from shipping_rules + manual tracking entries."""

    def check_serviceability(self, db: Session, postal_code: str) -> ServiceabilityResult:
        mode = settings_service.get_setting(db, "pincode_mode") or "denylist"
        rules = db.scalars(select(ShippingRule).where(ShippingRule.is_active.is_(True))).all()
        blocked = [r for r in rules if r.kind == ShippingRuleKind.blocked and r.matches_pincode(postal_code)]
        if blocked:
            return ServiceabilityResult(False, 0, "We do not deliver to this PIN code yet.")
        if mode == "allowlist":
            serviceable = [
                r for r in rules if r.kind == ShippingRuleKind.serviceable and r.matches_pincode(postal_code)
            ]
            if not serviceable:
                return ServiceabilityResult(False, 0, "This PIN code is not in our serviceable list yet.")
        charge = self.get_shipping_rate(db, postal_code, "", 0)
        est = settings_service.get_setting(db, "estimated_delivery_days") or "5-8"
        return ServiceabilityResult(True, charge, None, est)

    def get_shipping_rate(self, db: Session, postal_code: str, state: str, subtotal_paise: int) -> int:
        threshold = settings_service.get_setting(db, "free_shipping_threshold_paise")
        if threshold and subtotal_paise >= threshold:
            return 0
        rules = db.scalars(select(ShippingRule).where(ShippingRule.is_active.is_(True))).all()
        for rule in rules:
            if rule.kind == ShippingRuleKind.rate_pincode and rule.matches_pincode(postal_code):
                return rule.charge_paise or 0
        for rule in rules:
            if rule.kind == ShippingRuleKind.rate_state and state and rule.state == state:
                return rule.charge_paise or 0
        return settings_service.get_setting(db, "default_shipping_charge_paise") or 0

    def create_shipment(
        self,
        db: Session,
        order: Order,
        *,
        provider: str = "manual",
        tracking_number: str | None = None,
        tracking_url: str | None = None,
        direction: str = "forward",
    ) -> Shipment:
        shipment = Shipment(
            order_id=order.id,
            provider=provider,
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            direction=direction,
            status=ShipmentStatus.pending,
        )
        db.add(shipment)
        db.flush()
        return shipment

    def cancel_shipment(self, db: Session, shipment: Shipment) -> Shipment:
        shipment.status = ShipmentStatus.cancelled
        db.flush()
        return shipment

    def get_tracking_status(self, db: Session, shipment: Shipment) -> str:
        return shipment.status.value


def get_provider() -> ShippingProvider:
    return ManualShippingProvider()


def advance_shipment(db: Session, shipment: Shipment, status: ShipmentStatus) -> Shipment:
    shipment.status = status
    now = utcnow()
    if status == ShipmentStatus.picked_up and not shipment.pickup_date:
        shipment.pickup_date = now
    if status in (ShipmentStatus.in_transit, ShipmentStatus.out_for_delivery) and not shipment.shipped_date:
        shipment.shipped_date = shipment.shipped_date or now
    if status == ShipmentStatus.delivered and not shipment.delivered_date:
        shipment.delivered_date = now
    db.flush()
    return shipment
