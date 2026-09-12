"""Aggregate router for /api/v1."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    carts,
    checkout,
    coupons,
    engagement,
    inventory,
    orders,
    payments,
    products,
    returns,
    shipments,
    staff,
    taxonomy,
    users,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(taxonomy.router)
api_router.include_router(products.router)
api_router.include_router(carts.router)
api_router.include_router(checkout.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(shipments.router)
api_router.include_router(inventory.router)
api_router.include_router(returns.router)
api_router.include_router(coupons.router)
api_router.include_router(engagement.router)
api_router.include_router(staff.router)
api_router.include_router(admin.router)
api_router.include_router(webhooks.router)
