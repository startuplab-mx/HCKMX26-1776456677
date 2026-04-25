import re
import unicodedata

# Leet speak → ASCII
_LEET = str.maketrans({
    "@": "a", "4": "a",
    "3": "e",
    "1": "i", "!": "i",
    "0": "o",
    "$": "s", "5": "s",
    "7": "t", "+": "t",
    "9": "g", "6": "g",
    "8": "b",
})

# Collapse 3+ repeated chars → 2  (keeps "perro", "llamar" intact)
_REPEAT = re.compile(r"(.)\1{2,}")

# Single letters separated by spaces: "j a l e" → "jale"
_SPACED = re.compile(r"(?<!\w)((\w) (?=\w( |$))){1,}\w")

# Single letters separated by dots or dashes: "j.a.l.e" / "j-a-l-e" / "j_a_l_e"
# Matches: single-char + separator repeated, ending in single-char
_DOTTED = re.compile(r"\b(\w)[.\-_](?=(\w[.\-_])*\w\b)")

_MULTI_SPACE = re.compile(r" {2,}")


def _collapse_spaced_letters(text: str) -> str:
    def _join(m: re.Match) -> str:
        return m.group(0).replace(" ", "")
    return _SPACED.sub(_join, text)


def _collapse_dotted_letters(text: str) -> str:
    """'j.a.l.e' → 'jale', 'd-i-s-c-o-r-d' → 'discord'"""
    # Remove separators between single chars: \b X . X . X \b
    return re.sub(r"\b(\w)([.\-_]\w)+\b", lambda m: m.group(0).replace(".", "").replace("-", "").replace("_", ""), text)


# ── N-gram keyword detector ────────────────────────────────────────────────────
# Fast Tier-1.5: check if a message contains enough character bigrams of a
# known dangerous keyword — catches heavy obfuscation that leet+space fixes miss.

def _bigrams(word: str) -> set[str]:
    return {word[i:i+2] for i in range(len(word) - 1)}

_NGRAM_KEYWORDS: list[tuple[set[str], str, float]] = [
    # (bigrams, keyword, min_match_ratio)
    (_bigrams("discord"),   "discord",   0.75),
    (_bigrams("telegram"),  "telegram",  0.75),
    (_bigrams("whatsapp"),  "whatsapp",  0.75),
    (_bigrams("sicario"),   "sicario",   0.80),
    (_bigrams("halcon"),    "halcon",    0.80),
    (_bigrams("burrero"),   "burrero",   0.80),
    (_bigrams("jale"),      "jale",      0.85),
    (_bigrams("pasate"),    "pasate",    0.80),
    (_bigrams("discord"),   "discord",   0.75),
]


_PUNCT = re.compile(r"[^\w]")


def ngram_reconstruct(text: str) -> str:
    """
    For each known keyword, if the message's bigrams overlap enough,
    inject the clean keyword so the prefilter/LLM can match it.
    Runs on already-normalized text. O(K * N) where K=keywords, N=text length.
    """
    words = text.split()
    result = list(words)
    for i, word in enumerate(words):
        core = _PUNCT.sub("", word)  # strip punctuation before bigram check
        if len(core) < 3:
            continue
        wbg = _bigrams(core)
        for kw_bgs, kw, threshold in _NGRAM_KEYWORDS:
            if not kw_bgs:
                continue
            overlap = len(wbg & kw_bgs) / len(kw_bgs)
            if overlap >= threshold and core != kw:
                # preserve trailing punctuation (e.g. "jale?" → "jale?")
                suffix = word[len(core):]
                result[i] = kw + suffix
                break
    return " ".join(result)


def normalizar_texto(texto: str) -> str:
    # 1. Lowercase
    t = texto.lower()
    # 2. Strip accents
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii")
    # 3. Leet speak
    t = t.translate(_LEET)
    # 4. Collapse repeated chars (3+ → 2)
    t = _REPEAT.sub(r"\1\1", t)
    # 5. Join letters split by dots/dashes/underscores: "d.i.s.c.o.r.d" → "discord"
    t = _collapse_dotted_letters(t)
    # 6. Join letters split by spaces: "d i s c o r d" → "discord"
    t = _collapse_spaced_letters(t)
    # 7. N-gram reconstruction for heavy obfuscation
    t = ngram_reconstruct(t)
    # 8. Normalize whitespace
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


if __name__ == "__main__":
    cases = [
        ("Qu1er3s un j4l3?",           "quieres un jale?"),
        ("m4nd4 m3ns4j3 4l w h a t s", "manda mensaje al whats"),
        ("teeee paaaago biieeen",       "tee paago biieen"),
        ("p4s4t3 al d1sc0rd",          "pasate al discord"),
        ("j a l e bueno",              "jale bueno"),
        ("h4lc0n en la pl4z4",         "halcon en la plaza"),
        ("HOLA BUEN0S DIAS",           "hola buenos dias"),
        ("perro llamar",               "perro llamar"),
        # dot/dash separation
        ("j.a.l.e bueno",             "jale bueno"),
        ("d.i.s.c.o.r.d privado",     "discord privado"),
        ("h-a-l-c-o-n de la zona",    "halcon de la zona"),
        ("s_i_c_a_r_i_o",             "sicario"),
        # mixed
        ("p4s4t3 al d.i.s.c.o.r.d",  "pasate al discord"),
    ]
    for inp, expected in cases:
        result = normalizar_texto(inp)
        assert result == expected, f"FAIL:\n  in:  {inp!r}\n  got: {result!r}\n  exp: {expected!r}"
        print(f"OK: {inp!r} → {result!r}")
    print("All tests passed.")
