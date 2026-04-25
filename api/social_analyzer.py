"""
Social media analysis — TikTok/Instagram comments.
Reuses the core two-tier pipeline with platform-aware context injection.
"""
from models import SocialMediaIn, AnalysisResult, RiskLevel, Action
from prefilter import prefilter, prefilter_social
from analyzer import _call_llm_with_fallback
from cleaner import normalizar_texto

SOCIAL_SYSTEM_PROMPT = """Eres AEGIS, sistema de protección de menores en redes sociales (TikTok/Instagram). Detectas reclutamiento criminal de cárteles mexicanos en comentarios.

SEÑALES DE RECLUTAMIENTO — detecta cualquiera de estas:

OFERTA ECONÓMICA:
- "buen jale", "hay trabajo", "te pago bien", "ganas bien", "fácil dinero"
- "solo llevas/cargas/cruzas algo", "trabajo de mensajero", "nada difícil"
- Cifras específicas: "te doy 5k", "ganas 500 al día", "lana segura"

CONTACTO DIRECTO:
- "el patrón/jefe quiere hablar contigo", "te estamos viendo"
- "la organización/empresa/compañía te necesita", "únete al equipo"
- "eres de los buenos", "gente como tú nos hace falta"

MIGRACIÓN A PRIVADO:
- "escríbeme al WhatsApp/wsp/Telegram/tg/privado/dm"
- "te mando mi número", número de teléfono en comentario público

SEÑUELO DE LUJO:
- "¿quieres vivir así?", "carros, lana, respeto — todo se puede"
- "así se vive bien", "mira cómo vivo yo, tú también puedes"
- Emojis de lujo con oferta implícita: 💰🚗👑💎

NORMALIZACIÓN CRIMINAL:
- "el que no arriesga no gana", "todos lo hacen aquí"
- Glorificación del narco/cartel como aspiracional

CÓDIGOS CARTEL (México):
- empresa/organización/compañía/negocio/plebada = cártel
- jale/chamba en contexto de dinero = trabajo criminal
- brincar el charco/cruzar = tráfico
- halcón/halconeo = vigilancia | burrero/mula = droga
- plaza = territorio | 🐓=CJNG | 🍕=Sinaloa | 🍇=Unión Tepito

CRITERIOS DE DECISIÓN:
- BLOCK (high): oferta criminal directa a menor, solicitud de contacto privado con oferta, teléfono público
- WARN (medium): oferta laboral ambigua, señuelo de lujo, glorificación criminal, cualquier duda
- ALLOW (low): comentario de admiración genuino, jerga juvenil sin contexto criminal, elogios normales

CONTEXTO AMPLIFICADOR (sube un nivel si aplica):
- creator_is_minor=true → sé más estricto
- cuenta nueva (<30 días) + oferta → sube nivel
- ratio seguidores/seguidos muy bajo (<0.1) + oferta → cuenta bot/falsa

REGLA CRÍTICA: Si hay duda → medium+warn. Es mejor alertar de más que dejar pasar reclutamiento.

Responde ÚNICAMENTE con JSON válido (sin texto extra):
{"risk":bool,"level":"low|medium|high","reason":"max 100 chars","action":"block|warn|allow"}"""


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
