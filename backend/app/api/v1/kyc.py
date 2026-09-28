"""KYC decisions (transfer agent only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_investor_service
from app.core.security import require_roles
from app.models.domain import Role
from app.schemas.investor import KycActionResult

router = APIRouter(prefix="/kyc", tags=["kyc"])
_agent = require_roles(Role.TRANSFER_AGENT)


@router.post("/{address}/approve", response_model=KycActionResult)
async def approve(address: str, svc=Depends(get_investor_service), _=Depends(_agent)):
    return await svc.approve(address)


@router.post("/{address}/reject", response_model=KycActionResult)
async def reject(address: str, svc=Depends(get_investor_service), _=Depends(_agent)):
    return await svc.reject(address)


@router.post("/{address}/revoke", response_model=KycActionResult)
async def revoke(address: str, svc=Depends(get_investor_service), _=Depends(_agent)):
    return await svc.revoke(address)
