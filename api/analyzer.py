import json
import hashlib
import httpx
import anthropic as _anthropic
from models import AnalysisResult, RiskLevel, Action
from config import get_settings
from prefilter import prefilter
from cleaner import normalizar_texto

settings = get_settings()

_RESULT_CACHE_TTL = 60  # seconds — same player+message reuses result

SYSTEM_PROMPT = """Eres GuardianNode, moderador de chats en videojuegos. Detecta 2 amenazas contra menores:

A) RECLUTAMIENTO CRIMINAL: ingeniería social (halagos/regalos/amistad falsa), ofertas dinero/trabajo fácil, secretismo ("no le digas a tus papás"/"borra esto"), migración a otra plataforma (WhatsApp/Telegram/Discord privado), pedir ubicación/fotos/reuniones físicas.

B) GROOMING SEXUAL: solicitar fotos/videos íntimos o nudes, propuestas sexuales explícitas, sondeo (virgen/pareja/experiencia sexual), elogios corporales con intención sexual, preguntar si está solo/si sus padres están, extorsión con fotos.

CÓDIGOS CÁRTELES MX:
🍕/chapizza/CH🍕=Sinaloa | 🐓/mencho/el gallo=CJNG | 🆖/4L/NG/4letras/cuatro letras=CJNG | 🍇/unión/tepito=Unión Tepito | 🥷=operador | 🧿=la maña
la empresa/organización/plebada=cártel | jale bueno=trabajo criminal | halcón=vigilancia | burrero/mula=droga | sicario=asesino | alivianar=pagar criminal
#4letras #mencho #nuevageneración=CJNG | #gentedelmz #mayozambada=CDS | #maña #belicones=general

REGLAS:
- Duda → medium+warn. Grooming+menor confirmado → high+block inmediato.
- Evalúa SOLO intención de JUGADOR_A en MENSAJE NUEVO. No atribuyas riesgo de JUGADOR_B a JUGADOR_A.
- JUGADOR_A rechaza con "no"/"no quiero"/"pff"/"osh" → NO es riesgo.
- Preguntas recíprocas ("¿y tú?") tras pregunta personal de JUGADOR_B = respuesta social normal.
- NO son riesgo: jale=halar objeto en juego, rifado=cool, carnal/bro/cuate=amigo, neta=verdad, ¿cuántos años? sin seguimiento, preguntas de ping/rank/servidor/cuenta.
- Números solos ("4000","500") → riesgo solo si contexto explícito de oferta criminal.
- "reason" describe SOLO el MENSAJE NUEVO (<100 chars). Riesgo por patrón → "Patrón: [descripción breve]".

Responde ÚNICAMENTE: {"risk":bool,"level":"low|medium|high","reason":"...","action":"block|warn|allow"}"""


# Provider registry: name → (base_url, model, uses_openai_compat)
_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "api_key": lambda: settings.groq_api_key,
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.1-8b-instruct",
        "api_key": lambda: settings.nvidia_api_key,
    },
    "anthropic": {
        "base_url": None,  # uses SDK
        "model": "claude-haiku-4-5-20251001",
        "api_key": lambda: settings.anthropic_api_key,
    },
}

_SAFE_FALLBACK = AnalysisResult(
    risk=True,
    level=RiskLevel.medium,
    reason="No se pudo analizar — conservador por defecto",
    action=Action.warn,
)


def _real_key(k: str) -> bool:
    return bool(k) and k not in ("", "nvapi-...", "sk-ant-...") and "..." not in k


def _parse_llm_response(raw: str) -> AnalysisResult:
    if not raw or not raw.strip():
        return _SAFE_FALLBACK

    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    brace = raw.find("{")
    if brace == -1:
        return _SAFE_FALLBACK

    try:
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(raw, brace)
    except json.JSONDecodeError:
        return _SAFE_FALLBACK

    try:
        return AnalysisResult(
            risk=bool(data["risk"]),
            level=RiskLevel(data["level"]),
            reason=str(data.get("reason", ""))[:100],
            action=Action(data["action"]),
        )
    except (KeyError, ValueError):
        return _SAFE_FALLBACK


def _wrap_prompt(prompt: str) -> str:
    if prompt.startswith("["):
        return prompt + "\n\nResponde SOLO con JSON válido."
    return f"Analiza este mensaje de chat de videojuego:\n\n{prompt}\n\nResponde SOLO con JSON válido."


