"""
Conversation context manager — Redis Lists.

Key: conv:{game_id}:{min(p1,p2)}:{max(p1,p2)}:{session_id}
Stores last MAX_MESSAGES entries, TTL resets on each new message.
Bidirectional: A→B and B→A share same key so LLM sees full exchange.
"""
import json
import redis
from datetime import datetime
from config import get_settings

settings = get_settings()

MAX_MESSAGES = 10
TTL_SECONDS = 1800  # 30 min of inactivity resets context

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _conv_key(game_id: str, player_id: str, target_id: str, session_id: str) -> str:
    # Normalize order so A→B and B→A share same key
    p1, p2 = sorted([player_id, target_id])
    return f"conv:{game_id}:{session_id}:{p1}:{p2}"


def push_message(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
    message: str,
    risk: bool = False,
    level: str = "low",
) -> None:
    r = _get_redis()
    key = _conv_key(game_id, player_id, target_id, session_id)
    entry = json.dumps({
        "from": player_id,
        "msg": message[:500],
        "ts": datetime.utcnow().isoformat(),
        "risk": risk,
        "level": level,
    })
    pipe = r.pipeline()
    pipe.rpush(key, entry)
    pipe.ltrim(key, -MAX_MESSAGES, -1)  # keep only last N
    pipe.expire(key, TTL_SECONDS)
    pipe.execute()


def get_context(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
) -> list[dict]:
    r = _get_redis()
    key = _conv_key(game_id, player_id, target_id, session_id)
    raw = r.lrange(key, 0, -1)
    return [json.loads(e) for e in raw]


def format_context_for_llm(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
    current_message: str,
) -> str:
    """
    Returns a formatted string to prepend to the LLM prompt.
    If no history exists, returns just the current message.
    """
    history = get_context(game_id, session_id, player_id, target_id)

    if not history:
        return current_message

    lines = ["[HISTORIAL DE CONVERSACIÓN — últimos mensajes]"]
    for entry in history:
        sender = "JUGADOR_A" if entry["from"] == player_id else "JUGADOR_B"
        flag = " ⚠️" if entry["risk"] else ""
        lines.append(f"[{sender}]: {entry['msg']}{flag}")

    lines.append("")
    lines.append("[MENSAJE NUEVO A ANALIZAR]")
    lines.append(f"[JUGADOR_A]: {current_message}")
    lines.append("")
    lines.append(
        "Analiza el MENSAJE NUEVO considerando el patrón de la conversación completa."
    )

    return "\n".join(lines)


def has_escalating_pattern(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
) -> bool:
    """
    Fast check: if player_id already has 2+ risk messages in history,
    next message gets medium floor even if innocuous.
    """
    history = get_context(game_id, session_id, player_id, target_id)
    risk_count = sum(
        1 for e in history
        if e.get("risk") and e.get("from") == player_id
    )
    return risk_count >= 2
