"""
Social media analysis — TikTok/Instagram comments.
Reuses the core two-tier pipeline with platform-aware context injection.
"""
from models import SocialMediaIn, AnalysisResult, RiskLevel, Action
from prefilter import prefilter, prefilter_social
from analyzer import _call_llm_with_fallback
from cleaner import normalizar_texto

SOCIAL_SYSTEM_PROMPT = """Eres el motor de análisis de AEGIS, sistema de protección de menores en redes sociales.

TU TAREA:
Analizar comentarios de TikTok/Instagram para detectar RECLUTAMIENTO CRIMINAL por parte de cárteles y crimen organizado.

CONTEXTO DE OPERACIÓN:
Los cárteles mexicanos reclutan activamente en redes sociales, especialmente en videos de jóvenes de zonas marginadas.
Buscan menores vulnerables (entre 12-17 años) con promesas de dinero, lujo y pertenencia.

INDICADORES — RECLUTAMIENTO CARTEL EN REDES SOCIALES:

1. OFERTA DE TRABAJO/DINERO FÁCIL:
   - "buen jale", "hay trabajo", "te pago bien", "ganarías bien"
   - "solo cargas/llevas/cruzas algo pequeño"
   - "no es nada difícil", "trabajo de mensajero"
   - Promesas de dinero específico: "te doy 5k", "ganas 10 al día"

2. RECLUTAMIENTO DIRECTO:
   - "el patrón te llama", "el jefe quiere hablar contigo"
   - "¿quieres trabajar con nosotros?", "te estamos viendo"
   - "la organización necesita gente como tú"
   - "eres de los buenos, te queremos en el equipo"

3. LUXURY BAIT (cebo de lujo):
   - "así se vive bien", "¿quieres vivir así?"
   - "carros, lana, respeto — todo se puede"
   - "mira cómo vivo yo, tú también puedes"
   - Emojis de lujo en contexto de oferta: 💰🚗👑💎

4. NORMALIZACIÓN DE LA VIDA CRIMINAL:
   - "el que no arriesga no gana"
   - "todos lo hacen aquí", "es lo normal en el rancho/colonia"
   - Glorificación del narco/cartel como aspiracional

5. MIGRACIÓN A PRIVADO:
   - "escríbeme al privado/wsp/tg"
   - "te mando el número por dm"
   - Número de teléfono en comentario público

6. SEÑALES DE CONTEXTO DE ALTO RIESGO:
   - Comentario en video de menor de zona fronteriza/rural con oferta laboral
   - Cuenta nueva (<30 días) con foto de lujo haciendo oferta
   - Cuenta sin seguidores reales (ratio bajo) haciendo contacto

7. CÓDIGOS Y SLANG CARTEL (México):
   - "el negocio", "la empresa", "la compañía" = organización criminal
   - "brincar el charco", "cruzar" = tráfico ilícito
   - "el verde", "la lana", "feria" = dinero
   - "jale", "chamba" = trabajo criminal
   - "plaza" = territorio controlado
   - "halconeo", "halcón" = vigilancia para cartel
   - "burrero", "mula" = transporte de drogas
   - "la línea" = comunicación cartel
   - Emojis código: 🐓(gallo/pleito), 🌿💊(drogas), 🔫(armas), 👁️(vigilancia)

REGLAS:
- Comentario genérico en video adulto = low/allow.
- Oferta laboral vaga a adulto sin señales de menor = medium/warn.
- Cualquier oferta laboral criminal dirigida a menor = high/block.
- Cuenta sospechosa (nueva, sin seguidores) + oferta = sube un nivel automáticamente.
- Si el video es de un menor (creator_is_minor=true), sé más conservador.
- Respuesta ÚNICAMENTE en JSON válido, sin texto extra.

ESTRUCTURA DEL JSON:
{
  "risk": boolean,
  "level": "low" | "medium" | "high",
  "reason": "String corto (max 100 caracteres)",
  "action": "block" | "warn" | "allow"
}"""


def _build_social_prompt(payload: SocialMediaIn) -> str:
    lines = []

    ctx = payload.context
    if ctx:
        lines.append(f"[PLATAFORMA: {ctx.platform.upper()}]")

        if ctx.creator_is_minor:
            lines.append("[⚠️ ALERTA: El creador del contenido es menor de edad]")

        if ctx.post_description:
            lines.append(f"[DESCRIPCIÓN DEL VIDEO/POST]: {ctx.post_description}")

        if ctx.post_hashtags:
            lines.append(f"[HASHTAGS]: {' '.join('#' + h for h in ctx.post_hashtags[:10])}")

        # Account risk signals
        account_flags = []
        if ctx.account_age_days is not None and ctx.account_age_days < 30:
            account_flags.append(f"cuenta nueva ({ctx.account_age_days} días)")
        if ctx.follower_count is not None and ctx.following_count:
            ratio = ctx.follower_count / max(ctx.following_count, 1)
            if ratio < 0.1 and ctx.follower_count < 100:
                account_flags.append(f"cuenta sospechosa (ratio seguidores/seguidos: {ratio:.2f})")
        if account_flags:
            lines.append(f"[⚠️ SEÑALES DE CUENTA]: {', '.join(account_flags)}")

    lines.append("")
    lines.append("[COMENTARIO A ANALIZAR]:")
    lines.append(payload.comment)
    lines.append("")
    lines.append("Determina si este comentario representa un intento de reclutamiento criminal.")

    return "\n".join(lines)


def _apply_account_risk_floor(
    result: AnalysisResult,
    payload: SocialMediaIn,
) -> AnalysisResult:
    """Escalate risk level if account signals are suspicious."""
    ctx = payload.context
    if not ctx or not result.risk:
        return result

    suspicious = False
    if ctx.account_age_days is not None and ctx.account_age_days < 7:
        suspicious = True
    if ctx.follower_count is not None and ctx.follower_count < 10:
        suspicious = True
    if ctx.creator_is_minor and result.level == RiskLevel.medium:
        suspicious = True

    if suspicious and result.level == RiskLevel.medium:
        return AnalysisResult(
            risk=True,
            level=RiskLevel.high,
            reason=f"{result.reason} + cuenta sospechosa",
            action=Action.block,
        )
    return result


def analyze_social(payload: SocialMediaIn) -> AnalysisResult:
    """
    Two-tier pipeline for social media comments.
    Tier 0 — normalize (leet, dots, spaces)
    Tier 1 — prefilter (regex, 0ms) on raw + cleaned
    Tier 2 — LLM with full platform context
    """
    clean = normalizar_texto(payload.comment)

    fast_raw = prefilter(payload.comment)
    fast_clean = prefilter(clean)
    fast = None
    if fast_raw is not None and fast_raw.risk:
        fast = fast_raw
    elif fast_clean is not None and fast_clean.risk:
        fast = fast_clean
    elif fast_raw is not None:
        fast = fast_raw
    elif fast_clean is not None:
        fast = fast_clean

    if fast is not None:
        return _apply_account_risk_floor(fast, payload)

    # prefilter_social is an alias — skip duplicate call, use clean version only
    prompt = _build_social_prompt(payload)
    result = _call_llm_with_fallback(prompt, system_override=SOCIAL_SYSTEM_PROMPT)
    return _apply_account_risk_floor(result, payload)
