"""JWT authentication and role-based access control mapped to on-chain roles."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.blockchain.accounts import DevAccounts
from app.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.models.domain import Role
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login",
                                     auto_error=False)

# Demo login: fixed password for every demo user.
_DEMO_PASSWORD = "demo"
_dev_accounts = DevAccounts()
_DEMO_USERS = _dev_accounts.demo_users()


def _create_token(username: str, role: str, address: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "address": address,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def login(payload: LoginRequest) -> TokenResponse:
    username = payload.username.strip()
    password = payload.password.strip()
    user = _DEMO_USERS.get(username)
    if not user or password != _DEMO_PASSWORD:
        raise UnauthorizedError("Invalid username or password")
    token = _create_token(username, user["role"], user["address"])
    return TokenResponse(access_token=token, role=user["role"], address=user["address"])


def demo_users() -> dict:
    """Public map (no secrets) for docs / login helper."""
    return {u: {"role": v["role"], "address": v["address"], "password": _DEMO_PASSWORD}
            for u, v in _DEMO_USERS.items()}


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    if not token:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    return CurrentUser(username=payload["sub"], role=payload["role"], address=payload["address"])


def require_roles(*allowed: Role):
    """Dependency factory: allow the listed roles (ADMIN always allowed)."""
    allowed_names = {r.value for r in allowed} | {Role.ADMIN.value}

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_names:
            raise ForbiddenError(
                f"Role '{user.role}' is not permitted (requires one of {sorted(allowed_names)})"
            )
        return user

    return _dep
