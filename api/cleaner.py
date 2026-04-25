import re
import unicodedata

# Leet speak → ASCII. Order matters: longer/specific first.
_LEET = str.maketrans({
    "@": "a", "4": "a",
    "3": "e",
    "1": "i", "!": "i",
    "0": "o",
    "$": "s", "5": "s",
    "7": "t",
    "+": "t",
    "9": "g",
    "8": "b",
    "6": "g",
})

# Collapse 3+ repeated chars → 2  (keeps "perro", "llamar" intact)
_REPEAT = re.compile(r"(.)\1{2,}")

# Detect single-letter tokens: "j a l e" → "jale"
# Matches 2+ single chars separated by single spaces
_SPACED = re.compile(r"(?<!\w)((\w) (?=\w( |$))){1,}\w")

_MULTI_SPACE = re.compile(r" {2,}")


def _collapse_spaced_letters(text: str) -> str:
    """Join words spelled out with spaces: 'j a l e' → 'jale'."""
    def _join(m: re.Match) -> str:
        return m.group(0).replace(" ", "")
    return _SPACED.sub(_join, text)


def normalizar_texto(texto: str) -> str:
    # 1. Lowercase
    t = texto.lower()
    # 2. Strip accents (handles é→e, á→a, etc. for regex matching)
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii")
    # 3. Leet speak
    t = t.translate(_LEET)
    # 4. Collapse repeated chars (3+ → 2)
    t = _REPEAT.sub(r"\1\1", t)
    # 5. Join spaced-out letters
    t = _collapse_spaced_letters(t)
    # 6. Normalize whitespace
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


if __name__ == "__main__":
    cases = [
        ("Qu1er3s un j4l3?",          "quieres un jale?"),
        ("m4nd4 m3ns4j3 4l w h a t s", "manda mensaje al whats"),
        ("teeee paaaago biieeen",       "tee paago biieen"),
        ("p4s4t3 al d1sc0rd",          "pasate al discord"),
        ("j a l e bueno",              "jale bueno"),
        ("h4lc0n en la pl4z4",         "halcon en la plaza"),
        ("HOLA BUEN0S DIAS",           "hola buenos dias"),
        ("perro llamar",               "perro llamar"),   # legit double-letter preserved
    ]
    for inp, expected in cases:
        result = normalizar_texto(inp)
        assert result == expected, f"FAIL: {inp!r} → {result!r} (expected {expected!r})"
        print(f"OK: {inp!r} → {result!r}")
    print("All tests passed.")
