"""Custody hub: record LOCK/RELEASE/TRANSFER actions and report positions."""
from __future__ import annotations

from web3 import Web3

from app.blockchain.contract import ContractGateway
from app.core.errors import ValidationAppError
from app.models.domain import CustodyActionType
from app.repositories.base import Repository
from app.schemas.custody import (
    CustodyActionCreate,
    CustodyActionOut,
    CustodyActionResult,
    CustodyPosition,
)
from app.services.helpers import now_iso, receipt_from


class CustodyService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    async def create_action(self, payload: CustodyActionCreate) -> CustodyActionResult:
        try:
            action_type = CustodyActionType[payload.action_type.upper()]
        except KeyError as exc:
            raise ValidationAppError(
                f"Invalid action_type '{payload.action_type}' (LOCK|RELEASE|TRANSFER)"
            ) from exc

        rcpt, action_id = await self.g.record_custody(
            action_type, payload.investor, payload.units, payload.asset_ref, payload.reason
        )
        doc = {
            "id": action_id,
            "custodian": self.g.client.accounts.custodian.address,
            "action_type": action_type.name,
            "action_type_code": int(action_type),
            "investor": Web3.to_checksum_address(payload.investor),
            "units": payload.units,
            "asset_ref": payload.asset_ref,
            "reason": payload.reason,
            "timestamp": int(rcpt["receipt"]["blockNumber"]),
            "tx_hash": rcpt["tx_hash"],
            "block_number": rcpt["block_number"],
            "recorded_at": now_iso(),
        }
        await self.repo.add_custody(doc)
        return CustodyActionResult(action=CustodyActionOut(**doc), receipt=receipt_from(rcpt))

    async def list_actions(self, investor, limit, offset):
        items, total = await self.repo.list_custody(investor, limit, offset)
        return [CustodyActionOut(**d) for d in items], total

    async def positions(self, limit: int = 200, offset: int = 0):
        investors, total = await self.repo.list_investors(limit=limit, offset=offset)
        out = []
        for prof in investors:
            chain = self.g.get_investor(prof["address"])
            out.append(CustodyPosition(
                investor=Web3.to_checksum_address(prof["address"]),
                balance=chain["balance"],
                locked=chain["locked"],
                free=chain["balance"] - chain["locked"],
            ))
        return out, total
