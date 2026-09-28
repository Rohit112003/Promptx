"""Auth: demo JWT login (OAuth2 password form) and role directory."""
from __future__ import annotations

from fastapi import APIRouter, Form

from app.core import security
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    username: str = Form(..., description="Demo user: admin, agent, custodian, auditor, investor1..5"),
    password: str = Form(..., description="Password for every demo user is: demo"),
    grant_type: str | None = Form(default=None, include_in_schema=False),
) -> TokenResponse:
    """Exchange a demo username/password for a JWT (password = 'demo').

    Works with Swagger's **Authorize** button and with "Try it out" here.
    Demo users: admin, agent, custodian, auditor, investor1..investor5.
    """
    return security.login(LoginRequest(username=username, password=password))


@router.get("/demo-users")
async def demo_users() -> dict:
    """List the demo users, their roles, addresses and shared password."""
    return security.demo_users()
