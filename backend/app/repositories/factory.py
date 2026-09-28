"""Repository factory with graceful Mongo -> SQLite fallback."""
from __future__ import annotations

from app.config import settings
from app.logging_config import get_logger
from app.repositories.base import Repository

log = get_logger("repository")


async def build_repository() -> Repository:
    """Build and connect the configured repository.

    If DB_MODE=mongo but Mongo is unreachable, fall back to SQLite so the platform
    still runs with one command.
    """
    if settings.db_mode == "mongo":
        from app.repositories.mongo_repo import MongoRepository

        repo = MongoRepository(settings.mongo_url, settings.mongo_db)
        try:
            await repo.connect()
            log.info("connected to MongoDB", extra={"ctx_url": settings.mongo_url})
            return repo
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning("Mongo unavailable, falling back to SQLite",
                        extra={"ctx_error": str(exc)})

    from app.repositories.sqlite_repo import SqliteRepository

    repo = SqliteRepository(settings.sqlite_path)
    await repo.connect()
    log.info("connected to SQLite", extra={"ctx_path": settings.sqlite_path})
    return repo
