"""Common schema types: addresses, amounts, tx receipts, pagination."""
from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, Field
from web3 import Web3

T = TypeVar("T")


def _to_checksum(value: str) -> str:
    if not Web3.is_address(value):
        raise ValueError(f"'{value}' is not a valid Ethereum address")
    return Web3.to_checksum_address(value)


# A validated, checksummed Ethereum address.
Address = Annotated[str, AfterValidator(_to_checksum)]
# A strictly-positive unit amount.
PositiveUnits = Annotated[int, Field(gt=0, description="Number of fund units (> 0)")]


class TxReceipt(BaseModel):
    """Result of a state-changing chain call."""

    tx_hash: str = Field(description="Transaction hash")
    block_number: int = Field(description="Block the tx was mined in")
    status: str = Field(description="'success' or 'reverted'")
    gas_used: int = 0


class Page(BaseModel, Generic[T]):
    """Generic paginated envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str
