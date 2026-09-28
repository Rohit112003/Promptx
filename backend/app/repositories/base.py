"""Abstract repository interface. The chain is the source of truth; this stores
enriched off-chain profile data, order/custody metadata, and the event index."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Repository(ABC):
    """One interface, two implementations (SQLite, Mongo)."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    @abstractmethod
    async def reset_chain_data(self) -> None:
        """Drop all chain-derived data.

        Used when the connected chain is a different instance from the one this
        store was built against (e.g. CHAIN_MODE=inmemory redeploys a fresh chain
        on every start, so previously indexed events reference transactions that
        no longer exist).
        """

    # ---- investors ----
    @abstractmethod
    async def upsert_investor(self, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get_investor(self, address: str) -> dict | None: ...

    @abstractmethod
    async def list_investors(
        self, kyc_status: int | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]: ...

    # ---- orders ----
    @abstractmethod
    async def upsert_order(self, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get_order(self, order_id: int) -> dict | None: ...

    @abstractmethod
    async def list_orders(
        self, order_type: int | None = None, status: int | None = None,
        investor: str | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list[dict], int]: ...

    # ---- custody ----
    @abstractmethod
    async def add_custody(self, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get_custody(self, action_id: int) -> dict | None: ...

    @abstractmethod
    async def list_custody(
        self, investor: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]: ...

    # ---- events (audit index) ----
    @abstractmethod
    async def add_event(self, doc: dict[str, Any]) -> bool:
        """Idempotent insert keyed on tx_hash:log_index. Returns True if newly stored."""

    @abstractmethod
    async def list_events(
        self, event: str | None = None, from_block: int | None = None,
        to_block: int | None = None, event_type: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[dict], int]: ...

    @abstractmethod
    async def get_events_by_tx(self, tx_hash: str) -> list[dict]: ...

    # ---- meta (indexer bookmarks) ----
    @abstractmethod
    async def get_meta(self, key: str) -> str | None: ...

    @abstractmethod
    async def set_meta(self, key: str, value: str) -> None: ...

    # ---- idempotency ----
    @abstractmethod
    async def get_idempotency(self, key: str) -> dict | None: ...

    @abstractmethod
    async def set_idempotency(self, key: str, value: dict) -> None: ...
