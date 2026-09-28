"""Local dev signing accounts and their role mapping.

In both chain modes the backend signs transactions itself using well-known local
dev keys (never real keys). These map to the Hardhat default mnemonic accounts.
"""
from __future__ import annotations

from eth_account import Account
from eth_account.signers.local import LocalAccount

from app.config import settings
from app.models.domain import Role


class DevAccounts:
    def __init__(self) -> None:
        self.admin: LocalAccount = Account.from_key(settings.dev_admin_key)
        self.transfer_agent: LocalAccount = Account.from_key(settings.dev_transfer_agent_key)
        self.custodian: LocalAccount = Account.from_key(settings.dev_custodian_key)
        self.auditor: LocalAccount = Account.from_key(settings.dev_auditor_key)
        self.investors: list[LocalAccount] = [
            Account.from_key(k) for k in settings.dev_investor_keys
        ]

        self._by_role: dict[Role, LocalAccount] = {
            Role.ADMIN: self.admin,
            Role.TRANSFER_AGENT: self.transfer_agent,
            Role.CUSTODIAN: self.custodian,
            Role.AUDITOR: self.auditor,
        }
        self._by_address: dict[str, LocalAccount] = {
            a.address.lower(): a for a in self.all_accounts()
        }

    def all_accounts(self) -> list[LocalAccount]:
        return [self.admin, self.transfer_agent, self.custodian, self.auditor, *self.investors]

    def for_role(self, role: Role) -> LocalAccount:
        return self._by_role[role]

    def for_address(self, address: str) -> LocalAccount | None:
        return self._by_address.get(address.lower())

    def role_of(self, address: str) -> Role:
        addr = address.lower()
        for role, acct in self._by_role.items():
            if acct.address.lower() == addr:
                return role
        return Role.INVESTOR

    def demo_users(self) -> dict[str, dict]:
        """Username -> {role, address} for JWT demo login (password = 'demo')."""
        users = {
            "admin": {"role": Role.ADMIN.value, "address": self.admin.address},
            "agent": {"role": Role.TRANSFER_AGENT.value, "address": self.transfer_agent.address},
            "custodian": {"role": Role.CUSTODIAN.value, "address": self.custodian.address},
            "auditor": {"role": Role.AUDITOR.value, "address": self.auditor.address},
        }
        for i, acct in enumerate(self.investors, start=1):
            users[f"investor{i}"] = {"role": Role.INVESTOR.value, "address": acct.address}
        return users
