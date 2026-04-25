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
        r"\b(pasa(me|te)?|enví(a|ame)|envia(me)?|manda(me)?|ven|agrega(me)?|escri(be|beme)|contacta(me)?)\b.{0,40}"
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

# ── Sexual grooming — high-confidence block ───────────────────────────────────

_SEXUAL_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Nude / sexual photo requests
    (re.compile(
        r"\b(manda(me)?|enví(a|as?)(me)?|envia(me)?|sube|pásamela?|pasamela?|muéstrame|muestrame)\b"
        r".{0,35}"
        r"\b(nudes?|desnud[ao]s?|encuerad[ao]s?|en\s+ropa\s+interior|sin\s+ropa|calzon(cit[ao]s?)?)\b",
        re.IGNORECASE
    ), "Solicitud de fotos/desnudos sexuales"),

    # Explicit sexual solicitation
    (re.compile(
        r"\b(sexo\s+contig[ao]|hacer(lo|la)\s+contig[ao]|acostarte?\s+conmigo|"
        r"coger(te)?|cojer(te)?|follar(te)?|te\s+(cojo|follo|meto|penetro)|"
        r"quiero\s+(cogerte|follarte|meterte))\b",
        re.IGNORECASE
    ), "Solicitud sexual explícita"),

    # Sexual act on camera
    (re.compile(
        r"\b(mastúrbate|masturbate|tócate|tocate|muéstrate|muestrate)\b"
        r".{0,30}"
        r"\b(en\s+cámara|por\s+cámara|en\s+video|por\s+video|en\s+vivo|en\s+live|en\s+cam)\b",
        re.IGNORECASE
    ), "Solicitud de acto sexual en cámara"),

    # Sextortion / blackmail threat
    (re.compile(
        r"\b(publico|comparto|mando|difundo|subo)\b.{0,30}"
        r"\b(tus?\s+fotos|las\s+fotos|tus?\s+videos?|tus?\s+nudes?|tus?\s+imágenes?)\b",
        re.IGNORECASE
    ), "Amenaza de extorsión/chantaje sexual"),

    # Sexual video call request
    (re.compile(
        r"\b(videollamada|video\s*llamada|videochat|video\s*chat|por\s+cámara|en\s+cámara)\b"
        r".{0,30}"
        r"\b(desnud[ao]|sin\s+ropa|hot|sexy|sexual|erótic[ao]|erotico)\b",
        re.IGNORECASE
    ), "Solicitud de videollamada sexual"),

    # Grooming + meetup with sexual intent
    (re.compile(
        r"\b(te\s+quiero\s+(conocer|ver|tocar)|quiero\s+que\s+nos\s+veamos)\b"
        r".{0,40}"
        r"\b(solos?|sin\s+nadie|en\s+privado|en\s+mi\s+(cuarto|casa|carro|depa))\b",
        re.IGNORECASE
    ), "Invitación a encuentro privado con intención sexual"),
]

# ── Sexual grooming — medium-confidence warn ──────────────────────────────────

_SEXUAL_WARN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Virginity / sexual experience probe
    (re.compile(
        r"\b(eres\s+virgen|has\s+(tenido\s+)?(relaciones|sexo|novio|novia)|"
        r"te\s+has\s+(besado|acostado\s+con\s+alguien)|"
        r"tienes\s+(novio|novia|pareja)\b)",
        re.IGNORECASE
    ), "Sondeo de experiencia sexual del menor"),

    # Sexualized body compliments (grooming signal)
    (re.compile(
        r"\b(qué\s+(buen[ao]|ric[ao]|sexy|bonit[ao]|lind[ao])\s+(estás?|eres|te\s+ves)|"
        r"tienes\s+(buen|lindo|rico)\s+cuerpo|estás\s+(muy\s+)?(buenísim[ao]|riquísim[ao]))\b",
        re.IGNORECASE
    ), "Comentario sexualizado sobre apariencia del menor"),

    # "Are you alone" — classic grooming setup
    (re.compile(
        r"\b(estás\s+sol[ao]|estás\s+en\s+tu\s+(cuarto|recámara|habitación)|"
        r"hay\s+alguien\s+(contigo|en\s+tu\s+casa)|"
        r"tus?\s+(papás?|mamá|padres)\s+están?\s+en\s+casa)\b",
        re.IGNORECASE
    ), "Sondeo de si el menor está solo (patrón grooming)"),
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


