"""Reporting, audit, admin, and health schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.common import Address


class HealthComponent(BaseModel):
    status: str
    detail: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    api: HealthComponent
    chain: HealthComponent
    database: HealthComponent


class InvestorStatement(BaseModel):
    """Dual-format investor statement (traditional + blockchain-native)."""

    format: str  # "traditional" | "blockchain-native"
    investor: dict[str, Any]
    holdings: dict[str, Any]
    transactions: list[dict[str, Any]]
    generated_at: str


class FundSummary(BaseModel):
    fund_name: str
    nav_total: int
    total_supply: int
    unit_price: int
    total_value: int
    investor_count: int
    approved_investors: int
    pending_orders: int
    settled_orders: int
    generated_at: str


class NavPerformancePoint(BaseModel):
    timestamp: int
    unit_price: int
    nav_total: int
    return_pct: float


class AuditEvent(BaseModel):
    event: str
    tx_hash: str
    block_number: int
    log_index: int
    timestamp: int | None = None
    args: dict[str, Any]


class AuditVerification(BaseModel):
    tx_hash: str
    on_chain: bool
    off_chain: bool
    matches: bool
    detail: dict[str, Any]


class RoleHolder(BaseModel):
    role: str
    address: Address
    label: str
