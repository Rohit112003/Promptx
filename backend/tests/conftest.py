"""Pytest fixtures: boot the API against the in-memory chain + a temp SQLite DB."""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("CHAIN_MODE", "inmemory")
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["SQLITE_PATH"] = os.path.join(tempfile.gettempdir(), "fund_test.db")
if os.path.exists(os.environ["SQLITE_PATH"]):
    os.remove(os.environ["SQLITE_PATH"])

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def users(client):
    return client.get("/api/v1/auth/demo-users").json()


def _token(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", data={"username": username, "password": "demo"})
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def agent(client):
    return _token(client, "agent")


@pytest.fixture(scope="session")
def custodian(client):
    return _token(client, "custodian")


@pytest.fixture(scope="session")
def auditor(client):
    return _token(client, "auditor")


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
