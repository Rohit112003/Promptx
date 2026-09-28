"""Fund status and NAV endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import Pagination, get_nav_service
from app.core.security import get_current_user, require_roles
from app.models.domain import Role
from app.schemas.common import Page
from app.schemas.nav import FundStatus, NavPoint, NavUpdate, NavUpdateResult

router = APIRouter(prefix="/fund", tags=["fund/nav"])


@router.get("/status", response_model=FundStatus)
async def fund_status(svc=Depends(get_nav_service), _=Depends(get_current_user)) -> FundStatus:
    return svc.fund_status()


@router.post("/nav", response_model=NavUpdateResult)
async def update_nav(
    payload: NavUpdate,
    svc=Depends(get_nav_service),
    _=Depends(require_roles(Role.TRANSFER_AGENT)),
) -> NavUpdateResult:
    return await svc.update_nav(payload)


@router.get("/nav/history", response_model=Page[NavPoint])
async def nav_history(
    page: Pagination = Depends(),
    svc=Depends(get_nav_service),
    _=Depends(get_current_user),
) -> Page[NavPoint]:
    items, total = await svc.nav_history(page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
