import json
import hashlib
import time
from typing import Optional
import litellm
from models import AnalysisResult, RiskLevel, Action
from config import get_settings
from prefilter import prefilter
from cleaner import normalizar_texto

litellm.drop_params = True  # ignore unsupported params per provider

settings = get_settings()

_RESULT_CACHE_TTL = 60  # seconds — same player+message reuses result

SYSTEM_PROMPT = """Eres GuardianNode, sistema de protección de menores en chats de videojuegos. Tu misión es detectar amenazas reales contra menores.

AMENAZAS A DETECTAR:

A) RECLUTAMIENTO CRIMINAL (cárteles mexicanos):
- Ofertas de trabajo/dinero fácil: "hay jale", "te pago bien", "ganas bien", "solo llevas algo"
- Reclutamiento directo: "el patrón/jefe quiere hablar", "únete al equipo", "la organización te necesita"
- Secretismo: "no le digas a tus papás", "borra este mensaje", "esto es entre nosotros"
- Migración fuera del juego: "escríbeme al WhatsApp/Telegram/Discord", "te mando mi número"
- Pedir ubicación física: "¿dónde vives?", "¿de qué colonia eres?", "podemos vernos"
- Normalización criminal: glorificar cartel como aspiracional, "todos lo hacen", "así se vive bien"

B) GROOMING SEXUAL:
- Solicitar imágenes: "mándame fotos", "muéstrate en cámara", "nudes", "una foto tuya"
- Propuestas sexuales: cualquier referencia sexual explícita hacia el menor
- Sondeo: preguntar si es virgen, si tiene pareja, sobre experiencias sexuales
- Elogios corporales con intención: "qué bonito/a cuerpo", "debes estar muy bueno/a"
- Aislar: "¿estás solo/a?", "¿tus papás están en casa?", "¿tienes privacidad?"
- Extorsión: "si no me mandas fotos, le digo a todos", chantaje con imágenes

CÓDIGOS CÁRTELES MX:
🍕/chapizza=Sinaloa | 🐓/mencho/el gallo/🆖/4L/NG=CJNG | 🍇/unión/tepito=Unión Tepito | 🥷=operador
la empresa/organización/plebada/compañía=cártel | jale bueno/buen jale=trabajo criminal
halcón/halconeo=vigilancia para cartel | burrero/mula/brincar el charco=transporte drogas
sicario=asesino | plaza=territorio cartel | la línea=comunicación cartel

CRITERIOS DE DECISIÓN:
- BLOCK (high): grooming sexual explícito, oferta criminal directa, secretismo + menor, solicitud de ubicación física
- WARN (medium): señales ambiguas de reclutamiento, migración a otra plataforma, preguntas de sondeo, cualquier duda
- ALLOW (low): conversación normal de videojuego, palabras de jerga sin contexto criminal

FALSOS POSITIVOS — NO son riesgo:
- jale = halar objeto en juego (sin contexto de dinero/trabajo)
- rifado/chido/neta/carnal/bro/cuate = jerga juvenil normal
- ¿cuántos años tienes? solo, sin seguimiento sexual o criminal
- preguntas de ping/lag/rank/servidor/cuenta del juego
- números sueltos sin contexto de oferta (500, 4000)
- JUGADOR_A dice "no"/"no quiero"/"paso" = NO es riesgo, es rechazo

REGLA CRÍTICA: Si hay duda → usa medium+warn. Es mejor una alerta falsa que dejar pasar abuso.
Evalúa SOLO la intención de JUGADOR_A en el MENSAJE NUEVO. No atribuyas riesgo de JUGADOR_B a JUGADOR_A.

Responde ÚNICAMENTE con JSON válido (sin texto extra):
{"risk":bool,"level":"low|medium|high","reason":"descripción breve max 100 chars","action":"block|warn|allow"}"""


def _real_key(k: str) -> bool:
    return bool(k) and k not in ("", "nvapi-...", "sk-ant-...") and "..." not in k


# Provider waterfall: best quality first, small/fast models as fallbacks
# Each entry: (litellm_model_string, api_key_getter, extra_params)
def _build_provider_list() -> list[dict]:
    providers = []

    if _real_key(settings.google_api_key):
        providers.append({
            "model": "gemini/gemini-2.0-flash",
            "api_key": settings.google_api_key,
        })

    if _real_key(settings.cerebras_api_key):
        providers.append({
            "model": "cerebras/llama3.1-70b",
            "api_key": settings.cerebras_api_key,
        })

    if _real_key(settings.together_api_key):
        providers.append({
            "model": "together_ai/meta-llama/Llama-4-Scout-17B-16E-Instruct",
            "api_key": settings.together_api_key,
        })

    if _real_key(settings.anthropic_api_key):
        providers.append({
            "model": "claude-haiku-4-5-20251001",
            "api_key": settings.anthropic_api_key,
        })

    if _real_key(settings.groq_api_key):
        providers.append({
            "model": "groq/llama-3.1-8b-instant",
            "api_key": settings.groq_api_key,
        })

    if _real_key(settings.nvidia_api_key):
        providers.append({
            "model": "openai/meta/llama-3.1-8b-instruct",
            "api_key": settings.nvidia_api_key,
            "api_base": "https://integrate.api.nvidia.com/v1",
        })

    return providers


_SAFE_FALLBACK = AnalysisResult(
    risk=True,
    level=RiskLevel.medium,
    reason="No se pudo analizar — conservador por defecto",
    action=Action.warn,
)


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


def _call_llm_with_fallback(prompt: str, system_override: Optional[str] = None) -> AnalysisResult:
    system = system_override or SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _wrap_prompt(prompt)},
    ]
    providers = _build_provider_list()
    if not providers:
        raise RuntimeError("No LLM providers configured — set at least one API key in .env")

    last_err = None
    for p in providers:
        kwargs = {
            "model": p["model"],
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.0,
            "api_key": p["api_key"],
        }
        if "api_base" in p:
            kwargs["api_base"] = p["api_base"]

        for attempt in range(2):
            try:
                response = litellm.completion(**kwargs)
                return _parse_llm_response(response.choices[0].message.content)
            except Exception as e:
                last_err = e
                is_429 = "429" in str(e) or "rate" in str(e).lower()
                if is_429 and attempt == 0:
                    time.sleep(1)
                    continue
                break  # non-429 error or second attempt → try next provider

    raise RuntimeError(f"All LLM providers failed. Last: {last_err}")


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
