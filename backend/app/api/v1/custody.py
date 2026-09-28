"""Custody hub endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import Pagination, get_custody_service
from app.core.security import get_current_user, require_roles
from app.models.domain import Role
from app.schemas.common import Address, Page
from app.schemas.custody import (
    CustodyActionCreate,
    CustodyActionOut,
    CustodyActionResult,
    CustodyPosition,
)

router = APIRouter(prefix="/custody", tags=["custody"])


@router.post("/actions", response_model=CustodyActionResult, status_code=201)
async def create_action(
    payload: CustodyActionCreate,
    svc=Depends(get_custody_service),
    _=Depends(require_roles(Role.CUSTODIAN)),
) -> CustodyActionResult:
    return await svc.create_action(payload)


@router.get("/actions", response_model=Page[CustodyActionOut])
async def list_actions(
    page: Pagination = Depends(),
    investor: Address | None = Query(None),
    svc=Depends(get_custody_service),
    _=Depends(get_current_user),
) -> Page[CustodyActionOut]:
    items, total = await svc.list_actions(investor, page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/positions", response_model=Page[CustodyPosition])
async def positions(
    page: Pagination = Depends(),
    svc=Depends(get_custody_service),
    _=Depends(get_current_user),
) -> Page[CustodyPosition]:
    items, total = await svc.positions(page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