# ── Cartel recruitment — social media specific ────────────────────────────────

_CARTEL_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Direct recruitment + cartel language
    (re.compile(
        r"\b(el\s+patrón|el\s+jefe|la\s+organización|la\s+empresa|la\s+compañía)\b.{0,40}"
        r"\b(te\s+(llama|busca|quiere|necesita)|quiere\s+hablar(te)?|hay\s+trabajo)\b",
        re.IGNORECASE
    ), "Reclutamiento directo por organización criminal"),

    (re.compile(
        r"\b(burrer[oa]|mula|halcón|halcon|sicario|plaza|jale\s+bueno|buen\s+jale)\b.{0,50}"
        r"\b(trabajo|chamba|ganar|lana|feria|billete)\b",
        re.IGNORECASE
    ), "Slang cartel asociado a oferta laboral"),

    (re.compile(
        r"\b(cruzar|brincar\s+el\s+charco|pasar\s+al\s+otro\s+lado)\b.{0,40}"
        r"\b(cositas|paquete|encomienda|algo\s+pequeño|mercancía|fardos?)\b",
        re.IGNORECASE
    ), "Oferta de tráfico/transporte ilícito"),

    (re.compile(
        r"\b(te\s+doy|te\s+pago|gana[rs]?)\s+\$?\d[\d,\.]*\s*(k|mil|pesos|dolares|usd)?\b.{0,60}"
        r"\b(al\s+día|por\s+viaje|por\s+cruce|semanal|diario)\b",
        re.IGNORECASE
    ), "Oferta de pago específico por actividad criminal"),
]

_CARTEL_WARN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Luxury bait
    (re.compile(
        r"\b(así\s+se\s+vive|quieres\s+vivir\s+así|mira\s+cómo\s+(se\s+)?viv[eo]|"
        r"tú\s+también\s+puedes\s+(tener|vivir)|carros?\s+y\s+(lana|dinero|feria))\b",
        re.IGNORECASE
    ), "Cebo de lujo — patrón de reclutamiento cartel"),

    (re.compile(
        r"\b(el\s+que\s+no\s+arriesga\s+no\s+gana|todos\s+lo\s+hacen|es\s+lo\s+normal\s+(aquí|en\s+el\s+rancho|en\s+la\s+colonia))\b",
        re.IGNORECASE
    ), "Normalización de actividad criminal"),

    (re.compile(
        r"\b(hay\s+(buen\s+)?trabajo|te\s+ofrezco\s+(chamba|jale)|tengo\s+(trabajo|chamba)\s+para\s+ti)\b",
        re.IGNORECASE
    ), "Oferta laboral sospechosa en redes"),
]


def prefilter_social(message: str) -> AnalysisResult | None:
    """Cartel/social-media specific patterns — runs after base prefilter."""
    for pattern, reason in _CARTEL_BLOCK_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.high,
                reason=reason,
                action=Action.block,
            )
    for pattern, reason in _CARTEL_WARN_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.medium,
                reason=reason,
                action=Action.warn,
            )
    return None


def prefilter(message: str) -> AnalysisResult | None:
    """
    Returns AnalysisResult if rule fires with high confidence.
    Returns None → message must go to LLM (Tier 2).

    Check order: criminal recruitment blocks → sexual blocks → warn patterns (both types).
    """
    for pattern, reason in _BLOCK_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.high,
                reason=reason,
                action=Action.block,
            )

    for pattern, reason in _SEXUAL_BLOCK_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.high,
                reason=reason,
                action=Action.block,
            )

    for pattern, reason in _WARN_PATTERNS:
        if pattern.search(message):
            return AnalysisResult(
                risk=True,
                level=RiskLevel.low,
                reason=reason,
                action=Action.warn,
            )

    for pattern, reason in _SEXUAL_WARN_PATTERNS:
        if pattern.search(message):
            return None  # LLM confirms sexual intent

    return None  # Ambiguous → LLM
