"""Application configuration via pydantic-settings (env-driven)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = .../blockchain (two levels up from this file's backend/app dir)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All runtime configuration. Values come from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_name: str = "Tokenised Fund Servicing Platform"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    environment: str = "local"

    # ---- Chain ----
    chain_mode: Literal["inmemory", "hardhat"] = "inmemory"
    rpc_url: str = "http://127.0.0.1:8545"
    chain_id: int = 31337
    fund_name: str = "Global Tech Fund"
    initial_unit_price: int = 100 * 10**8  # PRICE_SCALE = 1e8
    event_start_block: int = 0
    event_poll_interval: float = 2.0

    # ---- Paths ----
    deployments_path: str = str(PROJECT_ROOT / "deployments" / "local.json")
    contract_source: str = str(PROJECT_ROOT / "contracts" / "TokenisedFundServicing.sol")
    oz_contracts_path: str = str(PROJECT_ROOT / "node_modules" / "@openzeppelin" / "contracts")

    # ---- Database ----
    db_mode: Literal["sqlite", "mongo"] = "sqlite"
    sqlite_path: str = str(PROJECT_ROOT / "backend" / "fund.db")
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "fund_servicing"

    # ---- Auth ----
    jwt_secret: str = "dev-secret-change-me-please-set-a-32b-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # ---- CORS ----
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ---- Well-known local dev keys (Hardhat mnemonic accounts 0-9) ----
    dev_admin_key: str = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    dev_transfer_agent_key: str = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    dev_custodian_key: str = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
    dev_auditor_key: str = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
    dev_investor_keys: list[str] = Field(
        default_factory=lambda: [
            "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
            "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba",
            "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e",
            "0x4bbbf85ce3377467afe5d46f804f221813b2bb87f24d81f60f1fcdbf7cbf4356",
            "0xdbda1821b80551c9d65939329250298aa3472ba22feea921c0cf5d620ea67b97",
        ]
    )

    @field_validator("cors_origins", "dev_investor_keys", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Allow comma-separated strings from env for list fields."""
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                return v  # let pydantic parse JSON
            return [item.strip() for item in s.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
