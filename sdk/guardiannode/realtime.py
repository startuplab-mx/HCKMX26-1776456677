"""
GuardianNode Python SDK — WebSocket realtime client.

Connects directly to /ws/game/{room} and handles the full
message protocol: join, send, receive, alerts, auto-reconnect.
"""
import json
import threading
import time
from typing import Callable, Optional
from .models import AnalysisResult, AlertEvent, ChatMessage, RiskLevel, Action

try:
    import websocket  # websocket-client
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False


class GuardianNodeRealtime:
    """
    WebSocket client for real-time game chat moderation.

    Usage:
        gn = GuardianNodeRealtime("ws://localhost:8000", "my-room", "Player1", "MyGame")
        gn.on_message(lambda msg: print(msg.text))
        gn.on_alert(lambda alert: print(f"ALERT: {alert.reason}"))
        gn.connect()
        gn.send("hola!")
        gn.disconnect()
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8000",
        room_id:    str = "default",
        player_id:  str = "Player1",
        game_id:    str = "MyGame",
        auto_reconnect: bool = True,
        reconnect_delay: float = 3.0,
    ):
        if not _WS_AVAILABLE:
            raise ImportError("pip install websocket-client")

        self.server_url      = server_url.rstrip("/")
        self.room_id         = room_id
        self.player_id       = player_id
        self.game_id         = game_id
        self.auto_reconnect  = auto_reconnect
        self.reconnect_delay = reconnect_delay

        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = threading.Event()
        self._stop      = threading.Event()
        self._players: list[str] = []

        # Callbacks
        self._on_message:    Optional[Callable[[ChatMessage], None]]  = None
        self._on_alert:      Optional[Callable[[AlertEvent], None]]   = None
        self._on_blocked:    Optional[Callable[[ChatMessage], None]]  = None
        self._on_connect:    Optional[Callable[[], None]]             = None
        self._on_disconnect: Optional[Callable[[], None]]             = None

    # ── Callback registration ──────────────────────────────────────────────────

    def on_message(self, fn: Callable[[ChatMessage], None]):
        """Called when a chat message is received (allowed or warned)."""
        self._on_message = fn
        return self

    def on_alert(self, fn: Callable[[AlertEvent], None]):
        """Called when a risk alert is detected."""
        self._on_alert = fn
        return self

    def on_blocked(self, fn: Callable[[ChatMessage], None]):
        """Called when YOUR message was blocked by moderation."""
        self._on_blocked = fn
        return self

    def on_connect(self, fn: Callable[[], None]):
        self._on_connect = fn
        return self

    def on_disconnect(self, fn: Callable[[], None]):
        self._on_disconnect = fn
        return self

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, block: bool = False):
        """Connect to the game room. Non-blocking by default."""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if block:
            self._connected.wait(timeout=10)

    def disconnect(self):
        self._stop.set()
        self.auto_reconnect = False
        if self._ws:
            self._ws.close()

    def wait_connected(self, timeout: float = 10.0) -> bool:
        return self._connected.wait(timeout=timeout)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def players(self) -> list[str]:
        return list(self._players)

    # ── Send ───────────────────────────────────────────────────────────────────

    def send(self, text: str):
        """Send a chat message. GuardianNode will analyze it server-side."""
        if not self.connected:
            raise RuntimeError("Not connected")
        self._ws.send(json.dumps({"type": "message", "text": text}))

    # ── Internal ───────────────────────────────────────────────────────────────

    def _run_loop(self):
        url = f"{self.server_url}/ws/game/{self.room_id}"
        while not self._stop.is_set():
            self._ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_ws_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self._ws.run_forever(ping_interval=20, ping_timeout=10)
            if not self.auto_reconnect or self._stop.is_set():
                break
            time.sleep(self.reconnect_delay)

    def _on_open(self, ws):
        ws.send(json.dumps({
            "type":      "join",
            "player_id": self.player_id,
            "game_id":   self.game_id,
        }))

    def _on_ws_message(self, ws, raw: str):
        try:
            data = json.loads(raw)
        except Exception:
            return

        msg_type = data.get("type")

        if msg_type == "joined":
            self._players = data.get("players", [])
            self._connected.set()
            if self._on_connect:
                self._on_connect()

        elif msg_type == "player_joined":
            pid = data.get("player_id")
            if pid and pid not in self._players:
                self._players.append(pid)

        elif msg_type == "player_left":
            pid = data.get("player_id")
            self._players = [p for p in self._players if p != pid]

        elif msg_type == "message":
            if self._on_message:
                self._on_message(ChatMessage.from_dict(data))
            if data.get("risk") and self._on_alert:
                self._on_alert(AlertEvent(
                    level=RiskLevel(data.get("level", "low")),
                    reason=data.get("reason", ""),
                    action=Action(data.get("action", "warn")),
                    from_=data.get("from", ""),
                    text=data.get("text", ""),
                    room=self.room_id,
                ))

        elif msg_type == "blocked":
            msg = ChatMessage.from_dict(data)
            if self._on_blocked:
                self._on_blocked(msg)
            if self._on_alert:
                self._on_alert(AlertEvent(
                    level=RiskLevel(data.get("level", "high")),
                    reason=data.get("reason", ""),
                    action=Action.block,
                    from_=self.player_id,
                    text=data.get("text", ""),
                    room=self.room_id,
                ))

        elif msg_type == "alert":
            if self._on_alert:
                self._on_alert(AlertEvent.from_dict({**data, "room": self.room_id}))

    def _on_error(self, ws, error):
        self._connected.clear()

    def _on_close(self, ws, code, msg):
        self._connected.clear()
        if self._on_disconnect:
            self._on_disconnect()
