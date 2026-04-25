"""
Tier 1 — rule-based pre-filter.
Runs in <1ms, zero network calls.
Returns AnalysisResult directly for obvious cases, None for ambiguous.
"""
import re
from models import AnalysisResult, RiskLevel, Action

# ── High-confidence block patterns ────────────────────────────────────────────
# Match = immediate block, no LLM needed

_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Platform migration
    (re.compile(
        r"\b(pasa(me|te)|ven|agrega(me)?|escri(be|beme)|contacta(me)?)\b.{0,40}"
        r"\b(whatsapp|whats|wsp|telegram|tele|discord|dm|privado|signal)\b",
        re.IGNORECASE
    ), "Migración a plataforma privada"),

    (re.compile(
        r"\b(wa|wsp|tg|telg)\s*[:=\-]?\s*\+?\d{7,15}\b",
        re.IGNORECASE
    ), "Número de contacto externo"),

    # Money / work offers
    (re.compile(
        r"\b(te\s+pago|te\s+doy|gana[rs]?|dinero\s+(fácil|facil|rápido|rapido)|"
        r"buen\s+sueldo|trabajo\s+(fácil|facil|bueno|rápido)|"
        r"(llevar|cargar|mover|transportar)\s+(paquete|cosas|mercancía|mercancia|encomienda))\b",
        re.IGNORECASE
    ), "Oferta laboral/dinero sospechosa"),

    # Secrecy
    (re.compile(
        r"\b(no\s+le\s+(digas|cuentes|avises|digas)\s+(a\s+)?(tus?\s+)?(papás|papas|mamá|mama|padres|apá|amá|familia)|"
        r"borra\s+(este?\s+)?(chat|mensaje|conversación|conv)|"
        r"esto\s+(es\s+)?entre\s+(nosotros|tu\s+y\s+yo)|"
        r"que\s+nadie\s+(se\s+)?entere)\b",
        re.IGNORECASE
    ), "Instrucción de secretismo"),

    # Physical meeting / location
    (re.compile(
        r"\b(dónde|donde)\s+(vives?|quedas?|estás?|estas?|queda\s+tu\s+casa)\b",
        re.IGNORECASE
    ), "Solicitud de ubicación"),

    (re.compile(
        r"\b(manda|envía|envia|sube|pásamela?|pasamela?)\s+(foto|fotos)\s+(de\s+)?(tu\s+)?"
        r"(casa|calle|colonia|barrio|escuela|colegio)\b",
        re.IGNORECASE
    ), "Solicitud de fotos físicas"),

    (re.compile(
        r"\b(nos\s+vemos|te\s+espero|pasa(te)?\s+por|recojo|te\s+llevo|te\s+traigo)\b.{0,30}"
        r"\b(hoy|mañana|ahorita|rato|saliendo)\b",
        re.IGNORECASE
    ), "Invitación a reunión física"),
]

# ── Medium-confidence warn patterns ───────────────────────────────────────────
# Match = warn, still send to LLM to confirm

_WARN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(
        r"\b(skins?\s+gratis|v-?bucks?\s+gratis|ítems?\s+gratis|items?\s+gratis|"
        r"te\s+regalo\s+(skins?|ítems?|items?|personajes?))\b",
        re.IGNORECASE
    ), "Oferta de ítems en juego (posible anzuelo)"),

    (re.compile(
        r"\b(confía(me)?|confía\s+en\s+mí|soy\s+tu\s+amigo|te\s+quiero\s+ayudar|"
        r"nadie\s+te\s+entiende\s+como\s+yo|tus\s+padres\s+no\s+(te\s+)?(entienden|escuchan))\b",
        re.IGNORECASE
    ), "Ingeniería social / manipulación emocional"),

    (re.compile(
        r"\b(cuántos?\s+años?\s+tienes?|en\s+qué\s+grado\s+estás?|vas\s+a\s+la\s+escuela)\b",
        re.IGNORECASE
    ), "Sondeo de edad/perfil del menor"),
]


def prefilter(message: str) -> AnalysisResult | None:
    """
    Returns AnalysisResult if rule fires with high confidence.
    Returns None → message must go to LLM (Tier 2).
    """
    for pattern, reason in _BLOCK_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.high,
                reason=reason,
                action=Action.block,
            )

    for pattern, reason in _WARN_PATTERNS:
        if pattern.search(message):
            # Warn but still escalate to LLM for confirmation
            return None  # Let LLM handle warn-level

    return None  # Ambiguous → LLM
