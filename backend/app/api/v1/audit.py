"""Audit endpoints: indexed on-chain events and off-chain/chain verification."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import Pagination, get_audit_service
from app.core.security import get_current_user
from app.schemas.common import Page
from app.schemas.report import AuditEvent, AuditVerification

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=Page[AuditEvent])
async def events(
    page: Pagination = Depends(),
    event: str | None = Query(None, description="Filter by event name"),
    from_block: int | None = Query(None, alias="from"),
    to_block: int | None = Query(None, alias="to"),
    svc=Depends(get_audit_service),
    _=Depends(get_current_user),
) -> Page[AuditEvent]:
    items, total = await svc.list_events(event, from_block, to_block, page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/verify/{tx_hash}", response_model=AuditVerification)
async def verify(
    tx_hash: str, svc=Depends(get_audit_service), _=Depends(get_current_user)
) -> AuditVerification:
    return await svc.verify(tx_hash)
