"""
Automated edge case tests — 5 bots in a group room.
Usage:
    pip install websockets
    python tests/test_edge_cases.py [ws://localhost:8000]
"""
import asyncio
import json
import sys
import time

WS_BASE = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000"
GAME = "test-suite"
API_KEY = "guardiannode-dev-secret"
DELAY = 0.6  # seconds between messages — must be > LLM p95 latency

# ── Test scenarios ─────────────────────────────────────────────────────────────
# Each: (room_suffix, sender_bot, message, expected_action, description)
# expected_action = "skip" → LLM-dependent, result is informational only
SCENARIOS = [
    # ── Benign ────────────────────────────────────────────────────────────────
    ("A", "bot1", "hola que onda",                          "allow", "saludo normal"),
    ("A", "bot2", "bien bien, jugamos?",                    "allow", "respuesta normal"),
    ("A", "bot3", "gg nice shot",                           "allow", "trash talk ok"),
    ("A", "bot4", "alguien tiene mic?",                     "allow", "pregunta de juego"),
    ("A", "bot5", "voy a reconnect ahorita",                "allow", "aviso de juego"),

    # ── Grooming sexual — Tier-1 (prefilter) ──────────────────────────────────
    ("B", "bot1", "mandame una foto de tu cuarto",          "block", "solicitud foto física"),
    ("B", "bot1", "mandame tus nudes",                      "block", "solicitud desnudos"),
    ("B", "bot2", "tu usuario de phub?",                    "block", "referencia plataforma adulta"),
    ("B", "bot3", "quiero cogerte",                         "block", "solicitud sexual explícita"),
    ("B", "bot3", "que culito tan rico tienes",             "block", "comentario sexual cuerpo"),

    # ── Grooming sexual — LLM-dependent ───────────────────────────────────────
    ("C", "bot1", "cuantos años tienes",                    "warn",  "sondeo edad"),
    ("C", "bot1", "estas solo ahorita?",                    "warn",  "sondeo aislamiento"),

    # ── Reclutamiento cartel — Tier-1 ─────────────────────────────────────────
    ("D", "bot2", "el patron te busca para trabajar",       "block", "reclutamiento directo"),
    ("D", "bot4", "4vis4 si v3s p4trull4s",                 "block", "halconeo leet speak"),
    ("D", "bot4", "avisa si ves patrullas por la esquina",  "block", "halconeo plain"),
    ("D", "bot5", "pasate a mi discord privado",            "block", "migración plataforma"),
    ("D", "bot5", "d.i.s.c.o.r.d privado te doy info",     "block", "migración dot-separated"),
    ("D", "bot1", "no le digas a tus papas de esto",        "block", "instrucción secretismo"),
    ("D", "bot2", "te aliviano con 4000 a la semana",       "block", "oferta pago criminal"),
    ("D", "bot3", "cuatro letras te llama a laborar",       "block", "reclutamiento CJNG"),

    # ── Reclutamiento cartel — LLM-dependent ──────────────────────────────────
    ("E", "bot2", "hay buen jale si quieres",               "warn",  "oferta laboral vaga"),

    # ── Emojis cartel — Tier-1 ────────────────────────────────────────────────
    ("F", "bot4", "🍕🐓 jalense a laborar",                 "block", "emoji cartel + recruit"),
    ("F", "bot4", "🍕🐓",                                   "warn",  "dos emojis cartel distintos"),

    # ── Leet speak / ofuscación — Tier-1 ──────────────────────────────────────
    ("G", "bot1", "p4s4t3 al d1sc0rd",                      "block", "leet migración"),
    ("G", "bot2", "h-a-l-c-o-n en la zona",                 "block", "dash-separated halcon"),
    ("G", "bot3", "Qu1er3s un j4l3?",                       "allow", "leet jale — ambiguo sin contexto"),

    # ── Contexto escalante ─────────────────────────────────────────────────────
    ("H", "bot5", "eres muy buen jugador",                  "allow", "elogio inicio grooming"),
    ("H", "bot5", "cuantos años tienes hermano",            "warn",  "sondeo edad post-elogio"),
    ("H", "bot5", "estas solito?",                          "skip",  "aislamiento post-elogio (LLM contexto)"),
]

# ─────────────────────────────────────────────────────────────────────────────

results = {"pass": 0, "fail": 0, "skip": 0}


async def make_bot(bot_id: str, room_id: str):
    import websockets
    uri = f"{WS_BASE}/ws/game/{room_id}"
    ws = await websockets.connect(uri)
    await ws.send(json.dumps({"type": "join", "room": room_id, "player_id": bot_id, "game_id": GAME}))
    resp = json.loads(await ws.recv())
    assert resp["type"] == "joined", f"Join failed: {resp}"
    return ws


async def drain(ws, timeout=0.3) -> list[dict]:
    """Collect all pending messages within timeout."""
    msgs = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msgs.append(json.loads(raw))
    except asyncio.TimeoutError:
        pass
    return msgs


async def run():
    import websockets

    base_room = f"test-{int(time.time())}"
    print(f"\n{'='*60}")
    print(f"Base room: {base_room}  |  {WS_BASE}")
    print(f"{'='*60}\n")

    # Create one room per suffix, connect bots as needed
    rooms: dict[str, dict] = {}  # suffix → {bot_id: ws}

    async def get_bot(suffix: str, bot_id: str):
        room_id = f"{base_room}-{suffix}"
        if suffix not in rooms:
            rooms[suffix] = {}
        if bot_id not in rooms[suffix]:
            ws = await make_bot(bot_id, room_id)
            rooms[suffix][bot_id] = ws
            # Drain join notifications
            await drain(ws, 0.3)
            # Drain all existing bots in room (they got player_joined)
            for bid, bws in rooms[suffix].items():
                if bid != bot_id:
                    await drain(bws, 0.1)
        return rooms[suffix][bot_id]

    # Run scenarios
    for suffix, sender, message, expected, desc in SCENARIOS:
        ws = await get_bot(suffix, sender)

        await ws.send(json.dumps({"type": "message", "text": message}))
        await asyncio.sleep(DELAY)

        responses = await drain(ws, 0.6)

        # Determine actual action
        actual = "allow"
        reason = ""
        for r in responses:
            if r.get("type") == "blocked":
                actual = "block"
                reason = r.get("reason", "")
                break
            if r.get("type") == "message":
                actual = "warn" if r.get("warned") else "allow"
                reason = r.get("reason", "")
                break
            if r.get("type") == "error":
                actual = "error"
                reason = r.get("detail", "")
                break

        if expected == "skip":
            icon = "⏭"
            results["skip"] += 1
        elif actual == "error":
            icon = "⚡"
            results["skip"] += 1
        elif actual == expected:
            icon = "✓"
            results["pass"] += 1
        else:
            icon = "✗"
            results["fail"] += 1

        print(f"  {icon} [{sender}/{suffix}] {desc}")
        if icon == "✗":
            print(f"      msg:      {message!r}")
            print(f"      expected: {expected}  got: {actual}  reason: {reason!r}")

    # Disconnect all
    for suffix_bots in rooms.values():
        for ws in suffix_bots.values():
            await ws.close()

    print(f"\n{'='*60}")
    print(f"  PASS: {results['pass']}  FAIL: {results['fail']}  SKIP: {results['skip']}")
    print(f"{'='*60}\n")

    if results["fail"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    try:
        import websockets  # noqa
    except ImportError:
        print("Install: pip install websockets")
        sys.exit(1)

    asyncio.run(run())
