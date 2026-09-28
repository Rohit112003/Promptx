"""MongoDB (Motor) repository — same interface as SQLite, for richer deployments."""
from __future__ import annotations

from typing import Any

from app.repositories.base import Repository


class MongoRepository(Repository):
    def __init__(self, url: str, db_name: str) -> None:
        self._url = url
        self._db_name = db_name
        self._client = None
        self._db = None

    async def connect(self) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(self._url, serverSelectionTimeoutMS=3000)
        self._db = self._client[self._db_name]
        await self._db.command("ping")
        await self._db.events.create_index("uid", unique=True)
        await self._db.investors.create_index("address", unique=True)
        await self._db.orders.create_index("id", unique=True)
        await self._db.custody.create_index("id", unique=True)

    async def close(self) -> None:
        if self._client:
            self._client.close()

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False

    async def reset_chain_data(self) -> None:
        for name in ("events", "orders", "custody", "investors", "idempotency"):
            await self._db[name].delete_many({})
        await self._db.meta.delete_one({"key": "last_indexed_block"})

    @staticmethod
    def _strip(doc: dict | None) -> dict | None:
        if doc:
            doc.pop("_id", None)
        return doc

    # ---- investors ----
    async def upsert_investor(self, doc: dict[str, Any]) -> None:
        doc = {**doc, "address": doc["address"].lower()}
        await self._db.investors.replace_one({"address": doc["address"]}, doc, upsert=True)

    async def get_investor(self, address: str) -> dict | None:
        return self._strip(await self._db.investors.find_one({"address": address.lower()}))

    async def list_investors(self, kyc_status=None, limit=50, offset=0):
        q: dict = {}
        if kyc_status is not None:
            q["kyc_status_code"] = kyc_status
        total = await self._db.investors.count_documents(q)
        cur = self._db.investors.find(q).sort("address", 1).skip(offset).limit(limit)
        return [self._strip(d) async for d in cur], total

    # ---- orders ----
    async def upsert_order(self, doc: dict[str, Any]) -> None:
        doc = {**doc, "investor": doc["investor"].lower()}
        await self._db.orders.replace_one({"id": int(doc["id"])}, doc, upsert=True)

    async def get_order(self, order_id: int) -> dict | None:
        return self._strip(await self._db.orders.find_one({"id": int(order_id)}))

    async def list_orders(self, order_type=None, status=None, investor=None, limit=50, offset=0):
        q: dict = {}
        if order_type is not None:
            q["order_type_code"] = order_type
        if status is not None:
            q["status_code"] = status
        if investor is not None:
            q["investor"] = investor.lower()
        total = await self._db.orders.count_documents(q)
        cur = self._db.orders.find(q).sort("id", -1).skip(offset).limit(limit)
        return [self._strip(d) async for d in cur], total

    # ---- custody ----
    async def add_custody(self, doc: dict[str, Any]) -> None:
        doc = {**doc, "investor": doc["investor"].lower()}
        await self._db.custody.replace_one({"id": int(doc["id"])}, doc, upsert=True)

    async def get_custody(self, action_id: int) -> dict | None:
        return self._strip(await self._db.custody.find_one({"id": int(action_id)}))

    async def list_custody(self, investor=None, limit=50, offset=0):
        q: dict = {}
        if investor is not None:
            q["investor"] = investor.lower()
        total = await self._db.custody.count_documents(q)
        cur = self._db.custody.find(q).sort("id", -1).skip(offset).limit(limit)
        return [self._strip(d) async for d in cur], total

    # ---- events ----
    async def add_event(self, doc: dict[str, Any]) -> bool:
        doc = {**doc, "uid": f"{doc['tx_hash']}:{doc['log_index']}"}
        res = await self._db.events.update_one(
            {"uid": doc["uid"]}, {"$setOnInsert": doc}, upsert=True
        )
        return res.upserted_id is not None

    async def list_events(self, event=None, from_block=None, to_block=None,
                          event_type=None, limit=50, offset=0):
        q: dict = {}
        if event is not None:
            q["event"] = event
        if from_block is not None or to_block is not None:
            q["block_number"] = {}
            if from_block is not None:
                q["block_number"]["$gte"] = from_block
            if to_block is not None:
                q["block_number"]["$lte"] = to_block
        total = await self._db.events.count_documents(q)
        cur = (self._db.events.find(q).sort([("block_number", -1), ("log_index", -1)])
               .skip(offset).limit(limit))
        return [self._strip(d) async for d in cur], total

    async def get_events_by_tx(self, tx_hash: str) -> list[dict]:
        cur = self._db.events.find({"tx_hash": tx_hash}).sort("log_index", 1)
        return [self._strip(d) async for d in cur]

    # ---- meta ----
    async def get_meta(self, key: str) -> str | None:
        doc = await self._db.meta.find_one({"key": key})
        return doc["value"] if doc else None

    async def set_meta(self, key: str, value: str) -> None:
        await self._db.meta.replace_one({"key": key}, {"key": key, "value": value}, upsert=True)

    # ---- idempotency ----
    async def get_idempotency(self, key: str) -> dict | None:
        doc = await self._db.idempotency.find_one({"key": key})
        return doc["value"] if doc else None

    async def set_idempotency(self, key: str, value: dict) -> None:
        await self._db.idempotency.update_one(
            {"key": key}, {"$setOnInsert": {"key": key, "value": value}}, upsert=True
        )
