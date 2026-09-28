"""FastAPI dependencies for accessing the app context and its services."""
from __future__ import annotations

from fastapi import Query, Request

from app.core.context import AppContext


def get_context(request: Request) -> AppContext:
    return request.app.state.ctx


def get_investor_service(request: Request):
    return request.app.state.ctx.investor_service


def get_order_service(request: Request):
    return request.app.state.ctx.order_service


def get_nav_service(request: Request):
    return request.app.state.ctx.nav_service


def get_custody_service(request: Request):
    return request.app.state.ctx.custody_service


def get_report_service(request: Request):
    return request.app.state.ctx.report_service


def get_audit_service(request: Request):
    return request.app.state.ctx.audit_service


def get_health_service(request: Request):
    return request.app.state.ctx.health_service


class Pagination:
    """Common pagination query params."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> None:
        self.limit = limit
        self.offset = offset
