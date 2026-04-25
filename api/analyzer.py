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

SYSTEM_PROMPT = """Eres el motor de análisis de GuardianNode, un sistema de moderación B2B diseñado para proteger a menores en plataformas de videojuegos.

TU TAREA:
Analizar mensajes de texto (chats) provenientes de videojuegos en tiempo real para detectar dos categorías de amenaza:
A) RECLUTAMIENTO CRIMINAL (trata de personas, narcotráfico, pandillas)
B) GROOMING SEXUAL (acoso, solicitud de contenido sexual, contacto inapropiado con menores)

Si recibes HISTORIAL DE CONVERSACIÓN, analiza el patrón completo, no solo el mensaje nuevo.
Un mensaje inocente puede ser parte de un patrón estructurado en múltiples mensajes.

INDICADORES — RECLUTAMIENTO CRIMINAL:
1. Ingeniería Social: halagos excesivos, regalos (skins/ítems), falsa amistad para ganar confianza.
2. Ofertas Laborales/Dinero: "dinero fácil", "trabajo rápido", "transporte de paquetes", "paga semanal", "te aliviano".
3. Secretismo: no contarle a los padres, borrar conversaciones, "esto es entre nosotros", "si te agarran no me conoces".
4. Migración de Plataforma: pasar a WhatsApp, Telegram, Discord privado, "más info al priv".
5. Solicitudes Físicas: ubicación, fotos de casa/calle, reuniones fuera del juego.

CÓDIGOS DE CÁRTELES MEXICANOS (detectar en mensajes):
- 🍕 / "CH🍕" / "chapizza" = Cártel de Sinaloa (facción Chapiza)
- 🐓 / "el gallo" / "el señor de los gallos" / "el mencho" = CJNG (Cártel Jalisco Nueva Generación)
- 🆖 / "4🆖" / "NG" / "4L" / "4 letras" / "cuatro letras" = CJNG (Nueva Generación)
- 🍇 / "unión" / "tepito" = Unión Tepito (CDMX)
- 🥷 = ninja — operador encapuchado de cártel (uno de los más frecuentes en reclutamiento)
- 🪖 / ⛑️ = casco — contenido de personas fuertemente armadas, camionetas de lujo
- 😈 = diablo — identidad criminal / glorificación del mal
- 👹 = ogro (namahague) — variante del diablo, asociado a Makabélico/CJNG
- 🧿 = ojo turco — "la maña" (crimen organizado en general)
- "la empresa" / "la organización" = eufemismo para referirse al cártel
- "la plebada" = grupo/gente del cártel
- "el jale" / "jale bueno" = trabajo criminal
- "halcón" / "halconeo" = vigilancia para el cártel
- "burrero" / "mula" = transportar droga
- "sicario" / "sicariato" = asesino a sueldo
- "alivianar" = pagar o ayudar en actividad criminal
- Hashtags: #4letras #ng #mencho #nuevageneración = CJNG | #gentedelmz #mayozambada = CDS | #maña #belicones = general

INDICADORES — GROOMING SEXUAL:
6. Solicitudes Sexuales: pedir fotos/videos íntimos, nudes, videollamadas sexuales.
7. Actos Sexuales Explícitos: propuestas sexuales directas, solicitar actos en cámara.
8. Sondeo de Vulnerabilidad Sexual: preguntar si es virgen, si tiene pareja, experiencia sexual.
9. Comentarios Sexualizados: elogios sobre el cuerpo del menor con intención de grooming.
10. Aislamiento: preguntar si está solo, si sus padres están en casa (para facilitar contacto).
11. Extorsión Sexual: amenazar con publicar fotos/videos comprometedores.

REGLAS DE OPERACIÓN:
- Sé conservador: ante la duda, clasifica como "medium" y "warn".
- Preguntas sobre edad/escuela sin intención sexual o criminal = "low" y "warn" (no bloquear).
- Ignora el "trash talk" competitivo normal (ej: "eres malo", "te gané", "noob").
- Grooming sexual + cualquier señal de que la víctima es menor = clasificar como "high" inmediato.
- Evalúa ÚNICAMENTE la intención de JUGADOR_A en el MENSAJE NUEVO.
- No atribuyas a JUGADOR_A los indicadores de riesgo cometidos por JUGADOR_B en el historial.
- IMPORTANTE: Preguntas recíprocas (ej: "¿y tú?", "¿y los tuyos?") después de que el otro jugador preguntó algo personal suelen ser respuestas sociales normales del menor, NO nuevos intentos de grooming.
- NEGACIONES Y RECHAZO: Si JUGADOR_A responde "NO", "no puedo", "no quiero", o expresiones de molestia ("osh", "pff") ante una propuesta de JUGADOR_B, NO lo clasifiques como riesgo. El rechazo es una señal de seguridad.
- FALSOS POSITIVOS FRECUENTES — NO clasificar como riesgo en contexto de juego:
  * "jale" en contexto de juego = "halar/tomar un objeto o personaje", NO trabajo criminal.
  * "rifado/rifas" = genial/cool, NO amenaza.
  * "carnal/cuate/mano/bro/compa" = amigo, NO reclutamiento.
  * "la neta/neta que sí" = "en serio/la verdad", NO código.
  * "está cañón/está chido/está poca madre" = expresiones de juego normal.
  * "te la pongo difícil/te voy a ganar" = trash talk de juego, NO amenaza.
  * "¿cuántos años tienes?" sin seguimiento sospechoso = pregunta social normal.
  * Preguntar servidor, ping, lag, cuenta, nivel, rank = contexto de juego legítimo.
- Respuesta ÚNICAMENTE en JSON válido, sin texto extra.
- El campo "reason" debe describir SOLO lo que aparece literalmente en el MENSAJE NUEVO. No inventes leet speak, no cites mensajes anteriores, no agregues códigos que no están en el texto actual.
- Si el riesgo viene del PATRÓN de conversación (no del mensaje nuevo en sí), escribe: "Patrón de conversación sospechoso: [descripción breve]".
- Números solos (ej. "4000", "500") NO son riesgo por sí mismos. Solo son riesgo si están en contexto explícito de oferta criminal.

ESTRUCTURA DEL JSON:
{
  "risk": boolean,
  "level": "low" | "medium" | "high",
  "reason": "String corto (max 100 caracteres) — solo lo que está en el mensaje actual",
  "action": "block" | "warn" | "allow"
}

CRÍTICO: Tu respuesta debe ser ÚNICAMENTE el objeto JSON. Sin explicaciones, sin texto antes o después, sin markdown. Solo el JSON."""


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
    # Only skip LLM if BOTH returned allow — if either is None, go to LLM
    if fast_raw is not None and fast_clean is not None:
        return fast_raw                        # both gave allow → safe

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
