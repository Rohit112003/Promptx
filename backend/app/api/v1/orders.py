"""Transfer-agency order endpoints: subscribe, redeem, settle, cancel, list."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.core.deps import Pagination, get_order_service
from app.core.errors import ForbiddenError
from app.models.domain import (
    ORDER_STATUS_NAME,
    ORDER_TYPE_NAME,
    OrderStatus,
    OrderType,
    Role,
)
from app.schemas.auth import CurrentUser
from app.schemas.common import Address, Page
from app.schemas.order import OrderActionResult, OrderCreate, OrderOut
from app.core.security import get_current_user, require_roles

router = APIRouter(prefix="/orders", tags=["orders"])

_TYPE_BY_NAME = {v: k for k, v in ORDER_TYPE_NAME.items()}
_STATUS_BY_NAME = {v: k for k, v in ORDER_STATUS_NAME.items()}


def _assert_can_act_for(user: CurrentUser, investor: str) -> None:
    """Investors may only act for themselves; agents/admins may act for anyone."""
    if user.role == Role.INVESTOR.value and user.address.lower() != investor.lower():
        raise ForbiddenError("Investors may only place orders for their own address")


@router.post("/subscribe", response_model=OrderActionResult, status_code=201)
async def subscribe(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    svc=Depends(get_order_service),
    user: CurrentUser = Depends(require_roles(Role.INVESTOR, Role.TRANSFER_AGENT)),
) -> OrderActionResult:
    _assert_can_act_for(user, payload.investor)
    return await svc.subscribe(payload, idempotency_key)


@router.post("/redeem", response_model=OrderActionResult, status_code=201)
async def redeem(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    svc=Depends(get_order_service),
    user: CurrentUser = Depends(require_roles(Role.INVESTOR, Role.TRANSFER_AGENT)),
) -> OrderActionResult:
    _assert_can_act_for(user, payload.investor)
    return await svc.redeem(payload, idempotency_key)


@router.post("/{order_id}/settle", response_model=OrderActionResult)
async def settle(
    order_id: int,
    svc=Depends(get_order_service),
    _=Depends(require_roles(Role.TRANSFER_AGENT)),
) -> OrderActionResult:
    return await svc.settle(order_id)


@router.post("/{order_id}/cancel", response_model=OrderActionResult)
async def cancel(
    order_id: int,
    svc=Depends(get_order_service),
    _=Depends(require_roles(Role.INVESTOR, Role.TRANSFER_AGENT)),
) -> OrderActionResult:
    return await svc.cancel(order_id)


@router.get("", response_model=Page[OrderOut])
async def list_orders(
    page: Pagination = Depends(),
    order_type: str | None = Query(None, description="SUBSCRIPTION|REDEMPTION"),
    status: str | None = Query(None, description="PENDING|SETTLED|CANCELLED"),
    investor: Address | None = Query(None),
    svc=Depends(get_order_service),
    _: CurrentUser = Depends(get_current_user),
) -> Page[OrderOut]:
    t = _TYPE_BY_NAME.get(order_type.upper()) if order_type else None
    s = _STATUS_BY_NAME.get(status.upper()) if status else None
    items, total = await svc.list_orders(t, s, investor, page.limit, page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    svc=Depends(get_order_service),
    _: CurrentUser = Depends(get_current_user),
) -> OrderOut:
    return await svc.get_order(order_id)
