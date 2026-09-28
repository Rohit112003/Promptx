"""Compliance/admin: pause, freeze, and role directory."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_context
from app.core.security import require_roles
from app.models.domain import Role
from app.schemas.common import Message
from app.schemas.report import RoleHolder
from app.services.helpers import receipt_from

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_roles(Role.ADMIN)
_agent_or_admin = require_roles(Role.TRANSFER_AGENT)


@router.post("/pause")
async def pause(ctx=Depends(get_context), _=Depends(_admin)):
    rcpt = await ctx.gateway.pause()
    return {"message": "Fund paused", "receipt": receipt_from(rcpt).model_dump()}


@router.post("/unpause")
async def unpause(ctx=Depends(get_context), _=Depends(_admin)):
    rcpt = await ctx.gateway.unpause()
    return {"message": "Fund unpaused", "receipt": receipt_from(rcpt).model_dump()}


@router.post("/freeze/{address}")
async def freeze(address: str, ctx=Depends(get_context), _=Depends(_agent_or_admin)):
    rcpt = await ctx.gateway.set_frozen(address, True)
    return {"message": f"Investor {address} frozen", "receipt": receipt_from(rcpt).model_dump()}


@router.post("/unfreeze/{address}")
async def unfreeze(address: str, ctx=Depends(get_context), _=Depends(_agent_or_admin)):
    rcpt = await ctx.gateway.set_frozen(address, False)
    return {"message": f"Investor {address} unfrozen", "receipt": receipt_from(rcpt).model_dump()}


@router.get("/roles", response_model=list[RoleHolder])
async def roles(ctx=Depends(get_context), _=Depends(require_roles(Role.AUDITOR, Role.TRANSFER_AGENT))):
    acc = ctx.client.accounts
    mapping = [
        ("ADMIN", acc.admin.address, "Fund administrator"),
        ("TRANSFER_AGENT", acc.transfer_agent.address, "KYC, NAV, order settlement"),
        ("CUSTODIAN", acc.custodian.address, "Custody actions"),
        ("AUDITOR", acc.auditor.address, "Read-only auditor"),
    ]
    return [RoleHolder(role=r, address=a, label=lbl) for r, a, lbl in mapping]
