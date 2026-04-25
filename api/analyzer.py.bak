import json
import httpx
import anthropic as _anthropic
from models import AnalysisResult, RiskLevel, Action
from config import get_settings
from prefilter import prefilter
from cleaner import normalizar_texto

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


def analyze_message(
    message: str,
    game_id: str = "",
    session_id: str = "",
    player_id: str = "",
    target_id: str = "",
) -> AnalysisResult:
    # Tier 0: normalize obfuscated text before any analysis
    clean = normalizar_texto(message)

    # Tier 1: regex prefilter — 0ms, no network (run on both raw + cleaned)
    fast = prefilter(message) or prefilter(clean)
    if fast is not None:
        return fast

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
            return result
    else:
        prompt = message

    try:
        return _call_llm_with_fallback(prompt)
    except Exception as e:
        return AnalysisResult(
            risk=True,
            level=RiskLevel.medium,
            reason=f"Fallo en motor IA (Fail-Close). Error: {str(e)[:50]}",
            action=Action.warn,
        )
