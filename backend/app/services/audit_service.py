"""Audit: expose the indexed on-chain event log and verify off-chain vs chain."""
from __future__ import annotations

import asyncio

from app.blockchain.contract import ContractGateway
from app.repositories.base import Repository
from app.schemas.report import AuditEvent, AuditVerification


class AuditService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    async def list_events(self, event, from_block, to_block, limit, offset):
        docs, total = await self.repo.list_events(
            event=event, from_block=from_block, to_block=to_block, limit=limit, offset=offset
        )
        return [
            AuditEvent(
                event=d["event"], tx_hash=d["tx_hash"], block_number=d["block_number"],
                log_index=d["log_index"], timestamp=d.get("timestamp"), args=d.get("args", {}),
            )
            for d in docs
        ], total

    async def verify(self, tx_hash: str) -> AuditVerification:
        off_chain_events = await self.repo.get_events_by_tx(tx_hash)
        off_chain = len(off_chain_events) > 0

        on_chain = False
        detail: dict = {"stored_events": len(off_chain_events)}
        try:
            rcpt = await asyncio.to_thread(
                self.g.client.w3.eth.get_transaction_receipt, tx_hash
            )
            on_chain = rcpt is not None and rcpt.get("status") == 1
            detail["block_number"] = rcpt["blockNumber"]
            detail["on_chain_logs"] = len(rcpt["logs"])
        except Exception as exc:
            detail["error"] = str(exc)

        matches = on_chain and off_chain
        detail["events"] = [e["event"] for e in off_chain_events]
        return AuditVerification(
            tx_hash=tx_hash, on_chain=on_chain, off_chain=off_chain,
            matches=matches, detail=detail,
        )
