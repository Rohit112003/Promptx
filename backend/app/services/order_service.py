"""Transfer-agency order flow: subscriptions, redemptions, settlement, transfers."""
from __future__ import annotations

from web3 import Web3

from app.blockchain.contract import ContractGateway
from app.models.domain import ORDER_STATUS_NAME, ORDER_TYPE_NAME
from app.repositories.base import Repository
from app.schemas.order import (
    OrderActionResult,
    OrderCreate,
    OrderOut,
    TransferCreate,
    TransferResult,
)
from app.services.helpers import receipt_from


def _order_doc(o: dict, note: str | None, tx_hash: str | None, block: int | None) -> dict:
    return {
        "id": o["id"],
        "investor": Web3.to_checksum_address(o["investor"]),
        "order_type": ORDER_TYPE_NAME[o["order_type"]],
        "order_type_code": o["order_type"],
        "status": ORDER_STATUS_NAME[o["status"]],
        "status_code": o["status"],
        "units": o["units"],
        "created_at": o["created_at"],
        "settled_at": o["settled_at"],
        "settled_unit_price": o["settled_unit_price"],
        "note": note,
        "tx_hash": tx_hash,
        "block_number": block,
    }


class OrderService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    async def subscribe(self, payload: OrderCreate, idem_key: str | None) -> OrderActionResult:
        cached = await self._check_idem(idem_key)
        if cached:
            return cached
        rcpt, order_id = await self.g.create_subscription(payload.investor, payload.units)
        result = await self._refresh(order_id, rcpt, note=payload.note)
        await self._store_idem(idem_key, result)
        return result

    async def redeem(self, payload: OrderCreate, idem_key: str | None) -> OrderActionResult:
        cached = await self._check_idem(idem_key)
        if cached:
            return cached
        rcpt, order_id = await self.g.create_redemption(payload.investor, payload.units)
        result = await self._refresh(order_id, rcpt, note=payload.note)
        await self._store_idem(idem_key, result)
        return result

    async def settle(self, order_id: int) -> OrderActionResult:
        rcpt = await self.g.settle_order(order_id)
        return await self._refresh(order_id, rcpt)

    async def cancel(self, order_id: int) -> OrderActionResult:
        chain = self.g.get_order(order_id)  # raises OrderNotFound if absent
        rcpt = await self.g.cancel_order(order_id, chain["investor"])
        return await self._refresh(order_id, rcpt)

    async def get_order(self, order_id: int) -> OrderOut:
        o = self.g.get_order(order_id)
        existing = await self.repo.get_order(order_id) or {}
        doc = _order_doc(o, existing.get("note"), existing.get("tx_hash"),
                         existing.get("block_number"))
        return OrderOut(**doc)

    async def list_orders(self, order_type, status, investor, limit, offset):
        items, total = await self.repo.list_orders(order_type, status, investor, limit, offset)
        return [OrderOut(**d) for d in items], total

    async def transfer(self, payload: TransferCreate) -> TransferResult:
        rcpt = await self.g.transfer_units(
            payload.from_address, payload.to_address, payload.units
        )
        return TransferResult(
            from_address=payload.from_address,
            to_address=payload.to_address,
            units=payload.units,
            receipt=receipt_from(rcpt),
        )

    # ---- internals ----
    async def _refresh(self, order_id: int, rcpt: dict, note: str | None = None) -> OrderActionResult:
        o = self.g.get_order(order_id)
        existing = await self.repo.get_order(order_id) or {}
        doc = _order_doc(
            o,
            note=note if note is not None else existing.get("note"),
            tx_hash=rcpt["tx_hash"],
            block=rcpt["block_number"],
        )
        await self.repo.upsert_order(doc)
        return OrderActionResult(order=OrderOut(**doc), receipt=receipt_from(rcpt))

    async def _check_idem(self, idem_key: str | None) -> OrderActionResult | None:
        if not idem_key:
            return None
        cached = await self.repo.get_idempotency(f"order:{idem_key}")
        return OrderActionResult(**cached) if cached else None

    async def _store_idem(self, idem_key: str | None, result: OrderActionResult) -> None:
        if idem_key:
            await self.repo.set_idempotency(f"order:{idem_key}", result.model_dump())
