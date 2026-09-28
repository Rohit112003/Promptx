"""Typed high-level wrappers over the contract functions (the on-chain gateway)."""
from __future__ import annotations

from web3 import Web3

from app.blockchain.client import ChainClient
from app.core.errors import ForbiddenError
from app.models.domain import CustodyActionType, Role


class ContractGateway:
    """Signer-aware, typed access to the TokenisedFundServicing contract."""

    def __init__(self, client: ChainClient) -> None:
        self.client = client

    @property
    def c(self):
        return self.client.contract

    def _signer_for_address(self, address: str):
        acct = self.client.accounts.for_address(address)
        if acct is None:
            raise ForbiddenError(
                f"No local signing key for {address}. This demo can only sign for the "
                "well-known dev accounts (see /admin/roles and the seeded investors).",
                code="no_signing_key",
            )
        return acct

    def _agent(self):
        return self.client.accounts.for_role(Role.TRANSFER_AGENT)

    def _custodian(self):
        return self.client.accounts.for_role(Role.CUSTODIAN)

    def _admin(self):
        return self.client.accounts.for_role(Role.ADMIN)

    # ---------- KYC / investor (transfer agent) ----------
    async def register_investor(self, address: str, jurisdiction: str, kyc_hash: bytes) -> dict:
        fn = self.c.functions.registerInvestor(address, jurisdiction, kyc_hash)
        return await self.client.send(fn, self._agent())

    async def approve_kyc(self, address: str) -> dict:
        return await self.client.send(self.c.functions.approveKyc(address), self._agent())

    async def reject_kyc(self, address: str) -> dict:
        return await self.client.send(self.c.functions.rejectKyc(address), self._agent())

    async def revoke_kyc(self, address: str) -> dict:
        return await self.client.send(self.c.functions.revokeKyc(address), self._agent())

    async def set_frozen(self, address: str, frozen: bool) -> dict:
        return await self.client.send(self.c.functions.setFrozen(address, frozen), self._agent())

    # ---------- NAV (transfer agent) ----------
    async def update_nav(self, new_nav: int) -> dict:
        return await self.client.send(self.c.functions.updateNAV(new_nav), self._agent())

    # ---------- orders ----------
    async def create_subscription(self, investor: str, units: int) -> tuple[dict, int]:
        signer = self._signer_for_address(investor)
        rcpt = await self.client.send(self.c.functions.createSubscriptionOrder(units), signer)
        return rcpt, self._order_id_from(rcpt)

    async def create_redemption(self, investor: str, units: int) -> tuple[dict, int]:
        signer = self._signer_for_address(investor)
        rcpt = await self.client.send(self.c.functions.createRedemptionOrder(units), signer)
        return rcpt, self._order_id_from(rcpt)

    async def settle_order(self, order_id: int) -> dict:
        return await self.client.send(self.c.functions.settleOrder(order_id), self._agent())

    async def cancel_order(self, order_id: int, by_address: str) -> dict:
        signer = self._signer_for_address(by_address)
        return await self.client.send(self.c.functions.cancelOrder(order_id), signer)

    def _order_id_from(self, rcpt: dict) -> int:
        logs = self.c.events.OrderCreated().process_receipt(rcpt["receipt"])
        return int(logs[0]["args"]["orderId"]) if logs else 0

    # ---------- transfers ----------
    async def transfer_units(self, frm: str, to: str, units: int) -> dict:
        signer = self._signer_for_address(frm)
        return await self.client.send(self.c.functions.transferUnits(to, units), signer)

    # ---------- custody ----------
    async def record_custody(
        self, action_type: CustodyActionType, investor: str, units: int,
        asset_ref: str, reason: str,
    ) -> tuple[dict, int]:
        fn = self.c.functions.recordCustodyAction(
            int(action_type), investor, units, asset_ref, reason
        )
        rcpt = await self.client.send(fn, self._custodian())
        logs = self.c.events.CustodyActionRecorded().process_receipt(rcpt["receipt"])
        action_id = int(logs[0]["args"]["actionId"]) if logs else 0
        return rcpt, action_id

    # ---------- admin ----------
    async def pause(self) -> dict:
        return await self.client.send(self.c.functions.pause(), self._admin())

    async def unpause(self) -> dict:
        return await self.client.send(self.c.functions.unpause(), self._admin())

    # ---------- reads ----------
    def get_investor(self, address: str) -> dict:
        (exists, kyc, frozen, juris, kyc_hash, balance, locked) = self.client.read(
            self.c.functions.getInvestor(address)
        )
        return {
            "exists": exists,
            "kyc_status": int(kyc),
            "frozen": frozen,
            "jurisdiction": juris,
            "kyc_hash": kyc_hash.hex() if isinstance(kyc_hash, (bytes, bytearray)) else str(kyc_hash),
            "balance": int(balance),
            "locked": int(locked),
        }

    def portfolio_value(self, address: str) -> int:
        return int(self.client.read(self.c.functions.portfolioValue(address)))

    def unit_price(self) -> int:
        return int(self.client.read(self.c.functions.unitPrice()))

    def fund_status(self) -> dict:
        name, nav, supply, price, total = self.client.read(self.c.functions.getFundStatus())
        paused = bool(self.client.read(self.c.functions.paused()))
        return {
            "fund_name": name,
            "nav_total": int(nav),
            "total_supply": int(supply),
            "unit_price": int(price),
            "total_value": int(total),
            "paused": paused,
            "contract_address": self.client.address,
        }

    def get_order(self, order_id: int) -> dict:
        o = self.client.read(self.c.functions.getOrder(order_id))
        return {
            "id": int(o[0]), "investor": o[1], "order_type": int(o[2]), "status": int(o[3]),
            "units": int(o[4]), "created_at": int(o[5]), "settled_at": int(o[6]),
            "settled_unit_price": int(o[7]),
        }

    def transaction_count(self, address: str) -> int:
        return int(self.client.read(self.c.functions.transactionCount(address)))

    def get_transactions(self, address: str, offset: int, limit: int) -> list[dict]:
        rows = self.client.read(self.c.functions.getTransactions(address, offset, limit))
        return [
            {"type": r[0], "units": int(r[1]), "unit_price": int(r[2]), "timestamp": int(r[3])}
            for r in rows
        ]

    def has_role(self, role_name: str, address: str) -> bool:
        role = self.client.read(getattr(self.c.functions, f"{role_name}_ROLE")())
        return bool(self.client.read(self.c.functions.hasRole(role, Web3.to_checksum_address(address))))
