"""Repository interfaces and swappable SQLite / Mongo implementations."""
from app.repositories.base import Repository
from app.repositories.factory import build_repository

__all__ = ["Repository", "build_repository"]
