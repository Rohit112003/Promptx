"""Investor registration, KYC decisions, and investor views."""
from __future__ import annotations

from web3 import Web3

from app.blockchain.contract import ContractGateway
from app.core.errors import NotFoundError
from app.models.domain import KYC_STATUS_NAME, KycStatus
from app.repositories.base import Repository
from app.schemas.investor import (
    InvestorCreate,
    InvestorOut,
    InvestorRegisterResult,
    KycActionResult,
)
from app.services.helpers import hex0x, now_iso, receipt_from


class InvestorService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    @staticmethod
    def _kyc_hash(payload: InvestorCreate) -> bytes:
        """Hash of the off-chain KYC dossier — only this hash goes on chain (no PII)."""
        base = f"{payload.name}|{payload.email or ''}|{payload.jurisdiction}"
        return Web3.keccak(text=base)

    async def register(self, payload: InvestorCreate) -> InvestorRegisterResult:
        kyc_hash = self._kyc_hash(payload)
        rcpt = await self.g.register_investor(payload.address, payload.jurisdiction, kyc_hash)
        await self.repo.upsert_investor({
            "address": payload.address,
            "name": payload.name,
            "email": payload.email,
            "jurisdiction": payload.jurisdiction,
            "kyc_status_code": KycStatus.PENDING.value,
            "kyc_hash": "0x" + kyc_hash.hex(),
            "created_at": now_iso(),
        })
        investor = await self.get_investor(payload.address)
        return InvestorRegisterResult(investor=investor, receipt=receipt_from(rcpt))

    async def approve(self, address: str) -> KycActionResult:
        return await self._kyc_action(address, self.g.approve_kyc, KycStatus.APPROVED)

    async def reject(self, address: str) -> KycActionResult:
        return await self._kyc_action(address, self.g.reject_kyc, KycStatus.REJECTED)

    async def revoke(self, address: str) -> KycActionResult:
        return await self._kyc_action(address, self.g.revoke_kyc, KycStatus.REJECTED)

    async def _kyc_action(self, address, fn, status: KycStatus) -> KycActionResult:
        rcpt = await fn(address)
        prof = await self.repo.get_investor(address) or {"address": address}
        prof["kyc_status_code"] = status.value
        await self.repo.upsert_investor(prof)
        return KycActionResult(address=address, kyc_status=status.name, receipt=receipt_from(rcpt))

    async def get_investor(self, address: str) -> InvestorOut:
        chain = self.g.get_investor(address)
        prof = await self.repo.get_investor(address)
        if not chain["exists"] and not prof:
            raise NotFoundError(f"Investor {address} not found")
        prof = prof or {}
        return InvestorOut(
            address=address,
            name=prof.get("name"),
            email=prof.get("email"),
            jurisdiction=chain["jurisdiction"] or prof.get("jurisdiction", "US"),
            kyc_status=KYC_STATUS_NAME.get(chain["kyc_status"], "NONE"),
            frozen=chain["frozen"],
            exists_on_chain=chain["exists"],
            kyc_hash=hex0x(chain["kyc_hash"]),
            balance=chain["balance"],
            locked=chain["locked"],
            portfolio_value=float(self.g.portfolio_value(address)),
            created_at=prof.get("created_at"),
        )

    async def list_investors(self, kyc_status: int | None, limit: int, offset: int):
        items, total = await self.repo.list_investors(kyc_status, limit, offset)
        out = [await self.get_investor(p["address"]) for p in items]
        return out, total
