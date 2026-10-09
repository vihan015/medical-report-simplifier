"""Text normalisation that never alters numbers, decimal points or units."""
import re
import unicodedata

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")


def to_ascii_digits(text: str) -> str:
    """Convert decimal digits of any script (Devanagari, Gurmukhi, Arabic-Indic...) to 0-9.
    Superscripts such as the 3 in 10³ are not decimal digits and are left untouched."""
    out = []
    for ch in text:
        if not ch.isascii() and ch.isdecimal():
            out.append(str(unicodedata.decimal(ch)))
        else:
            out.append(ch)
    return "".join(out)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_DASHES).replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    text = to_ascii_digits(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_OCR_O = re.compile(r"(?<=\d)[Oo](?=[\d.])|(?<=[\d.])[Oo](?=\d)")


def fix_ocr_numbers(text: str) -> str:
    """Very conservative OCR repair: a letter O sandwiched inside a number becomes 0."""
    return _OCR_O.sub("0", text)


def normalize_unit(unit: str) -> str:
    return unit.lower().replace("µ", "u").replace("μ", "u").replace(" ", "")


def sanitize_label(text: str, max_len: int = 60) -> str:
    """Names come from untrusted documents. Keep only harmless characters (prompt-injection guard)."""
    text = re.sub(r"[^\w\s()%/.,+\-']", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()[:max_len]
