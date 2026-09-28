"""Run the API with `python -m app` (from the backend/ directory)."""
from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # we configure structured logging ourselves
    )


if __name__ == "__main__":
    main()
