"""Fixed, human-reviewed strings. Only English, Hindi and Punjabi are hand-written here.
Other languages get the English text plus an LLM-localised disclaimer that is also safety-checked."""

DISCLAIMER_EN = (
    "This tool is for general information only. It does not diagnose any disease, does not give treatment or "
    "medicine advice, and is not a substitute for a doctor. Always discuss your report with a qualified doctor."
)
DISCLAIMER = {
    "en": DISCLAIMER_EN,
    "hi": "यह टूल केवल सामान्य जानकारी के लिए है। यह किसी बीमारी की पहचान नहीं करता, इलाज या दवा की सलाह नहीं देता और डॉक्टर का विकल्प नहीं है। अपनी रिपोर्ट के बारे में हमेशा किसी योग्य डॉक्टर से बात करें।",
    "pa": "ਇਹ ਟੂਲ ਸਿਰਫ਼ ਆਮ ਜਾਣਕਾਰੀ ਲਈ ਹੈ। ਇਹ ਕਿਸੇ ਬਿਮਾਰੀ ਦੀ ਪਛਾਣ ਨਹੀਂ ਕਰਦਾ, ਇਲਾਜ ਜਾਂ ਦਵਾਈ ਦੀ ਸਲਾਹ ਨਹੀਂ ਦਿੰਦਾ ਅਤੇ ਡਾਕਟਰ ਦੀ ਥਾਂ ਨਹੀਂ ਲੈ ਸਕਦਾ। ਆਪਣੀ ਰਿਪੋਰਟ ਬਾਰੇ ਹਮੇਸ਼ਾ ਕਿਸੇ ਯੋਗ ਡਾਕਟਰ ਨਾਲ ਗੱਲ ਕਰੋ।",
}
STATUS_LABEL = {
    "en": {"low": "Low", "normal": "Normal", "high": "High", "unknown": "Unknown"},
    "hi": {"low": "कम", "normal": "सामान्य", "high": "अधिक", "unknown": "अज्ञात"},
    "pa": {"low": "ਘੱਟ", "normal": "ਆਮ", "high": "ਵੱਧ", "unknown": "ਅਣਜਾਣ"},
}
WARNING = {
    "en": {
        "low": "This value is below the range given in your report. Please show this report to your doctor.",
        "high": "This value is above the range given in your report. Please show this report to your doctor.",
        "unknown": "No clear range was found in the report for this value, so it cannot be called low or high. Please ask your doctor.",
    },
    "hi": {
        "low": "रिपोर्ट में दी गई सीमा से यह मान कम है। कृपया यह रिपोर्ट अपने डॉक्टर को दिखाएं।",
        "high": "रिपोर्ट में दी गई सीमा से यह मान अधिक है। कृपया यह रिपोर्ट अपने डॉक्टर को दिखाएं।",
        "unknown": "इस मान की तुलना के लिए रिपोर्ट में स्पष्ट सीमा नहीं मिली, इसलिए इसे कम या अधिक नहीं कहा जा सकता। कृपया अपने डॉक्टर से पूछें।",
    },
    "pa": {
        "low": "ਰਿਪੋਰਟ ਵਿੱਚ ਦਿੱਤੀ ਹੱਦ ਨਾਲੋਂ ਇਹ ਮੁੱਲ ਘੱਟ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਇਹ ਰਿਪੋਰਟ ਆਪਣੇ ਡਾਕਟਰ ਨੂੰ ਦਿਖਾਓ।",
        "high": "ਰਿਪੋਰਟ ਵਿੱਚ ਦਿੱਤੀ ਹੱਦ ਨਾਲੋਂ ਇਹ ਮੁੱਲ ਵੱਧ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਇਹ ਰਿਪੋਰਟ ਆਪਣੇ ਡਾਕਟਰ ਨੂੰ ਦਿਖਾਓ।",
        "unknown": "ਇਸ ਮੁੱਲ ਦੀ ਤੁਲਨਾ ਲਈ ਰਿਪੋਰਟ ਵਿੱਚ ਸਪੱਸ਼ਟ ਹੱਦ ਨਹੀਂ ਮਿਲੀ, ਇਸ ਲਈ ਇਸ ਨੂੰ ਘੱਟ ਜਾਂ ਵੱਧ ਨਹੀਂ ਕਿਹਾ ਜਾ ਸਕਦਾ। ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਡਾਕਟਰ ਨੂੰ ਪੁੱਛੋ।",
    },
}


def status_label(lang: str, status: str) -> str:
    return STATUS_LABEL.get(lang, STATUS_LABEL["en"])[status] if lang in STATUS_LABEL else STATUS_LABEL["en"][status]


def fixed_warning(lang: str, status: str) -> str:
    """Deterministic warning. Empty for normal values."""
    if status == "normal":
        return ""
    return WARNING.get(lang, WARNING["en"])[status]
