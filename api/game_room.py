"""
Game room WebSocket — connects players through the moderation pipeline.

Protocol (JSON):
  Client → Server:
    {"type": "join",    "room": "abc", "player_id": "px", "game_id": "demo"}
    {"type": "message", "text": "hola"}
    {"type": "ping"}

  Server → Client (players):
    {"type": "joined",        "room": "abc", "player_id": "px", "players": [...]}
    {"type": "player_joined", "player_id": "..."}
    {"type": "player_left",   "player_id": "..."}
    {"type": "message",       "from": "px", "text": "...", "level": "low", "blocked": false, "reason": ""}
    {"type": "blocked",       "reason": "..."}   ← only to sender
    {"type": "pong"}
    {"type": "error",         "detail": "..."}

  Server → Supervisor (admin):
    {"type": "supervisor_message", "from": "px", "text": "...", "level": "low",
     "blocked": bool, "warned": bool, "reason": "...", "ts": "..."}
    {"type": "supervisor_alert",   ...}           ← risk events
    {"type": "room_state",         "players": [...], "room": "..."}
    {"type": "player_joined",      "player_id": "..."}
    {"type": "player_left",        "player_id": "..."}
"""
import json
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# ── Ephemeral in-memory stats (never written to disk — legal compliance) ──────
# Reset on process restart. No PII, no message content stored here.
_ephemeral_stats: dict = {
    "total_messages": 0,
    "total_alerts": 0,
    "by_level": {"low": 0, "medium": 0, "high": 0},
    "by_action": {"allow": 0, "warn": 0, "block": 0},
}

def get_ephemeral_stats() -> dict:
    return {
        "total_messages": _ephemeral_stats["total_messages"],
        "total_alerts": _ephemeral_stats["total_alerts"],
        "alert_rate": round(
            _ephemeral_stats["total_alerts"] / _ephemeral_stats["total_messages"], 4
        ) if _ephemeral_stats["total_messages"] else 0,
        "by_level": dict(_ephemeral_stats["by_level"]),
        "by_action": dict(_ephemeral_stats["by_action"]),
    }

def _update_stats(result: dict) -> None:
    _ephemeral_stats["total_messages"] += 1
    level = result.get("level", "low")
    action = result.get("action", "allow")
    if level in _ephemeral_stats["by_level"]:
        _ephemeral_stats["by_level"][level] += 1
    if action in _ephemeral_stats["by_action"]:
        _ephemeral_stats["by_action"][action] += 1
    if result.get("risk"):
        _ephemeral_stats["total_alerts"] += 1

router = APIRouter()


@dataclass
class Player:
    ws: WebSocket
    player_id: str
    game_id: str


@dataclass
class Room:
    room_id: str
    players: dict[str, Player] = field(default_factory=dict)
    dashboard_listeners: set[WebSocket] = field(default_factory=set)
    supervisor_listeners: set[WebSocket] = field(default_factory=set)

    MAX_PLAYERS = 20

    def is_full(self) -> bool:
        return len(self.players) >= self.MAX_PLAYERS

    async def broadcast(self, msg: dict, exclude: str | None = None):
        dead = []
        for pid, player in self.players.items():
            if pid == exclude:
                continue
            try:
                await player.ws.send_json(msg)
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.players.pop(pid, None)

    async def send_to(self, player_id: str, msg: dict):
        player = self.players.get(player_id)
        if player:
            try:
                await player.ws.send_json(msg)
            except Exception:
                pass

    async def notify_dashboards(self, alert: dict):
        dead = []
        for ws in list(self.dashboard_listeners):
            try:
                await ws.send_json(alert)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.dashboard_listeners.discard(ws)

    async def notify_supervisors(self, msg: dict):
        dead = []
        for ws in list(self.supervisor_listeners):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.supervisor_listeners.discard(ws)


_rooms: dict[str, Room] = {}


def _get_or_create_room(room_id: str) -> Room:
    if room_id not in _rooms:
        _rooms[room_id] = Room(room_id=room_id)
    return _rooms[room_id]


