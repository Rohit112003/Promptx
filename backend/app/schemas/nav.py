"""NAV / fund schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TxReceipt


class FundStatus(BaseModel):
    fund_name: str
    nav_total: int
    total_supply: int
    unit_price: int
    total_value: int
    paused: bool
    contract_address: str


class NavUpdate(BaseModel):
    new_nav: int = Field(gt=0, description="New total NAV (PRICE_SCALE-scaled)")


class NavUpdateResult(BaseModel):
    new_nav: int
    unit_price: int
    receipt: TxReceipt


class NavPoint(BaseModel):
    nav_total: int
    unit_price: int
    timestamp: int
    block_number: int
    tx_hash: str
