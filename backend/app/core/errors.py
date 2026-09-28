"""Application error types, contract-revert mapping, and FastAPI handlers."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import get_logger, request_id_ctx

log = get_logger("errors")


class AppError(Exception):
    """Base application error with a stable machine-readable code."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None,
                 detail: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.detail = detail or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ChainRevertError(AppError):
    """A contract call reverted; carries the mapped HTTP status."""

    def __init__(self, revert_name: str | None, message: str, *, status_code: int = 400):
        super().__init__(message, code="contract_revert", status_code=status_code,
                         detail={"revert": revert_name})
        self.revert_name = revert_name


# Map on-chain revert/custom-error names -> (http status, human message).
_REVERT_MAP: dict[str, tuple[int, str]] = {
    "NotRegistered": (404, "Investor is not registered on chain"),
    "NotApproved": (409, "Investor KYC is not approved"),
    "IsFrozen": (409, "Investor account is frozen"),
    "InvalidAmount": (400, "Amount must be greater than zero"),
    "InsufficientBalance": (409, "Insufficient balance"),
    "InsufficientUnlocked": (409, "Insufficient unlocked units (some may be under custody lock)"),
    "NavChangeTooLarge": (400, "NAV change exceeds the allowed 20% bound"),
    "OrderNotFound": (404, "Order not found"),
    "OrderNotPending": (409, "Order is not in a pending state"),
    "NotOrderOwner": (403, "Only the order owner or a transfer agent may do this"),
    "ZeroAddress": (400, "Zero address is not allowed"),
    "EnforcedPause": (409, "Fund is paused"),
    "ExpectedPause": (409, "Fund is not paused"),
    "AccessControlUnauthorizedAccount": (403, "Account is missing the required on-chain role"),
}


def map_revert(revert_name: str | None, raw_message: str) -> ChainRevertError:
    """Translate a contract revert into a ChainRevertError with the right status."""
    if revert_name and revert_name in _REVERT_MAP:
        status, msg = _REVERT_MAP[revert_name]
        return ChainRevertError(revert_name, msg, status_code=status)
    # Fallback: scan the raw message for a known name.
    for name, (status, msg) in _REVERT_MAP.items():
        if name in raw_message:
            return ChainRevertError(name, msg, status_code=status)
    return ChainRevertError(revert_name, f"Contract call reverted: {raw_message}", status_code=400)


def _error_body(code: str, message: str, detail: dict) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "request_id": request_id_ctx.get(),
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        log.warning("app_error", extra={"ctx_code": exc.code, "ctx_path": request.url.path})
        return JSONResponse(status_code=exc.status_code,
                            content=_error_body(exc.code, exc.message, exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Sanitise: pydantic errors can carry a non-JSON-serialisable `ctx` (e.g. the
        # underlying exception object). Stringify any such fields.
        safe_errors = [
            {k: (str(v) if k == "ctx" else v) for k, v in err.items()}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", "Request validation failed",
                                {"errors": safe_errors}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error")
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "Internal server error", {}),
        )
