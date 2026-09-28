"""Order (subscription/redemption) and transfer schemas."""
from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field, field_validator
from web3 import Web3

from app.schemas.common import Address, PositiveUnits, TxReceipt


class OrderCreate(BaseModel):
    investor: Address
    units: PositiveUnits
    note: str | None = Field(default=None, max_length=280)


class OrderOut(BaseModel):
    id: int
    investor: Address
    order_type: str
    status: str
    units: int
    created_at: int
    settled_at: int
    settled_unit_price: int
    note: str | None = None
    tx_hash: str | None = None
    block_number: int | None = None


class OrderActionResult(BaseModel):
    order: OrderOut
    receipt: TxReceipt


class TransferCreate(BaseModel):
    model_config = {"populate_by_name": True}

    from_address: str = Field(validation_alias=AliasChoices("from", "from_address"))
    to_address: str = Field(validation_alias=AliasChoices("to", "to_address"))
    units: PositiveUnits

    @field_validator("from_address", "to_address")
    @classmethod
    def _checksum(cls, v: str) -> str:
        if not Web3.is_address(v):
            raise ValueError(f"'{v}' is not a valid Ethereum address")
        return Web3.to_checksum_address(v)


class TransferResult(BaseModel):
    from_address: Address
    to_address: Address
    units: int
    receipt: TxReceipt
