"""NAV updates, fund status, and NAV history (from indexed events)."""
from __future__ import annotations

from app.blockchain.contract import ContractGateway
from app.repositories.base import Repository
from app.schemas.nav import FundStatus, NavPoint, NavUpdate, NavUpdateResult
from app.services.helpers import receipt_from


class NavService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    def fund_status(self) -> FundStatus:
        return FundStatus(**self.g.fund_status())

    async def update_nav(self, payload: NavUpdate) -> NavUpdateResult:
        rcpt = await self.g.update_nav(payload.new_nav)
        return NavUpdateResult(
            new_nav=payload.new_nav,
            unit_price=self.g.unit_price(),
            receipt=receipt_from(rcpt),
        )

    async def nav_history(self, limit: int = 100, offset: int = 0):
        events, total = await self.repo.list_events(
            event="NAVUpdated", limit=limit, offset=offset
        )
        points = [
            NavPoint(
                nav_total=int(e["args"].get("newNAV", 0)),
                unit_price=int(e["args"].get("unitPrice", 0)),
                timestamp=int(e["args"].get("timestamp", e.get("timestamp") or 0)),
                block_number=e["block_number"],
                tx_hash=e["tx_hash"],
            )
            for e in events
        ]
        return points, total
