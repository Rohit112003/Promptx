"""Investor-to-investor transfers with compliance checks."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_order_service
from app.core.errors import ForbiddenError
from app.core.security import require_roles
from app.models.domain import Role
from app.schemas.auth import CurrentUser
from app.schemas.order import TransferCreate, TransferResult

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferResult, status_code=201)
async def create_transfer(
    payload: TransferCreate,
    svc=Depends(get_order_service),
    user: CurrentUser = Depends(require_roles(Role.INVESTOR, Role.TRANSFER_AGENT)),
) -> TransferResult:
    if user.role == Role.INVESTOR.value and user.address.lower() != payload.from_address.lower():
        raise ForbiddenError("Investors may only transfer from their own address")
    return await svc.transfer(payload)
