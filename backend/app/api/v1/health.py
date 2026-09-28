"""Health endpoint (unauthenticated)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_health_service
from app.schemas.report import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(svc=Depends(get_health_service)) -> HealthResponse:
    """API, chain connectivity, DB, latest block and contract address."""
    return await svc.health()
