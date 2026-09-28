"""SQLite (aiosqlite) repository — the zero-dependency default store."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from app.repositories.base import Repository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS investors (
    address TEXT PRIMARY KEY, kyc_status INTEGER, doc TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY, order_type INTEGER, status INTEGER, investor TEXT, doc TEXT
);
CREATE TABLE IF NOT EXISTS custody (
    id INTEGER PRIMARY KEY, investor TEXT, doc TEXT
);
CREATE TABLE IF NOT EXISTS events (
    uid TEXT PRIMARY KEY, event TEXT, block_number INTEGER, tx_hash TEXT,
    log_index INTEGER, doc TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
CREATE INDEX IF NOT EXISTS idx_events_block ON events(block_number);
CREATE INDEX IF NOT EXISTS idx_orders_inv ON orders(investor);
"""


class SqliteRepository(Repository):
    def __init__(self, path: str) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def ping(self) -> bool:
        try:
            await self._db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def reset_chain_data(self) -> None:
        for table in ("events", "orders", "custody", "investors", "idempotency"):
            await self._db.execute(f"DELETE FROM {table}")
        await self._db.execute("DELETE FROM meta WHERE key = ?", ("last_indexed_block",))
        await self._db.commit()

    # ---- investors ----
    async def upsert_investor(self, doc: dict[str, Any]) -> None:
        addr = doc["address"].lower()
        await self._db.execute(
            "INSERT INTO investors(address, kyc_status, doc) VALUES(?,?,?) "
            "ON CONFLICT(address) DO UPDATE SET kyc_status=excluded.kyc_status, doc=excluded.doc",
            (addr, int(doc.get("kyc_status_code", 0)), json.dumps(doc)),
        )
        await self._db.commit()

    async def get_investor(self, address: str) -> dict | None:
        cur = await self._db.execute(
            "SELECT doc FROM investors WHERE address=?", (address.lower(),)
        )
        row = await cur.fetchone()
        return json.loads(row["doc"]) if row else None

    async def list_investors(self, kyc_status=None, limit=50, offset=0):
        where, params = "", []
        if kyc_status is not None:
            where, params = "WHERE kyc_status=?", [kyc_status]
        total = await self._count("investors", where, params)
        cur = await self._db.execute(
            f"SELECT doc FROM investors {where} ORDER BY address LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows = await cur.fetchall()
        return [json.loads(r["doc"]) for r in rows], total

    # ---- orders ----
    async def upsert_order(self, doc: dict[str, Any]) -> None:
        await self._db.execute(
            "INSERT INTO orders(id, order_type, status, investor, doc) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET order_type=excluded.order_type, "
            "status=excluded.status, investor=excluded.investor, doc=excluded.doc",
            (int(doc["id"]), int(doc["order_type_code"]), int(doc["status_code"]),
             doc["investor"].lower(), json.dumps(doc)),
        )
        await self._db.commit()

    async def get_order(self, order_id: int) -> dict | None:
        cur = await self._db.execute("SELECT doc FROM orders WHERE id=?", (int(order_id),))
        row = await cur.fetchone()
        return json.loads(row["doc"]) if row else None

    async def list_orders(self, order_type=None, status=None, investor=None, limit=50, offset=0):
        clauses, params = [], []
        if order_type is not None:
            clauses.append("order_type=?"); params.append(order_type)
        if status is not None:
            clauses.append("status=?"); params.append(status)
        if investor is not None:
            clauses.append("investor=?"); params.append(investor.lower())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        total = await self._count("orders", where, params)
        cur = await self._db.execute(
            f"SELECT doc FROM orders {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [json.loads(r["doc"]) for r in await cur.fetchall()], total

    # ---- custody ----
    async def add_custody(self, doc: dict[str, Any]) -> None:
        await self._db.execute(
            "INSERT INTO custody(id, investor, doc) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET investor=excluded.investor, doc=excluded.doc",
            (int(doc["id"]), doc["investor"].lower(), json.dumps(doc)),
        )
        await self._db.commit()

    async def get_custody(self, action_id: int) -> dict | None:
        cur = await self._db.execute("SELECT doc FROM custody WHERE id=?", (int(action_id),))
        row = await cur.fetchone()
        return json.loads(row["doc"]) if row else None

    async def list_custody(self, investor=None, limit=50, offset=0):
        where, params = "", []
        if investor is not None:
            where, params = "WHERE investor=?", [investor.lower()]
        total = await self._count("custody", where, params)
        cur = await self._db.execute(
            f"SELECT doc FROM custody {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [json.loads(r["doc"]) for r in await cur.fetchall()], total

    # ---- events ----
    async def add_event(self, doc: dict[str, Any]) -> bool:
        uid = f"{doc['tx_hash']}:{doc['log_index']}"
        cur = await self._db.execute(
            "INSERT OR IGNORE INTO events(uid, event, block_number, tx_hash, log_index, doc) "
            "VALUES(?,?,?,?,?,?)",
            (uid, doc["event"], int(doc["block_number"]), doc["tx_hash"],
             int(doc["log_index"]), json.dumps(doc)),
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def list_events(self, event=None, from_block=None, to_block=None,
                          event_type=None, limit=50, offset=0):
        clauses, params = [], []
        if event is not None:
            clauses.append("event=?"); params.append(event)
        if from_block is not None:
            clauses.append("block_number>=?"); params.append(from_block)
        if to_block is not None:
            clauses.append("block_number<=?"); params.append(to_block)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        total = await self._count("events", where, params)
        cur = await self._db.execute(
            f"SELECT doc FROM events {where} ORDER BY block_number DESC, log_index DESC "
            "LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [json.loads(r["doc"]) for r in await cur.fetchall()], total

    async def get_events_by_tx(self, tx_hash: str) -> list[dict]:
        cur = await self._db.execute(
            "SELECT doc FROM events WHERE tx_hash=? ORDER BY log_index", (tx_hash,)
        )
        return [json.loads(r["doc"]) for r in await cur.fetchall()]

    # ---- meta ----
    async def get_meta(self, key: str) -> str | None:
        cur = await self._db.execute("SELECT value FROM meta WHERE key=?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        await self._db.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await self._db.commit()

    # ---- idempotency ----
    async def get_idempotency(self, key: str) -> dict | None:
        cur = await self._db.execute("SELECT value FROM idempotency WHERE key=?", (key,))
        row = await cur.fetchone()
        return json.loads(row["value"]) if row else None

    async def set_idempotency(self, key: str, value: dict) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO idempotency(key, value) VALUES(?,?)",
            (key, json.dumps(value)),
        )
        await self._db.commit()

    async def _count(self, table: str, where: str, params: list) -> int:
        cur = await self._db.execute(f"SELECT COUNT(*) AS n FROM {table} {where}", params)
        row = await cur.fetchone()
        return int(row["n"])
