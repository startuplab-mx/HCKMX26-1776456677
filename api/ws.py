"""
WebSocket endpoint — pushes real-time alerts to the moderator dashboard.
Redis pub/sub bridges Celery workers → connected WS clients.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from config import get_settings
import redis.asyncio as aioredis

settings = get_settings()
router = APIRouter()

# Connected dashboard clients
_clients: set[WebSocket] = set()


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        # Start Redis listener on first connection
        listener = asyncio.create_task(_redis_listener(websocket))
        while True:
            # Keep alive — client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        listener.cancel()


async def _redis_listener(websocket: WebSocket):
    """Subscribe to Redis channel and forward alerts to this WS client."""
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("guardiannode:alerts")
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                try:
                    await websocket.send_text(data)
                except Exception:
                    break
    finally:
        await pubsub.unsubscribe("guardiannode:alerts")
        await r.aclose()
