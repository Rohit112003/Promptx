"""In-process pub/sub for broadcasting indexed on-chain events to WebSocket clients."""
from __future__ import annotations

import asyncio
from typing import Any


class WsManager:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Drop for slow consumers rather than blocking the indexer.
                pass

    @property
    def client_count(self) -> int:
        return len(self._subscribers)
