"""Application context: wires the chain client, gateway, repository, and services."""
from __future__ import annotations

from dataclasses import dataclass

from app.blockchain.client import ChainClient
from app.blockchain.contract import ContractGateway
from app.blockchain.event_listener import EventListener
from app.core.ws_manager import WsManager
from app.logging_config import get_logger
from app.repositories.base import Repository

log = get_logger("context")


@dataclass
class AppContext:
    client: ChainClient
    gateway: ContractGateway
    repo: Repository
    ws: WsManager
    listener: EventListener

    # services (populated by the factory)
    investor_service: "object" = None
    order_service: "object" = None
    nav_service: "object" = None
    custody_service: "object" = None
    report_service: "object" = None
    audit_service: "object" = None
    health_service: "object" = None


async def _discard_stale_index(client: ChainClient, repo: Repository) -> None:
    """Clear chain-derived data when the connected chain is not the one we indexed.

    `inmemory` deploys a brand-new chain on every start, so nothing previously
    indexed can still be valid. For a persistent node we reset only when the
    contract address changed (a redeploy) or the node's height went backwards
    (the node was restarted).
    """
    import asyncio

    from app.config import settings

    address = (client.address or "").lower()
    if settings.chain_mode == "inmemory":
        await repo.reset_chain_data()
    else:
        previous = (await repo.get_meta("contract_address") or "").lower()
        bookmark = int(await repo.get_meta("last_indexed_block") or 0)
        latest = await asyncio.to_thread(client.latest_block)
        if (previous and previous != address) or bookmark > latest:
            log.warning("chain instance changed — clearing stale off-chain index",
                        extra={"ctx_previous": previous, "ctx_current": address,
                               "ctx_bookmark": bookmark, "ctx_latest": latest})
            await repo.reset_chain_data()
    await repo.set_meta("contract_address", address)


async def build_context() -> AppContext:
    from app.repositories.factory import build_repository
    from app.services.audit_service import AuditService
    from app.services.custody_service import CustodyService
    from app.services.health_service import HealthService
    from app.services.investor_service import InvestorService
    from app.services.nav_service import NavService
    from app.services.order_service import OrderService
    from app.services.report_service import ReportService

    client = ChainClient()
    await client.connect()
    gateway = ContractGateway(client)
    repo = await build_repository()

    # The off-chain store is only valid for the chain it was built against;
    # otherwise indexed events point at transactions that no longer exist.
    await _discard_stale_index(client, repo)

    ws = WsManager()
    listener = EventListener(client, repo, ws)

    ctx = AppContext(client=client, gateway=gateway, repo=repo, ws=ws, listener=listener)
    ctx.investor_service = InvestorService(gateway, repo)
    ctx.order_service = OrderService(gateway, repo)
    ctx.nav_service = NavService(gateway, repo)
    ctx.custody_service = CustodyService(gateway, repo)
    ctx.report_service = ReportService(gateway, repo)
    ctx.audit_service = AuditService(gateway, repo)
    ctx.health_service = HealthService(client, repo)
    return ctx
