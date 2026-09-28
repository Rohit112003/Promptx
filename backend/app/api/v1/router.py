"""Aggregate all v1 routers under a single APIRouter."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    audit,
    auth,
    custody,
    health,
    investors,
    kyc,
    nav,
    orders,
    reports,
    transfers,
    ws,
)

api_router = APIRouter()
for module in (health, auth, investors, kyc, orders, nav, transfers, custody, admin,
               reports, audit):
    api_router.include_router(module.router)

# WebSocket route (no prefix beyond /ws).
ws_router = ws.router
