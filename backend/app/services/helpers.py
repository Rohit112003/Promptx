"""Small shared helpers for services."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.common import TxReceipt


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def receipt_from(rcpt: dict) -> TxReceipt:
    return TxReceipt(
        tx_hash=rcpt["tx_hash"],
        block_number=rcpt["block_number"],
        status=rcpt["status"],
        gas_used=rcpt.get("gas_used", 0),
    )


def hex0x(value: str) -> str:
    return value if value.startswith("0x") else "0x" + value
