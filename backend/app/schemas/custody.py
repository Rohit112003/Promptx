"""Custody hub schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Address, TxReceipt


class CustodyActionCreate(BaseModel):
    action_type: str = Field(description="LOCK | RELEASE | TRANSFER")
    investor: Address
    units: int = Field(ge=0)
    asset_ref: str = Field(max_length=120, description="Asset/ISIN reference")
    reason: str = Field(max_length=280)


class CustodyActionOut(BaseModel):
    id: int
    custodian: Address
    action_type: str
    investor: Address
    units: int
    asset_ref: str
    reason: str
    timestamp: int
    tx_hash: str | None = None
    block_number: int | None = None


class CustodyActionResult(BaseModel):
    action: CustodyActionOut
    receipt: TxReceipt


class CustodyPosition(BaseModel):
    investor: Address
    balance: int
    locked: int
    free: int
