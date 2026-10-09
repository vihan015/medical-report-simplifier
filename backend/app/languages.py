"""Language registry.

tier 1: languages where large LLMs are generally strong. Still validate with native speakers.
tier 2: lower-resource or less validated; the UI shows an extra caution.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native: str
    tier: int
    script: str | None  # Unicode name prefix used for the output-script check (None = Latin)
    rtl: bool = False


_L = Language
LANGUAGES: dict[str, Language] = {l.code: l for l in [
    _L("en", "English", "English", 1, None),
    _L("hi", "Hindi", "हिन्दी", 1, "DEVANAGARI"),
    _L("pa", "Punjabi", "ਪੰਜਾਬੀ", 1, "GURMUKHI"),
    _L("bn", "Bengali", "বাংলা", 1, "BENGALI"),
    _L("ta", "Tamil", "தமிழ்", 1, "TAMIL"),
    _L("te", "Telugu", "తెలుగు", 1, "TELUGU"),
    _L("mr", "Marathi", "मराठी", 1, "DEVANAGARI"),
    _L("gu", "Gujarati", "ગુજરાતી", 1, "GUJARATI"),
    _L("kn", "Kannada", "ಕನ್ನಡ", 1, "KANNADA"),
    _L("ml", "Malayalam", "മലയാളം", 1, "MALAYALAM"),
    _L("or", "Odia", "ଓଡ଼ିଆ", 1, "ORIYA"),
    _L("ur", "Urdu", "اردو", 1, "ARABIC", rtl=True),
    _L("ne", "Nepali", "नेपाली", 1, "DEVANAGARI"),
    _L("as", "Assamese", "অসমীয়া", 2, "BENGALI"),
    _L("sa", "Sanskrit", "संस्कृतम्", 2, "DEVANAGARI"),
    _L("mai", "Maithili", "मैथिली", 2, "DEVANAGARI"),
    _L("kok", "Konkani", "कोंकणी", 2, "DEVANAGARI"),
    _L("sd", "Sindhi", "سنڌي", 2, "ARABIC", rtl=True),
    _L("ks", "Kashmiri", "کٲشُر", 2, "ARABIC", rtl=True),
    _L("es", "Spanish", "Español", 1, None),
    _L("fr", "French", "Français", 1, None),
    _L("de", "German", "Deutsch", 1, None),
    _L("pt", "Portuguese", "Português", 1, None),
    _L("it", "Italian", "Italiano", 1, None),
    _L("id", "Indonesian", "Bahasa Indonesia", 1, None),
    _L("sw", "Swahili", "Kiswahili", 2, None),
    _L("tr", "Turkish", "Türkçe", 1, None),
    _L("vi", "Vietnamese", "Tiếng Việt", 1, None),
    _L("ar", "Arabic", "العربية", 1, "ARABIC", rtl=True),
    _L("fa", "Persian", "فارسی", 2, "ARABIC", rtl=True),
    _L("ru", "Russian", "Русский", 1, "CYRILLIC"),
    _L("zh", "Chinese", "中文", 1, "CJK"),
    _L("ja", "Japanese", "日本語", 1, "CJK|HIRAGANA|KATAKANA"),
    _L("ko", "Korean", "한국어", 1, "HANGUL"),
    _L("th", "Thai", "ไทย", 2, "THAI"),
]}


def get_language(code: str) -> Language:
    if code not in LANGUAGES:
        raise ValueError(f"Unsupported language: {code}")
    return LANGUAGES[code]