def _call_provider(name: str, prompt: str, system: str | None) -> AnalysisResult:
    cfg = _PROVIDERS[name]
    system = system or SYSTEM_PROMPT

    if name == "anthropic":
        client = _anthropic.Anthropic(api_key=cfg["api_key"]())
        response = client.messages.create(
            model=cfg["model"],
            max_tokens=128,
            system=system,
            messages=[{"role": "user", "content": _wrap_prompt(prompt)}],
        )
        return _parse_llm_response(response.content[0].text)

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _wrap_prompt(prompt)},
        ],
        "max_tokens": 128,
        "temperature": 0.0,
    }
    resp = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {cfg['api_key']()}", "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return _parse_llm_response(resp.json()["choices"][0]["message"]["content"])


def _call_llm_with_fallback(prompt: str, system_override: str | None = None) -> AnalysisResult:
    primary = settings.llm_provider

    # Build ordered provider list — primary first, then fallbacks with real keys
    fallbacks = [n for n in ("groq", "nvidia", "anthropic") if n != primary and _real_key(_PROVIDERS[n]["api_key"]())]
    providers = [primary] + fallbacks

    last_err = None
    for name in providers:
        for attempt in range(3):
            try:
                return _call_provider(name, prompt, system_override)
            except Exception as e:
                last_err = e
                if "429" in str(e) and attempt < 2:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                break

    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")


def _cache_key(player_id: str, message: str) -> str:
    return "llm_cache:" + hashlib.md5(f"{player_id}:{message}".encode()).hexdigest()


def _get_cached(player_id: str, message: str) -> AnalysisResult | None:
    try:
        from context import _get_redis
        raw = _get_redis().get(_cache_key(player_id, message))
        if raw:
            data = json.loads(raw)
            return AnalysisResult(
                risk=data["risk"],
                level=RiskLevel(data["level"]),
                reason=data["reason"],
                action=Action(data["action"]),
            )
    except Exception:
        pass
    return None


def _set_cached(player_id: str, message: str, result: AnalysisResult) -> None:
    try:
        from context import _get_redis
        _get_redis().setex(
            _cache_key(player_id, message),
            _RESULT_CACHE_TTL,
            json.dumps({"risk": result.risk, "level": result.level.value,
                        "reason": result.reason, "action": result.action.value}),
        )
    except Exception:
        pass


def analyze_message(
    message: str,
    game_id: str = "",
    session_id: str = "",
    player_id: str = "",
    target_id: str = "",
) -> AnalysisResult:
    # Tier 0: normalize obfuscated text before any analysis
    clean = normalizar_texto(message)

    # Tier 1: regex prefilter — 0ms, no network
    # Run on raw first; if raw gives allow but clean gives risk, clean wins
    fast_raw = prefilter(message)
    fast_clean = prefilter(clean)

    if fast_raw is not None and fast_raw.risk:
        return fast_raw                        # raw hit — block/warn on literal text
    if fast_clean is not None and fast_clean.risk:
        return fast_clean                      # clean hit — obfuscated input caught
    if fast_raw is not None:
        return fast_raw                        # both gave allow → return allow
    if fast_clean is not None:
        return fast_clean                      # raw=None, clean=allow → return clean

    # Tier 1.5: result cache — skip LLM for repeated message+player within 60s
    if player_id:
        cached = _get_cached(player_id, clean)
        if cached is not None:
            return cached

    # Tier 2: LLM with optional conversation context (send cleaned message)
    message = clean
    if game_id and session_id and player_id and target_id:
        from context import format_context_for_llm, has_escalating_pattern

        prompt = format_context_for_llm(game_id, session_id, player_id, target_id, message)

        if has_escalating_pattern(game_id, session_id, player_id, target_id):
            result = _call_llm_with_fallback(prompt)
            if not result.risk and result.level == RiskLevel.low:
                result = AnalysisResult(
                    risk=True,
                    level=RiskLevel.medium,
                    reason="Patrón escalante: jugador con historial de riesgo",
                    action=Action.warn,
                )
            if player_id:
                _set_cached(player_id, message, result)
            return result
    else:
        prompt = message

    try:
        result = _call_llm_with_fallback(prompt)
        if player_id:
            _set_cached(player_id, message, result)
        return result
    except Exception as e:
        return AnalysisResult(
            risk=True,
            level=RiskLevel.medium,
            reason=f"Fallo en motor IA (Fail-Close). Error: {str(e)[:50]}",
            action=Action.warn,
        )
