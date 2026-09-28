"""Investor & KYC schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Address, TxReceipt


class InvestorCreate(BaseModel):
    address: Address
    name: str = Field(min_length=1, max_length=120, description="Off-chain only (PII)")
    email: str | None = Field(default=None, max_length=200)
    jurisdiction: str = Field(default="US", min_length=2, max_length=4)


class InvestorOut(BaseModel):
    address: Address
    name: str | None = None
    email: str | None = None
    jurisdiction: str
    kyc_status: str
    frozen: bool
    exists_on_chain: bool
    kyc_hash: str | None = None
    balance: int
    locked: int
    portfolio_value: float
    created_at: str | None = None


class InvestorRegisterResult(BaseModel):
    investor: InvestorOut
    receipt: TxReceipt


class KycActionResult(BaseModel):
    address: Address
    kyc_status: str
    receipt: TxReceipt
