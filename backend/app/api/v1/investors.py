"""Investor registration and lookup."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import Pagination, get_investor_service
from app.core.security import require_roles
from app.models.domain import KYC_STATUS_NAME, KycStatus, Role
from app.schemas.common import Page
from app.schemas.investor import InvestorCreate, InvestorOut, InvestorRegisterResult

router = APIRouter(prefix="/investors", tags=["investors"])

_STATUS_BY_NAME = {v: k for k, v in KYC_STATUS_NAME.items()}


@router.post("", response_model=InvestorRegisterResult, status_code=201)
async def register_investor(
    payload: InvestorCreate,
    svc=Depends(get_investor_service),
    _=Depends(require_roles(Role.TRANSFER_AGENT)),
) -> InvestorRegisterResult:
    """Register an investor on chain (status PENDING). PII stays off-chain."""
    return await svc.register(payload)


@router.get("", response_model=Page[InvestorOut])
async def list_investors(
    page: Pagination = Depends(),
    kyc_status: str | None = Query(None, description="NONE|PENDING|APPROVED|REJECTED"),
    svc=Depends(get_investor_service),
    _=Depends(require_roles(Role.AUDITOR, Role.TRANSFER_AGENT, Role.CUSTODIAN)),
) -> Page[InvestorOut]:
    status_code = _STATUS_BY_NAME.get(kyc_status.upper()) if kyc_status else None
    items, total = await svc.list_investors(status_code, page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{address}", response_model=InvestorOut)
async def get_investor(
    address: str,
    svc=Depends(get_investor_service),
    _=Depends(require_roles(Role.AUDITOR, Role.TRANSFER_AGENT, Role.CUSTODIAN, Role.INVESTOR)),
) -> InvestorOut:
    return await svc.get_investor(address)
