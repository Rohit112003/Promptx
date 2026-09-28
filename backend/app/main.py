"""FastAPI application factory and lifespan wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.v1.router import api_router, ws_router
from app.config import settings
from app.core.context import build_context
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIdMiddleware
from app.logging_config import configure_logging, get_logger

log = get_logger("main")

# cd backend
# ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    log.info("starting up", extra={"ctx_chain_mode": settings.chain_mode,
                                   "ctx_db_mode": settings.db_mode}) 
    ctx = await build_context()
    app.state.ctx = ctx
    ctx.listener.start()
    log.info("ready", extra={"ctx_contract": ctx.client.address})
    try:
        yield
    finally:
        await ctx.listener.stop()
        await ctx.repo.close()
        log.info("shutdown complete")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Tokenised Fund Servicing Platform — Custody Hub, Transfer Agency Engine, "
            "and Reporting & Analytics Suite. The chain is the source of truth; the API "
            "enriches it with off-chain data and a real-time event feed."
        ),
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(ws_router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
