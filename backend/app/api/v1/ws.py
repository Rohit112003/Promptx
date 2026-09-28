"""WebSocket feed of indexed on-chain events."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.logging_config import get_logger

router = APIRouter()
log = get_logger("ws")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Stream on-chain events as JSON as they are indexed."""
    await websocket.accept()
    ws_manager = websocket.app.state.ctx.ws
    queue = ws_manager.subscribe()
    try:
        await websocket.send_json({"type": "connected", "message": "subscribed to on-chain events"})
        while True:
            message = await queue.get()
            await websocket.send_json({"type": "event", "data": message})
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover
        log.exception("websocket error")
    finally:
        ws_manager.unsubscribe(queue)
