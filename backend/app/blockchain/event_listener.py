"""Background event indexer: backfills from block 0, then polls for new events,
storing them in the repository (audit index) and broadcasting over WebSocket."""
from __future__ import annotations

import asyncio
from typing import Any

from hexbytes import HexBytes

from app.blockchain.client import ChainClient
from app.config import settings
from app.core.ws_manager import WsManager
from app.logging_config import get_logger
from app.repositories.base import Repository

log = get_logger("chain.events")

_LAST_BLOCK_META = "last_indexed_block"

# Events we index (contract + relevant OpenZeppelin lifecycle events).
_EVENT_NAMES = [
    "InvestorRegistered", "KycStatusChanged", "InvestorFrozen", "NAVUpdated",
    "OrderCreated", "OrderSettled", "OrderCancelled", "UnitsTransferred",
    "CustodyActionRecorded", "UnitsPurchased", "UnitsRedeemed",
    "Paused", "Unpaused", "RoleGranted", "RoleRevoked",
]


def _jsonify(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, HexBytes)):
        return "0x" + bytes(value).hex()
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    return value


class EventListener:
    def __init__(self, client: ChainClient, repo: Repository, ws: WsManager) -> None:
        self.client = client
        self.repo = repo
        self.ws = ws
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="event-listener")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        try:
            await self.backfill()
        except Exception:
            log.exception("backfill failed")
        while not self._stop.is_set():
            try:
                await self._poll_once()
            except Exception:
                log.exception("event poll failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.event_poll_interval)
            except asyncio.TimeoutError:
                pass

    async def backfill(self) -> None:
        stored = await self.repo.get_meta(_LAST_BLOCK_META)
        from_block = int(stored) + 1 if stored is not None else settings.event_start_block
        latest = await asyncio.to_thread(self.client.latest_block)
        if from_block > latest:
            return
        indexed = await self._index_range(from_block, latest, broadcast=False)
        log.info("backfill complete", extra={"ctx_from": from_block, "ctx_to": latest,
                                             "ctx_indexed": indexed})

    async def _poll_once(self) -> None:
        stored = await self.repo.get_meta(_LAST_BLOCK_META)
        from_block = int(stored) + 1 if stored is not None else settings.event_start_block
        latest = await asyncio.to_thread(self.client.latest_block)
        if from_block > latest:
            return
        await self._index_range(from_block, latest, broadcast=True)

    async def _index_range(self, from_block: int, to_block: int, broadcast: bool) -> int:
        count = 0
        for name in _EVENT_NAMES:
            event = getattr(self.client.contract.events, name, None)
            if event is None:
                continue
            logs = await asyncio.to_thread(
                self._get_logs, event, from_block, to_block
            )
            for entry in logs:
                doc = await self._store(name, entry, broadcast)
                if doc:
                    count += 1
        await self.repo.set_meta(_LAST_BLOCK_META, str(to_block))
        return count

    @staticmethod
    def _get_logs(event, from_block: int, to_block: int) -> list:
        try:
            return list(event.get_logs(from_block=from_block, to_block=to_block))
        except Exception:
            return []

    async def _store(self, name: str, entry, broadcast: bool) -> dict | None:
        tx_hash = "0x" + bytes(entry["transactionHash"]).hex()
        block_number = int(entry["blockNumber"])
        log_index = int(entry["logIndex"])
        try:
            ts = await asyncio.to_thread(self.client.block_timestamp, block_number)
        except Exception:
            ts = None
        doc = {
            "event": name,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "log_index": log_index,
            "timestamp": ts,
            "args": _jsonify(dict(entry["args"])),
        }
        is_new = await self.repo.add_event(doc)
        if is_new and broadcast:
            await self.ws.broadcast(doc)
        return doc if is_new else None
