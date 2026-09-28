"""Reporting & analytics: dual-format statements (traditional + blockchain-native),
CSV/PDF export, fund summary, transaction reports, and NAV performance."""
from __future__ import annotations

import csv
import io

from web3 import Web3

from app.blockchain.contract import ContractGateway
from app.core.constants import PRICE_SCALE, price_to_float
from app.core.errors import NotFoundError
from app.models.domain import KYC_STATUS_NAME, KycStatus, OrderStatus
from app.repositories.base import Repository
from app.schemas.report import FundSummary, InvestorStatement, NavPerformancePoint
from app.services.helpers import now_iso


class ReportService:
    def __init__(self, gateway: ContractGateway, repo: Repository) -> None:
        self.g = gateway
        self.repo = repo

    # ---------- data gathering ----------
    def _all_transactions(self, address: str) -> list[dict]:
        total = self.g.transaction_count(address)
        rows: list[dict] = []
        offset = 0
        while offset < total:
            page = self.g.get_transactions(address, offset, 100)
            if not page:
                break
            rows.extend(page)
            offset += len(page)
        return rows

    async def _investor_events(self, address: str) -> list[dict]:
        events, _ = await self.repo.list_events(limit=500, offset=0)
        addr = address.lower()
        matched = []
        for e in events:
            args = e.get("args", {})
            if any(isinstance(v, str) and v.lower() == addr for v in args.values()):
                matched.append({
                    "event": e["event"], "tx_hash": e["tx_hash"],
                    "block_number": e["block_number"], "timestamp": e.get("timestamp"),
                    "args": args,
                })
        return matched

    # ---------- statements ----------
    async def investor_statement(self, address: str, fmt: str = "traditional") -> InvestorStatement:
        chain = self.g.get_investor(address)
        prof = await self.repo.get_investor(address)
        if not chain["exists"] and not prof:
            raise NotFoundError(f"Investor {address} not found")
        prof = prof or {}
        unit_price = self.g.unit_price()
        txs = self._all_transactions(address)

        holdings = {
            "units": chain["balance"],
            "locked_units": chain["locked"],
            "free_units": chain["balance"] - chain["locked"],
            "unit_price": price_to_float(unit_price),
            "portfolio_value": self.g.portfolio_value(address),
            "currency": "USD",
        }
        investor_block = {
            "address": Web3.to_checksum_address(address),
            "name": prof.get("name"),
            "jurisdiction": chain["jurisdiction"] or prof.get("jurisdiction"),
            "kyc_status": KYC_STATUS_NAME.get(chain["kyc_status"], "NONE"),
            "frozen": chain["frozen"],
        }

        if fmt == "blockchain-native":
            events = await self._investor_events(address)
            investor_block["kyc_hash"] = chain["kyc_hash"]
            investor_block["contract_address"] = self.g.client.address
            transactions = events
        else:
            transactions = [
                {
                    "type": t["type"],
                    "units": t["units"],
                    "unit_price": price_to_float(t["unit_price"]),
                    "amount": round(t["units"] * t["unit_price"] / PRICE_SCALE, 2),
                    "timestamp": t["timestamp"],
                }
                for t in txs
            ]

        return InvestorStatement(
            format=fmt,
            investor=investor_block,
            holdings=holdings,
            transactions=transactions,
            generated_at=now_iso(),
        )

    async def statement_csv(self, address: str) -> str:
        stmt = await self.investor_statement(address, "traditional")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Investor Statement"])
        writer.writerow(["Address", stmt.investor["address"]])
        writer.writerow(["Name", stmt.investor.get("name") or ""])
        writer.writerow(["KYC Status", stmt.investor["kyc_status"]])
        writer.writerow(["Units", stmt.holdings["units"]])
        writer.writerow(["Unit Price", stmt.holdings["unit_price"]])
        writer.writerow(["Portfolio Value", stmt.holdings["portfolio_value"]])
        writer.writerow([])
        writer.writerow(["Type", "Units", "Unit Price", "Amount", "Timestamp"])
        for t in stmt.transactions:
            writer.writerow([t.get("type"), t.get("units"), t.get("unit_price"),
                             t.get("amount"), t.get("timestamp")])
        return buf.getvalue()

    async def statement_pdf(self, address: str) -> bytes:
        stmt = await self.investor_statement(address, "traditional")
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="Investor Statement")
        styles = getSampleStyleSheet()
        story = [
            Paragraph("Tokenised Fund Servicing — Investor Statement", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Address: {stmt.investor['address']}", styles["Normal"]),
            Paragraph(f"Name: {stmt.investor.get('name') or '-'}", styles["Normal"]),
            Paragraph(f"KYC Status: {stmt.investor['kyc_status']}", styles["Normal"]),
            Paragraph(f"Units: {stmt.holdings['units']} @ {stmt.holdings['unit_price']} USD",
                      styles["Normal"]),
            Paragraph(f"Portfolio Value: {stmt.holdings['portfolio_value']} USD", styles["Normal"]),
            Spacer(1, 16),
            Paragraph("Transactions", styles["Heading2"]),
        ]
        table_data = [["Type", "Units", "Unit Price", "Amount", "Timestamp"]]
        for t in stmt.transactions:
            table_data.append([t.get("type"), t.get("units"), t.get("unit_price"),
                               t.get("amount"), t.get("timestamp")])
        table = Table(table_data, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
        doc.build(story)
        return buf.getvalue()

    # ---------- fund-level ----------
    async def fund_summary(self) -> FundSummary:
        fs = self.g.fund_status()
        investors, investor_count = await self.repo.list_investors(limit=1, offset=0)
        approved, approved_count = await self.repo.list_investors(
            kyc_status=KycStatus.APPROVED.value, limit=1, offset=0
        )
        _, pending = await self.repo.list_orders(status=OrderStatus.PENDING.value, limit=1)
        _, settled = await self.repo.list_orders(status=OrderStatus.SETTLED.value, limit=1)
        return FundSummary(
            fund_name=fs["fund_name"],
            nav_total=fs["nav_total"],
            total_supply=fs["total_supply"],
            unit_price=fs["unit_price"],
            total_value=fs["total_value"],
            investor_count=investor_count,
            approved_investors=approved_count,
            pending_orders=pending,
            settled_orders=settled,
            generated_at=now_iso(),
        )

    async def transactions_report(self, from_block, to_block, event_type, limit, offset):
        return await self.repo.list_events(
            event=event_type, from_block=from_block, to_block=to_block,
            limit=limit, offset=offset,
        )

    async def nav_performance(self) -> list[NavPerformancePoint]:
        events, _ = await self.repo.list_events(event="NAVUpdated", limit=500, offset=0)
        events = sorted(events, key=lambda e: e["block_number"])
        points: list[NavPerformancePoint] = []
        base_price = None
        for e in events:
            price = int(e["args"].get("unitPrice", 0))
            if base_price is None:
                base_price = price or 1
            ret = ((price - base_price) / base_price * 100) if base_price else 0.0
            points.append(NavPerformancePoint(
                timestamp=int(e["args"].get("timestamp", e.get("timestamp") or 0)),
                unit_price=price,
                nav_total=int(e["args"].get("newNAV", 0)),
                return_pct=round(ret, 4),
            ))
        return points
