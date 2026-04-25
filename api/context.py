"""
Conversation context manager — Redis Lists.

Key: conv:{game_id}:{session_id}:{min(p1,p2)}:{max(p1,p2)}
Stores last MAX_MESSAGES entries, TTL resets on each new message.
Bidirectional: A→B and B→A share same key so LLM sees full exchange.

Player risk index: player_risk:{game_id}:{player_id}
Tracks risk events across ALL conversations in a room (multi-victim detection).
"""
import json
import redis
from datetime import datetime, timezone
from config import get_settings

settings = get_settings()

MAX_MESSAGES = 15           # increased for more pattern visibility
TTL_SECONDS = 1800          # 30 min inactivity resets context
ESCALATION_WINDOW = 300     # 5 min — rapid escalation = immediate flag
RISK_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
ESCALATION_SCORE_THRESHOLD = 4  # weighted score to trigger escalation floor

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _conv_key(game_id: str, player_id: str, target_id: str, session_id: str) -> str:
    p1, p2 = sorted([player_id, target_id])
    return f"conv:{game_id}:{session_id}:{p1}:{p2}"


def _player_risk_key(game_id: str, player_id: str) -> str:
    return f"player_risk:{game_id}:{player_id}"


def _relative_time(ts_iso: str, reference_iso: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_iso)
        ref = datetime.fromisoformat(reference_iso)
        delta = int((ref - ts).total_seconds())
        if delta < 10:
            return "ahora"
        if delta < 60:
            return f"{delta}s atrás"
        if delta < 3600:
            return f"{delta // 60}m atrás"
        return f"{delta // 3600}h atrás"
    except Exception:
        return ""


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
    now = datetime.now(timezone.utc).isoformat()
    entry = json.dumps({
        "from": player_id,
        "msg": message[:500],
        "ts": now,
        "risk": risk,
        "level": level,
    })
    pipe = r.pipeline()
    pipe.rpush(key, entry)
    pipe.ltrim(key, -MAX_MESSAGES, -1)
    pipe.expire(key, TTL_SECONDS)

    # Global player risk index — track across all victims in this room
    if risk:
        risk_entry = json.dumps({"ts": now, "level": level, "target": target_id})
        risk_key = _player_risk_key(game_id, player_id)
        pipe.rpush(risk_key, risk_entry)
        pipe.ltrim(risk_key, -20, -1)
        pipe.expire(risk_key, TTL_SECONDS)

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


def get_player_global_risk(game_id: str, player_id: str) -> list[dict]:
    """Risk events for player across ALL conversations in this game room."""
    r = _get_redis()
    raw = r.lrange(_player_risk_key(game_id, player_id), 0, -1)
    return [json.loads(e) for e in raw]


def format_context_for_llm(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
    current_message: str,
) -> str:
    history = get_context(game_id, session_id, player_id, target_id)
    global_risk = get_player_global_risk(game_id, player_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    lines = []

    # Mejora 2: contexto global — alerta si jugador tiene historial con otras víctimas
    if global_risk:
        other_targets = {e.get("target") for e in global_risk if e.get("target") != target_id}
        total = len(global_risk)
        lines.append(
            f"[⚠️ ALERTA GLOBAL: JUGADOR_A acumula {total} evento(s) de riesgo en esta sala"
            + (f" — contactó a {len(other_targets)} jugador(es) distinto(s)" if other_targets else "")
            + "]"
        )

    if history:
        lines.append("[HISTORIAL DE CONVERSACIÓN — mensajes recientes]")
        for entry in history:
            sender = "JUGADOR_A" if entry["from"] == player_id else "JUGADOR_B"
            # Mejora 1: timestamps relativos
            rel = _relative_time(entry["ts"], now_iso)
            prefix = f"[{rel}] " if rel else ""
            # Mejora 4: nivel de riesgo explícito en lugar de solo emoji
            if entry["risk"]:
                lvl = entry["level"].upper()
                flag = f" ⚠️[RIESGO:{lvl}]"
            else:
                flag = ""
            lines.append(f"{prefix}[{sender}]: {entry['msg']}{flag}")
        lines.append("")

    lines.append("[MENSAJE NUEVO A ANALIZAR]")
    lines.append(f"[JUGADOR_A]: {current_message}")
    lines.append("")
    lines.append("Analiza el MENSAJE NUEVO considerando el patrón de la conversación completa.")

    return "\n".join(lines)


def has_escalating_pattern(
    game_id: str,
    session_id: str,
    player_id: str,
    target_id: str,
) -> bool:
    """
    Weighted escalation check across conversation history + global player risk.

    Mejora 3: score ponderado por nivel (high=3, medium=2, low=1) vs conteo plano.
    Mejora 5: ventana temporal — 2+ msgs riesgosos en 5min = flag inmediato.
    Mejora 2: suma eventos globales de otras víctimas al score.
    """
    history = get_context(game_id, session_id, player_id, target_id)
    global_risk = get_player_global_risk(game_id, player_id)
    now = datetime.now(timezone.utc)

    conv_score = 0
    recent_risk_count = 0

    for entry in history:
        if entry.get("risk") and entry.get("from") == player_id:
            conv_score += RISK_WEIGHTS.get(entry.get("level", "low"), 1)
            try:
                ts = datetime.fromisoformat(entry["ts"])
                if (now - ts).total_seconds() <= ESCALATION_WINDOW:
                    recent_risk_count += 1
            except Exception:
                pass

    # Mejora 5: escalamiento rápido — 2+ eventos en ventana de 5 min
    if recent_risk_count >= 2:
        return True

    # Score de otras víctimas en la misma sala
    global_score = sum(
        RISK_WEIGHTS.get(e.get("level", "low"), 1)
        for e in global_risk
        if e.get("target") != target_id
    )

    return (conv_score + global_score) >= ESCALATION_SCORE_THRESHOLD
