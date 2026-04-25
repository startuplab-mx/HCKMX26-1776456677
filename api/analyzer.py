import json
import httpx
from models import AnalysisResult, RiskLevel, Action
from config import get_settings
from prefilter import prefilter

settings = get_settings()

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
- 🥷 = operador de cártel encapuchado
- 😈 / 👹 = identidad criminal / glorificación del crimen
- 🧿 = "la maña" (crimen organizado en general)
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
- Respuesta ÚNICAMENTE en JSON válido, sin texto extra.

ESTRUCTURA DEL JSON:
{
  "risk": boolean,
  "level": "low" | "medium" | "high",
  "reason": "String corto (max 100 caracteres) explicando el indicador detectado",
  "action": "block" | "warn" | "allow"
}"""


def _parse_llm_response(raw: str) -> AnalysisResult:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    # Extract first JSON object — model sometimes appends extra text
    brace = raw.find("{")
    if brace != -1:
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(raw, brace)
    else:
        data = json.loads(raw)
    return AnalysisResult(
        risk=data["risk"],
        level=RiskLevel(data["level"]),
        reason=data["reason"][:100],
        action=Action(data["action"]),
    )


def _call_openai_compat(prompt: str, base_url: str, api_key: str, model: str, system: str | None = None) -> AnalysisResult:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 128,
        "temperature": 0.0,
    }
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return _parse_llm_response(resp.json()["choices"][0]["message"]["content"])


def analyze_with_groq(prompt: str, system: str | None = None) -> AnalysisResult:
    return _call_openai_compat(
        prompt,
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model="llama-3.1-8b-instant",
        system=system,
    )


def analyze_with_nvidia(prompt: str, system: str | None = None) -> AnalysisResult:
    return _call_openai_compat(
        prompt,
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.nvidia_api_key,
        model="meta/llama-3.1-70b-instruct",
        system=system,
    )


def analyze_with_claude(prompt: str, system: str | None = None) -> AnalysisResult:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        system=system or SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_llm_response(response.content[0].text)


def _call_llm_with_fallback(prompt: str, system_override: str | None = None) -> AnalysisResult:
    """Try primary provider, fall back to next available on failure."""
    providers_in_order = []

    primary = settings.llm_provider
    def _real_key(k: str) -> bool:
        return bool(k) and not k.startswith("nvapi-...") and not k.startswith("sk-ant-...")

    if primary == "groq":
        providers_in_order = [
            ("groq", analyze_with_groq),
            ("nvidia", analyze_with_nvidia) if _real_key(settings.nvidia_api_key) else None,
            ("anthropic", analyze_with_claude) if _real_key(settings.anthropic_api_key) else None,
        ]
    elif primary == "nvidia":
        providers_in_order = [
            ("nvidia", analyze_with_nvidia),
            ("groq", analyze_with_groq) if _real_key(settings.groq_api_key) else None,
        ]
    else:
        providers_in_order = [
            ("anthropic", analyze_with_claude),
            ("groq", analyze_with_groq) if _real_key(settings.groq_api_key) else None,
        ]

    providers_in_order = [p for p in providers_in_order if p is not None]
    last_err = None

    for name, fn in providers_in_order:
        try:
            return fn(prompt, system_override)
        except Exception as e:
            last_err = e
            continue

    # All providers failed — conservative fallback, do not silently allow
    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")


def analyze_message(
    message: str,
    game_id: str = "",
    session_id: str = "",
    player_id: str = "",
    target_id: str = "",
) -> AnalysisResult:
    """
    Full two-tier pipeline with conversation context.

    Tier 1 — regex pre-filter (0ms, no network)
    Tier 2 — LLM with conversation history from Redis
    """
    # Tier 1: instant rule check on raw message
    fast = prefilter(message)
    if fast is not None:
        return fast

    # Build context-aware prompt if session info provided
    if game_id and session_id and player_id and target_id:
        from context import format_context_for_llm, has_escalating_pattern

        prompt = format_context_for_llm(game_id, session_id, player_id, target_id, message)

        # Escalation floor: player already flagged 2+ times → force medium minimum
        if has_escalating_pattern(game_id, session_id, player_id, target_id):
            result = _call_llm_with_fallback(prompt)
            if not result.risk and result.level == RiskLevel.low:
                result = AnalysisResult(
                    risk=True,
                    level=RiskLevel.medium,
                    reason="Patrón escalante: jugador con historial de riesgo",
                    action=Action.warn,
                )
            return result
    else:
        prompt = message

    try:
        return _call_llm_with_fallback(prompt)
    except Exception as e:
        # FAIL-CLOSE: Si la IA falla, no dejamos pasar el mensaje en silencio.
        # Marcamos como riesgo medio para que un humano lo revise.
        return AnalysisResult(
            risk=True,
            level=RiskLevel.medium,
            reason=f"Fallo en motor IA (Fail-Close). Error: {str(e)[:50]}",
            action=Action.warn,
        )
