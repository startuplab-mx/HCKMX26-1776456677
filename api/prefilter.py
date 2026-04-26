"""
Tier 1 — rule-based pre-filter.
Runs in <1ms, zero network calls.
Returns AnalysisResult directly for obvious cases, None for ambiguous.
"""
import re
import unicodedata
from models import AnalysisResult, RiskLevel, Action


def _normalize(text: str) -> str:
    """Strip accents so 'pásate' matches 'pasate', 'dónde' matches 'donde', etc."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")

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
        r"\b(d[ií](gam[eo]s?|game?s?)|manda|pasa|deja)\b.{0,25}"
        r"\b(ubicaci[oó]n|direcci[oó]n|domicilio|colonia|direcci[oó]n\s+de\s+tu\s+casa)\b",
        re.IGNORECASE
    ), "Solicitud de ubicación física"),

    # Phone number / contact solicitation
    (re.compile(
        r"\b(pasa|dame|manda|comparte|tira|deja)\b.{0,20}"
        r"\b(tu\s+n[uú]mero|tu\s+cel|tu\s+cel[uu]lar|tu\s+whats|tu\s+tele[fé]ono|"
        r"n[uú]mero\s+de\s+(tu\s+)?cel|tu\s+contacto)\b",
        re.IGNORECASE
    ), "Solicitud de número de teléfono/contacto"),

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

    # Adult platform migration — clear predator signal
    (re.compile(
        r"\b(tu\s+(usuario|user|cuenta|perfil|nick)\s+(de|en)\s+)?"
        r"(pornhub|phub|p\.?hub|onlyfans|of\b|xvideos|xnxx|redtube|"
        r"chaturbate|fansly|privacy|adulto?s?)\b",
        re.IGNORECASE
    ), "Solicitud/referencia a plataforma adulta (grooming)"),

    # Explicit body part comments directed at minor
    (re.compile(
        r"\b(qu[eé]\s+(ric[ao]|buen[ao]|lind[ao]|bonit[ao]|hermoso|hermosa)\s+"
        r"(cul[oi]t?[ao]s?|nalgas?|culo|poto|pompas?|cuerp[ao]|pech[ao]|tetas?|"
        r"chichi[s]?|butt|ass))\b",
        re.IGNORECASE
    ), "Comentario sexual sobre cuerpo del menor"),

    (re.compile(
        r"\b(cul[oi]t?[ao]s?|nalgas?\s+(rica[s]?|buena[s]?|hermosa[s]?)|"
        r"tetas?\s+(rica[s]?|grande[s]?|bonita[s]?)|"
        r"pech[ao]\s+(bueno|lindo|rico))\b",
        re.IGNORECASE
    ), "Comentario sexual explícito sobre cuerpo"),

    # Mexican sexual slang — "chichis" (breasts), "concha" (vagina MX slang)
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
        r"tienes\s+(buen|lindo|rico)\s+cuerpo|estás\s+(muy\s+)?(buenísim[ao]|riquísim[ao])|"
        r"qu[eé]\s+(ric[ao]|buen[ao]).{0,20}(cuerp[ao]|piernas?|cara|ojos))\b",
        re.IGNORECASE
    ), "Comentario sexualizado sobre apariencia del menor"),

    # "Are you alone" — classic grooming setup
    (re.compile(
        r"\b(est[aá]s\s+solit?[ao]|est[aá]s\s+sol[ao]|"
        r"est[aá]s\s+en\s+tu\s+(cuarto|rec[aá]mara|habitaci[oó]n)|"
        r"hay\s+alguien\s+(contigo|en\s+tu\s+casa)|"
        r"tus?\s+(pap[aá]s?|mam[aá]|padres)\s+est[aá]n?\s+en\s+casa)\b",
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
        r"\b(cu[aá]ntos?\s+a[nñ]os?\s+tienes?|en\s+qu[eé]\s+grado\s+est[aá]s?|vas\s+a\s+la\s+escuela)\b",
        re.IGNORECASE
    ), "Sondeo de edad/perfil del menor"),
]


# ── Cartel recruitment — social media specific ────────────────────────────────
# Source: Constanza Nuche — "Reclutamiento Digital" (TikTok ethnography, Mexico)

_CARTEL_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Self-identification as cartel member + any recruitment signal
    (re.compile(
        r"\b(somos?\s+(del?|de\s+la)|soy\s+(del?|de\s+la)|andamos?\s+con|trabajamos?\s+(para|con))\b.{0,30}"
        r"\b(cjng|chapiza|chapizza|sinaloa|unión\s+tepito|nueva\s+generaci[oó]n|la\s+empresa|la\s+organizaci[oó]n|la\s+ma[nñ]a)\b",
        re.IGNORECASE
    ), "Identificación como miembro de cártel"),

    # Cartel name + active recruitment verb
    (re.compile(
        r"\b(cjng|chapiza|chapizza|nueva\s+generaci[oó]n|la\s+empresa|la\s+organizaci[oó]n)\b.{0,60}"
        r"\b(se\s+busca|buscamos|recluta(mos|ndo)?|únete|jálate|jalense|hay\s+(trabajo|chamba|jale)|"
        r"necesita(mos)?\s+gente|gente\s+de\s+confianza)\b",
        re.IGNORECASE
    ), "Reclutamiento explícito en nombre de cártel"),

    (re.compile(
        r"\b(se\s+busca|buscamos|recluta(mos|ndo)?|únete|jálate|gente\s+de\s+confianza|necesita(mos)?\s+gente)\b.{0,60}"
        r"\b(cjng|chapiza|chapizza|nueva\s+generaci[oó]n|la\s+empresa|la\s+organizaci[oó]n)\b",
        re.IGNORECASE
    ), "Reclutamiento explícito en nombre de cártel"),

    # Direct recruitment + cartel language
    (re.compile(
        r"\b(el\s+patr[oó]n|el\s+jefe|la\s+organizaci[oó]n|la\s+empresa|la\s+compa[nñ][ií]a)\b.{0,40}"
        r"\b(te\s+(llama|busca|quiere|necesita)|quiere\s+hablar(te)?|hay\s+trabajo)\b",
        re.IGNORECASE
    ), "Reclutamiento directo por organización criminal"),

    # Standalone cartel role identifiers — high-confidence even without context
    (re.compile(
        r"\b(halc[oó]n|halcanazo|halconazo|hal\s*c[oó]n|halconeo|burrer[oa]|"
        r"mula\s+de\s+(droga|carga)|sicari[oa]|"
        r"plaza\s+(controlada|del\s+\w+)|jefe\s+de\s+plaza)\b",
        re.IGNORECASE
    ), "Rol criminal cartel (halcón/burrero/sicario)"),

    # Drug offer — explicit
    (re.compile(
        r"\b(quieren?|vendo|consigo|hay|tengo)\s+(droga[s]?|mota|hierba|cristal|"
        r"polvo|coca|chiva|foco[s]?|pastillas?)\b",
        re.IGNORECASE
    ), "Oferta de drogas"),

    # Trafficking intent
    (re.compile(
        r"\b(necesito|quiero|voy\s+a|puedo)\s+(traficar|trafic\w+)\b",
        re.IGNORECASE
    ), "Intención de tráfico ilícito"),

    # "4L" / "4 letras" / "cuatro letras" = CJNG identifier (fuente: PDF)
    (re.compile(
        r"\b(únete\s+a\s+(las?\s+)?4\s*l|4\s*letras|cuatro\s+letras|"
        r"jalense\s+a\s+laborar.{0,20}4\s*l|"
        r"empleo\s+con\s+la\s+plebada|la\s+plebada\s+de\s+\w+)\b",
        re.IGNORECASE
    ), "Reclutamiento CJNG (4L/cuatro letras)"),

    # Exact cartel recruitment phrases from real evidence (PDF pág. 13-15)
    (re.compile(
        r"(únete\s+a\s+la\s+(empresa|organización)|"
        r"estamos\s+buscando\s+gente|"
        r"se\s+te\s+da\s+(ropa|comida|adiestramiento|hospedaje)|"
        r"más\s+info\s+al\s+priv|"
        r"si\s+te\s+agarran.{0,30}no\s+me\s+conoces|"
        r"jamás\s+nos\s+conocimos)",
        re.IGNORECASE
    ), "Frase real de reclutamiento criminal"),

    # Slang: halconeo, burrero, sicariato
    (re.compile(
        r"\b(burrer[oa]|mula|halcón|halcon|halconeo|sicario|sicariato|plaza|"
        r"jale\s+bueno|buen\s+jale|el\s+jale)\b.{0,50}"
        r"\b(trabajo|chamba|ganar|lana|feria|billete|paga|sueldo)\b",
        re.IGNORECASE
    ), "Slang cartel asociado a oferta laboral"),

    # Border/trafficking offers
    (re.compile(
        r"\b(cruzar|brincar\s+el\s+charco|pasar\s+al\s+otro\s+lado|"
        r"brincar\s+la\s+barda)\b.{0,40}"
        r"\b(cositas|paquete|encomienda|algo\s+pequeño|mercancía|fardos?|"
        r"mota|cristal|polvo)\b",
        re.IGNORECASE
    ), "Oferta de tráfico/transporte ilícito"),

    # Specific pay offer for criminal activity
    (re.compile(
        r"\b(te\s+doy|te\s+pago|gana[rs]?)\s+\$?\d[\d,\.]*\s*(k|mil|pesos|dolares|usd)?\b.{0,60}"
        r"\b(al\s+día|por\s+viaje|por\s+cruce|semanal|diario|por\s+semana)\b",
        re.IGNORECASE
    ), "Oferta de pago por actividad criminal"),

    # "alivianar" = pagar/ayudar criminalmente
    (re.compile(
        r"\b(te\s+alivian[ao]|yo\s+te\s+alivian[ao])\b.{0,40}"
        r"\b(semana|quincena|rápido|pronto|ahorita)\b",
        re.IGNORECASE
    ), "Oferta de pago con slang criminal (alivianar)"),

    # Halconeo / lookout instructions — "avisa si ves patrullas/policías/federales"
    (re.compile(
        r"\b(avisa|checa|fíjate|fijate|cuida|vigila|párate|parate|ponte)\b.{0,30}"
        r"\b(patrullas?|polic[ií]as?|federales?|militares?|soldados?|"
        r"la\s+ley|la\s+jura|la\s+tira|la\s+poli|judiciales?|marinos?|"
        r"retén|reten|bloqueo|operativo|movimiento\s+raro)\b",
        re.IGNORECASE
    ), "Instrucción de vigilancia (halconeo)"),

    # "si te agarran / si te cacha" = secretismo criminal
    (re.compile(
        r"\b(si\s+te\s+(agarran|cacha[n]?|pescan|detienen)|"
        r"si\s+(viene|llega)\s+la\s+(ley|poli|tira|jura))\b.{0,40}"
        r"\b(no\s+(me\s+)?(conoces|saben|digas)|yo\s+no\s+existo|nada\s+que\s+ver)\b",
        re.IGNORECASE
    ), "Instrucción de negación/secretismo criminal"),
]

_CARTEL_WARN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Luxury aspiration bait (PDF: "nacimos pobres tenemos que morirnos podridos en dinero")
    (re.compile(
        r"\b(así\s+se\s+vive|quieres\s+vivir\s+así|mira\s+cómo\s+(se\s+)?viv[eo]|"
        r"tú\s+también\s+puedes\s+(tener|vivir)|carros?\s+y\s+(lana|dinero|feria)|"
        r"salir\s+adelante\s+(rápido|pronto)|nacimos\s+pobres)\b",
        re.IGNORECASE
    ), "Cebo aspiracional — patrón de reclutamiento cartel"),

    # Normalization of crime
    (re.compile(
        r"\b(el\s+que\s+no\s+arriesga\s+no\s+gana|todos\s+lo\s+hacen|"
        r"es\s+lo\s+normal\s+(aquí|en\s+el\s+rancho|en\s+la\s+colonia)|"
        r"o\s+pierdes\s+el\s+miedo\s+o\s+pierdes\s+la\s+oportunidad|"
        r"demuestra\s+que\s+s[ií]\s+hay)\b",
        re.IGNORECASE
    ), "Normalización de actividad criminal"),

    # Generic suspicious job offer
    (re.compile(
        r"\b(hay\s+(buen\s+)?trabajo|te\s+ofrezco\s+(chamba|jale)|"
        r"tengo\s+(trabajo|chamba)\s+para\s+ti|"
        r"pidan\s+información.{0,30}empleo|"
        r"ánimo\s+plebada.{0,30}laborar)\b",
        re.IGNORECASE
    ), "Oferta laboral sospechosa con lenguaje cartel"),

    # Cartel hashtags (PDF pág. 7-8)
    (re.compile(
        r"#(nuevageneración|nuevageneracion|4letras|4l\b|ng\b|mencho|mecho|"
        r"señormencho|senormencho|ElSeñorDeLosGallos|"
        r"gentedelmz|mayozambada|operativamz|gentedelmayozambada|"
        r"maña|mana|trabajoparalamaña|belicones|fracesbelicas|"
        r"makabelico|ondeado|victormendivil)",
        re.IGNORECASE
    ), "Hashtag vinculado a cártel (CJNG/CDS/General)"),

    # Standalone cartel name mentions (without # — still suspicious in chat)
    (re.compile(
        r"\b(cjng|chapiza|chapizza|mayo\s+zambada|el\s+mencho|mencho|"
        r"beli[ck]ones?|la\s+ma[nñ]a|sinaloa\b|nueva\s+generaci[oó]n)\b",
        re.IGNORECASE
    ), "Referencia directa a cártel mexicano"),

    # "4l" / "4 l" standalone = CJNG "4 Letras" code
    (re.compile(r"\b4\s*l\b", re.IGNORECASE), "Código CJNG (4L = cuatro letras)"),
]

# ── Emoji cartel codes (fuente: Reclutamiento Digital — Constanza Nuche) ──────
# 🍕  = Chapizza / Cártel de Sinaloa (facción Chapiza, "CH🍕")
# 🐓  = CJNG / El Señor de los Gallos (Nemesio Oseguera "El Mencho")
# 🆖  = CJNG Nueva Generación ("4🆖", siglas NG)
# 🍇  = Unión Tepito (CDMX)
# 🥷  = ninja — operador encapuchado de cártel (uno de los más usados)
# 🪖⛑️ = casco — videos de personas fuertemente armadas, camionetas de lujo
# 😈  = diablo — representa el mal / identidad criminal
# 👹  = ogro (namahague) — variante del diablo, asociado a Makabélico/CJNG
# 🧿  = ojo turco — "la maña" (crimen organizado en general)

# Emoji combos that signal cartel affiliation + recruitment context
_EMOJI_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Cartel emoji + recruitment verb = BLOCK
    (re.compile(
        r"(únete|jálate|jalense|busca(mos|n)|empleo|trabajo|chamba|laborar|info\s+al\s+priv)"
        r".{0,60}"
        r"(🍕|🐓|🆖|🍇|🥷|🪖|⛑️|😈|👹)",
        re.IGNORECASE
    ), "Emoji cartel + llamado a reclutamiento"),

    (re.compile(
        r"(🍕|🐓|🆖|🍇|🥷|🪖|⛑️|😈|👹)"
        r".{0,60}"
        r"(únete|jálate|jalense|busca(mos|n)|empleo|trabajo|chamba|laborar|info\s+al\s+priv)",
        re.IGNORECASE
    ), "Emoji cartel + llamado a reclutamiento"),

    # "CH🍕" = Chapizza (Cártel de Sinaloa facción Chapo)
    (re.compile(r"ch\s*🍕", re.IGNORECASE), "Referencia directa Chapizza (CDS)"),

    # "4🆖" = CJNG Nueva Generación
    (re.compile(r"4\s*🆖"), "Referencia directa CJNG (4NG)"),
]

def _has_two_distinct_cartel_emojis(text: str) -> bool:
    """Require at least 2 DIFFERENT cartel emojis — avoids triple-same-emoji false positive."""
    cartel = [e for e in "🍕🐓🆖🍇🥷🪖⛑️😈👹🧿" if e in text]
    return len(set(cartel)) >= 2


_EMOJI_WARN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Sexual emoji combinations
    (re.compile(r"(🍑|🍆|💦|🫦).{0,20}(🍑|🍆|💦|🫦)"),
     "Emojis sexuales explícitos"),
]

# Cartel emoji check runs separately via function (not regex) to avoid false positives
_CARTEL_EMOJI_PRESENCE = re.compile(r"(🍕|🐓|🆖|🍇|🥷|🪖|⛑️|😈|👹|🧿)")


# Common safe tokens — clearly benign regardless of context
_SAFE_PASS = re.compile(
    r"^\s*(gg|gg\s*wp|nice|lol|xd|jaja+|jeje+|:v|oof|noob|ez|rip|wp|glhf|"
    r"good\s*game|well\s*played|nice\s*shot|wtf|omg|bruh|"
    r"hola|hi|hey|hello|buenas|saludos|"
    r"gracia[s]?|thx|ty|np|de\s*nada|"
    r"ok|okey|okay|sale|va|vale|"
    r"sí|si|no|nel|nop|"
    r"bien|todo\s+bien|bien\s+gracias|"
    r"que\s+(onda|tal|pasa|hay)|como\s+estas?|como\s+andas?|"
    r"bro|we|wey|güey|carnal|mano|cuate|"
    r"jeje+|jaja+|haha+|kk|xd|:(|:D|\^\^)"
    r")\s*[!?\.]*\s*$",
    re.IGNORECASE
)

# Short purely-alphabetic messages (≤12 chars only) — only catch trivial greetings like "si", "ok"
_SHORT_SAFE = re.compile(
    r"^[\w\s\?\!\.\,áéíóúüñÁÉÍÓÚÜÑ]{1,12}$"
)


# Keywords that disqualify a short message from being auto-allowed
_RISK_WORDS = re.compile(
    r"\b(paga|pago|dinero|lana|feria|trabajo|traficar|traficando|jale|chamba|patrulla|patrullas|policia|federal|"
    r"discord|whatsapp|telegram|pasate|nude|nudes|foto|fotos|camara|numero|cel|celular|"
    r"solo|sola|solito|solita|solos|edad|cuantos|anos|ubicacion|direccion|domicilio|"
    r"avisame|avisa|vigila|checa|halcon|halcanazo|sicario|burrero|cartel|plaza|4l|"
    r"droga|mota|cristal|coca|chiva|foco|"
    r"cjng|mencho|chapiza|chapizza|sinaloa|mana|belicones|belico|zambada|"
    r"sexo|sexual|pene|pito|verga|pilin|culo|culos|nalga|nalgas|culito|"
    r"tetas|butt|dick|cock|pussy|porn|phub|onlyfans|hub)\b",
    re.IGNORECASE
)


def prefilter(message: str) -> AnalysisResult | None:
    """
    Runs all patterns against both original and accent-normalized text.
    Returns AnalysisResult on match, None → pass to LLM.
    """
    # Fast-pass 1: known safe tokens (unambiguous, no pattern check needed)
    if _SAFE_PASS.match(message):
        return AnalysisResult(risk=False, level=RiskLevel.low, reason="Expresión de juego segura", action=Action.allow)

    msg_norm = _normalize(message)

    def _check(patterns: list, level: RiskLevel, action: Action) -> AnalysisResult | None:
        for pattern, reason in patterns:
            if pattern.search(message) or pattern.search(msg_norm):
                return AnalysisResult(risk=True, level=level, reason=reason, action=action)
        return None

    # Block patterns always run first — before any fast-pass
    block = (
        _check(_BLOCK_PATTERNS,        RiskLevel.high, Action.block) or
        _check(_SEXUAL_BLOCK_PATTERNS, RiskLevel.high, Action.block) or
        _check(_CARTEL_BLOCK_PATTERNS, RiskLevel.high, Action.block) or
        _check(_EMOJI_BLOCK_PATTERNS,  RiskLevel.high, Action.block)
    )
    if block:
        return block

    # Fast-pass 2: short messages with no risk keywords → skip warn + LLM
    # Safe ONLY after confirming no block patterns matched above
    if len(message) <= 30 and _SHORT_SAFE.match(message) and not _RISK_WORDS.search(message):
        return AnalysisResult(risk=False, level=RiskLevel.low, reason="Mensaje corto sin indicadores de riesgo", action=Action.allow)

    # Sexual warn patterns → always defer to LLM for context
    for pattern, _ in _SEXUAL_WARN_PATTERNS:
        if pattern.search(message) or pattern.search(msg_norm):
            return None

    # Cartel emoji: 2+ DISTINCT emojis = high confidence cartel affiliation → BLOCK
    cartel_emoji_result = None
    if _CARTEL_EMOJI_PRESENCE.search(message) and _has_two_distinct_cartel_emojis(message):
        cartel_emoji_result = AnalysisResult(
            risk=True, level=RiskLevel.high,
            reason="Combinación de emojis asociados a cárteles",
            action=Action.block,
        )

    return (
        _check(_WARN_PATTERNS,        RiskLevel.low,    Action.warn) or
        _check(_CARTEL_WARN_PATTERNS, RiskLevel.medium, Action.warn) or
        _check(_EMOJI_WARN_PATTERNS,  RiskLevel.medium, Action.warn) or
        cartel_emoji_result or
        None
    )


def prefilter_social(message: str) -> AnalysisResult | None:
    """Legacy alias — kept for backward compatibility."""
    return prefilter(message)
