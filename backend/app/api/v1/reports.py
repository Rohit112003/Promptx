"""Reporting & analytics endpoints (dual-format, CSV/PDF export)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import Pagination, get_report_service
from app.core.security import get_current_user
from app.schemas.common import Page
from app.schemas.report import (
    AuditEvent,
    FundSummary,
    InvestorStatement,
    NavPerformancePoint,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/investor/{address}/statement", response_model=InvestorStatement)
async def investor_statement(
    address: str,
    style: str = Query("traditional", description="traditional | blockchain-native"),
    format: str = Query("json", description="json | csv | pdf"),
    svc=Depends(get_report_service),
    _=Depends(get_current_user),
):
    """Investor statement. `style` picks traditional vs blockchain-native;
    `format` returns JSON, CSV or a PDF download."""
    if format == "csv":
        csv_text = await svc.statement_csv(address)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=statement_{address}.csv"},
        )
    if format == "pdf":
        pdf_bytes = await svc.statement_pdf(address)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=statement_{address}.pdf"},
        )
    return await svc.investor_statement(address, style)


@router.get("/fund/summary", response_model=FundSummary)
async def fund_summary(svc=Depends(get_report_service), _=Depends(get_current_user)) -> FundSummary:
    return await svc.fund_summary()


@router.get("/transactions", response_model=Page[AuditEvent])
async def transactions(
    page: Pagination = Depends(),
    from_block: int | None = Query(None, alias="from"),
    to_block: int | None = Query(None, alias="to"),
    type: str | None = Query(None, description="Event name filter, e.g. OrderSettled"),
    svc=Depends(get_report_service),
    _=Depends(get_current_user),
) -> Page[AuditEvent]:
    items, total = await svc.transactions_report(from_block, to_block, type, page.limit, page.offset)
    events = [
        AuditEvent(event=d["event"], tx_hash=d["tx_hash"], block_number=d["block_number"],
                   log_index=d["log_index"], timestamp=d.get("timestamp"), args=d.get("args", {}))
        for d in items
    ]
    return Page(items=events, total=total, limit=page.limit, offset=page.offset)


@router.get("/nav-performance", response_model=list[NavPerformancePoint])
async def nav_performance(
    svc=Depends(get_report_service), _=Depends(get_current_user)
) -> list[NavPerformancePoint]:
    return await svc.nav_performance()