@router.websocket("/ws/game/{room_id}")
async def game_room_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    room = _get_or_create_room(room_id)
    player_id: str | None = None
    game_id: str = "simulator"

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            mtype = msg.get("type")

            # ── Join ──────────────────────────────────────────────────────────
            if mtype == "join":
                if room.is_full() and msg.get("player_id") not in room.players:
                    await websocket.send_json({"type": "error", "detail": "Room full"})
                    continue

                player_id = msg.get("player_id", f"player_{len(room.players)+1}")
                game_id = msg.get("game_id", "simulator")
                room.players[player_id] = Player(ws=websocket, player_id=player_id, game_id=game_id)

                await websocket.send_json({
                    "type": "joined",
                    "room": room_id,
                    "player_id": player_id,
                    "players": list(room.players.keys()),
                })
                await room.broadcast(
                    {"type": "player_joined", "player_id": player_id},
                    exclude=player_id,
                )
                await room.notify_supervisors({
                    "type": "player_joined",
                    "player_id": player_id,
                    "players": list(room.players.keys()),
                })

            # ── Chat message ──────────────────────────────────────────────────
            elif mtype == "message":
                if not player_id:
                    await websocket.send_json({"type": "error", "detail": "Join first"})
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                # Group context: use stable room target so all messages share one context
                target_id = f"group_{room_id}"

                # Run moderation in thread pool (sync LLM calls)
                loop = asyncio.get_event_loop()
                try:
                    result = await loop.run_in_executor(
                        None,
                        _moderate,
                        text, game_id, room_id, player_id, target_id,
                    )
                except Exception as e:
                    # LLM failed — allow message through, notify sender
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Moderación no disponible: {str(e)[:80]}",
                    })
                    # Still deliver message so session doesn't die
                    ts = datetime.now(timezone.utc).isoformat()
                    await room.broadcast({
                        "type": "message",
                        "from": player_id,
                        "text": text,
                        "level": "low",
                        "blocked": False,
                        "warned": False,
                        "reason": "",
                    })
                    await room.notify_supervisors({
                        "type": "supervisor_message",
                        "from": player_id,
                        "text": text,
                        "level": "low",
                        "blocked": False,
                        "warned": False,
                        "risk": False,
                        "reason": "",
                        "ts": ts,
                    })
                    continue

                blocked = result["action"] == "block"
                ts = datetime.now(timezone.utc).isoformat()

                if blocked:
                    await websocket.send_json({
                        "type": "blocked",
                        "text": text,
                        "reason": result["reason"],
                        "level": result["level"],
                    })
                else:
                    await room.broadcast({
                        "type": "message",
                        "from": player_id,
                        "text": text,
                        "level": result["level"],
                        "blocked": False,
                        "warned": result["action"] == "warn",
                        "reason": result["reason"] if result["risk"] else "",
                    })

                # Supervisors see ALL messages (including blocked)
                await room.notify_supervisors({
                    "type": "supervisor_message",
                    "from": player_id,
                    "text": text,
                    "level": result["level"],
                    "blocked": blocked,
                    "warned": result["action"] == "warn",
                    "risk": result["risk"],
                    "reason": result["reason"],
                    "ts": ts,
                })

                # Update ephemeral stats and push to supervisors
                _update_stats(result)
                await room.notify_supervisors({
                    "type": "stats_update",
                    **get_ephemeral_stats(),
                })

                # Dashboard + supervisors get alert on risk
                if result["risk"]:
                    alert = {
                        "type": "alert",
                        "room": room_id,
                        "from": player_id,
                        "text": text,
                        "level": result["level"],
                        "reason": result["reason"],
                        "action": result["action"],
                        "ts": ts,
                    }
                    await room.notify_dashboards(alert)
                    await room.notify_supervisors({**alert, "type": "supervisor_alert"})

            # ── Ping ──────────────────────────────────────────────────────────
            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        if player_id and player_id in room.players:
            room.players.pop(player_id)
            await room.broadcast({"type": "player_left", "player_id": player_id})
            await room.notify_supervisors({
                "type": "player_left",
                "player_id": player_id,
                "players": list(room.players.keys()),
            })
        if not room.players and not room.supervisor_listeners:
            _rooms.pop(room_id, None)


@router.websocket("/ws/game/{room_id}/dashboard")
async def room_dashboard_ws(websocket: WebSocket, room_id: str):
    """Dashboard connects here to receive alerts for a specific room."""
    await websocket.accept()
    room = _get_or_create_room(room_id)
    room.dashboard_listeners.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        room.dashboard_listeners.discard(websocket)


@router.websocket("/ws/game/{room_id}/supervisor")
async def room_supervisor_ws(websocket: WebSocket, room_id: str):
    """Admin supervisor — receives ALL messages + alerts + player events."""
    await websocket.accept()
    room = _get_or_create_room(room_id)
    room.supervisor_listeners.add(websocket)
    # Send current room state + initial stats snapshot on connect
    await websocket.send_json({
        "type": "room_state",
        "room": room_id,
        "players": list(room.players.keys()),
    })
    await websocket.send_json({"type": "stats_update", **get_ephemeral_stats()})
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ping
    except WebSocketDisconnect:
        pass
    finally:
        room.supervisor_listeners.discard(websocket)


def _moderate(text: str, game_id: str, session_id: str, player_id: str, target_id: str) -> dict:
    """Sync wrapper for the analysis pipeline — runs in executor.
    No message content is persisted (ephemeral-only, legal compliance)."""
    from analyzer import analyze_message
    from context import push_message

    result = analyze_message(
        message=text,
        game_id=game_id,
        session_id=session_id,
        player_id=player_id,
        target_id=target_id,
    )
    push_message(
        game_id=game_id,
        session_id=session_id,
        player_id=player_id,
        target_id=target_id,
        message=text,
        risk=result.risk,
        level=result.level.value,
    )
    return result.model_dump()
