"""Health checks across API, chain, and database."""
from __future__ import annotations

import asyncio

from app.blockchain.client import ChainClient
from app.repositories.base import Repository
from app.schemas.report import HealthComponent, HealthResponse


class HealthService:
    def __init__(self, client: ChainClient, repo: Repository) -> None:
        self.client = client
        self.repo = repo

    async def health(self) -> HealthResponse:
        chain_ok = await asyncio.to_thread(self.client.is_connected)
        chain_detail: dict = {"connected": chain_ok, "contract_address": self.client.address}
        if chain_ok:
            try:
                chain_detail["latest_block"] = await asyncio.to_thread(self.client.latest_block)
                chain_detail["chain_id"] = self.client.w3.eth.chain_id
            except Exception as exc:  # pragma: no cover
                chain_ok = False
                chain_detail["error"] = str(exc)

        db_ok = await self.repo.ping()
        overall = "ok" if (chain_ok and db_ok) else "degraded"
        return HealthResponse(
            status=overall,
            api=HealthComponent(status="ok"),
            chain=HealthComponent(status="ok" if chain_ok else "down", detail=chain_detail),
            database=HealthComponent(status="ok" if db_ok else "down"),
        )
