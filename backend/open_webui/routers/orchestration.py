"""
WebSocket endpoint for real-time orchestration events.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from open_webui.utils.orchestration_broadcast import subscribe, unsubscribe

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def orchestration_ws(ws: WebSocket):
    await ws.accept()
    q = subscribe()
    try:
        await ws.send_json({"step": "connected"})
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                # Keep-alive ping
                await ws.send_json({"step": "ping"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        unsubscribe(q)
