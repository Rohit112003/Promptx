"""Enums that mirror the on-chain contract and the RBAC roles."""
from __future__ import annotations

from enum import Enum, IntEnum


class KycStatus(IntEnum):
    """Mirrors the contract KycStatus enum."""

    NONE = 0
    PENDING = 1
    APPROVED = 2
    REJECTED = 3


class OrderType(IntEnum):
    SUBSCRIPTION = 0
    REDEMPTION = 1


class OrderStatus(IntEnum):
    PENDING = 0
    SETTLED = 1
    CANCELLED = 2


class CustodyActionType(IntEnum):
    LOCK = 0
    RELEASE = 1
    TRANSFER = 2


class Role(str, Enum):
    """RBAC roles mapped 1:1 to on-chain AccessControl roles."""

    ADMIN = "ADMIN"
    TRANSFER_AGENT = "TRANSFER_AGENT"
    CUSTODIAN = "CUSTODIAN"
    AUDITOR = "AUDITOR"
    INVESTOR = "INVESTOR"


# Convenience reverse maps for serialisation.
KYC_STATUS_NAME = {s.value: s.name for s in KycStatus}
ORDER_TYPE_NAME = {t.value: t.name for t in OrderType}
ORDER_STATUS_NAME = {s.value: s.name for s in OrderStatus}
CUSTODY_TYPE_NAME = {t.value: t.name for t in CustodyActionType}
