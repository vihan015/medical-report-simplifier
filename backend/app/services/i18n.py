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


FIXED_LANGS = ("en", "hi", "pa")

LABELS = {
    "en": {"what_it_is": "What this test is", "what_it_means": "What your result means",
           "should_i_worry": "Should I be worried?", "when_to_see_doctor": "When to see a doctor"},
    "hi": {"what_it_is": "यह जाँच क्या है", "what_it_means": "आपके नतीजे का मतलब",
           "should_i_worry": "क्या चिंता करनी चाहिए?", "when_to_see_doctor": "डॉक्टर को कब दिखाएं"},
    "pa": {"what_it_is": "ਇਹ ਜਾਂਚ ਕੀ ਹੈ", "what_it_means": "ਤੁਹਾਡੇ ਨਤੀਜੇ ਦਾ ਮਤਲਬ",
           "should_i_worry": "ਕੀ ਚਿੰਤਾ ਕਰਨੀ ਚਾਹੀਦੀ ਹੈ?", "when_to_see_doctor": "ਡਾਕਟਰ ਨੂੰ ਕਦੋਂ ਦਿਖਾਓ"},
}
URGENCY_LABEL = {
    "en": {"routine": "Routine", "review": "Needs review", "soon": "See a doctor soon", "prompt": "Contact a doctor today"},
    "hi": {"routine": "सामान्य", "review": "जाँच करवाएं", "soon": "जल्द डॉक्टर को दिखाएं", "prompt": "आज ही डॉक्टर से संपर्क करें"},
    "pa": {"routine": "ਆਮ", "review": "ਜਾਂਚ ਕਰਵਾਓ", "soon": "ਜਲਦੀ ਡਾਕਟਰ ਨੂੰ ਦਿਖਾਓ", "prompt": "ਅੱਜ ਹੀ ਡਾਕਟਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ"},
}
URGENCY_TEXT = {
    "en": {
        "routine": "This value is inside the range printed in your report. You can discuss it with your doctor at your next routine visit.",
        "review": "A clear range was not available (or the value could not be read with confidence), so this value cannot be judged here. Please ask your doctor to review it.",
        "soon": "This value is outside the range in your report. Please show this report to your doctor within the next few days.",
        "prompt": "This value is far outside the range in your report. Please contact your doctor today or as soon as you can.",
    },
    "hi": {
        "routine": "यह मान आपकी रिपोर्ट में दी गई सीमा के अंदर है। आप अगली नियमित मुलाकात में डॉक्टर से इस पर बात कर सकते हैं।",
        "review": "रिपोर्ट में स्पष्ट सीमा उपलब्ध नहीं थी (या मान भरोसे से पढ़ा नहीं जा सका), इसलिए इस मान को यहाँ परखा नहीं जा सकता। कृपया डॉक्टर से इसे दिखवाएं।",
        "soon": "यह मान रिपोर्ट की सीमा से बाहर है। कृपया अगले कुछ दिनों में यह रिपोर्ट अपने डॉक्टर को दिखाएं।",
        "prompt": "यह मान रिपोर्ट की सीमा से काफ़ी बाहर है। कृपया आज ही या जल्द से जल्द अपने डॉक्टर से संपर्क करें।",
    },
    "pa": {
        "routine": "ਇਹ ਮੁੱਲ ਤੁਹਾਡੀ ਰਿਪੋਰਟ ਵਿੱਚ ਦਿੱਤੀ ਹੱਦ ਦੇ ਅੰਦਰ ਹੈ। ਤੁਸੀਂ ਅਗਲੀ ਨਿਯਮਤ ਮੁਲਾਕਾਤ ਵਿੱਚ ਡਾਕਟਰ ਨਾਲ ਇਸ ਬਾਰੇ ਗੱਲ ਕਰ ਸਕਦੇ ਹੋ।",
        "review": "ਰਿਪੋਰਟ ਵਿੱਚ ਸਪੱਸ਼ਟ ਹੱਦ ਉਪਲਬਧ ਨਹੀਂ ਸੀ (ਜਾਂ ਮੁੱਲ ਭਰੋਸੇ ਨਾਲ ਪੜ੍ਹਿਆ ਨਹੀਂ ਜਾ ਸਕਿਆ), ਇਸ ਲਈ ਇਸ ਮੁੱਲ ਨੂੰ ਇੱਥੇ ਪਰਖਿਆ ਨਹੀਂ ਜਾ ਸਕਦਾ। ਕਿਰਪਾ ਕਰਕੇ ਡਾਕਟਰ ਤੋਂ ਇਸ ਦੀ ਜਾਂਚ ਕਰਵਾਓ।",
        "soon": "ਇਹ ਮੁੱਲ ਰਿਪੋਰਟ ਦੀ ਹੱਦ ਤੋਂ ਬਾਹਰ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਅਗਲੇ ਕੁਝ ਦਿਨਾਂ ਵਿੱਚ ਇਹ ਰਿਪੋਰਟ ਆਪਣੇ ਡਾਕਟਰ ਨੂੰ ਦਿਖਾਓ।",
        "prompt": "ਇਹ ਮੁੱਲ ਰਿਪੋਰਟ ਦੀ ਹੱਦ ਤੋਂ ਕਾਫ਼ੀ ਬਾਹਰ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਅੱਜ ਹੀ ਜਾਂ ਜਲਦੀ ਤੋਂ ਜਲਦੀ ਆਪਣੇ ਡਾਕਟਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
    },
}
EMERGENCY_EN = ("Get emergency medical help straight away if you have chest pain, trouble breathing, fainting, confusion, "
                "severe bleeding or sudden severe weakness, whatever your report says.")
EMERGENCY = {
    "en": EMERGENCY_EN,
    "hi": "यदि आपको सीने में दर्द, साँस लेने में तकलीफ़, बेहोशी, भ्रम, तेज़ रक्तस्राव या अचानक तेज़ कमज़ोरी हो, तो रिपोर्ट जो भी कहे, तुरंत आपातकालीन चिकित्सा सहायता लें।",
    "pa": "ਜੇ ਤੁਹਾਨੂੰ ਛਾਤੀ ਵਿੱਚ ਦਰਦ, ਸਾਹ ਲੈਣ ਵਿੱਚ ਤਕਲੀਫ਼, ਬੇਹੋਸ਼ੀ, ਉਲਝਣ, ਤੇਜ਼ ਖੂਨ ਵਗਣਾ ਜਾਂ ਅਚਾਨਕ ਤੇਜ਼ ਕਮਜ਼ੋਰੀ ਹੋਵੇ, ਤਾਂ ਰਿਪੋਰਟ ਜੋ ਵੀ ਕਹੇ, ਤੁਰੰਤ ਐਮਰਜੈਂਸੀ ਡਾਕਟਰੀ ਮਦਦ ਲਓ।",
}
STATUS_MEANING = {
    "en": {"low": "Your value is below the range printed in the report.", "high": "Your value is above the range printed in the report.",
           "normal": "Your value is inside the range printed in the report.", "unknown": "No clear range for this value was found in the report."},
    "hi": {"low": "आपका मान रिपोर्ट में छपी सीमा से कम है।", "high": "आपका मान रिपोर्ट में छपी सीमा से अधिक है।",
           "normal": "आपका मान रिपोर्ट में छपी सीमा के अंदर है।", "unknown": "रिपोर्ट में इस मान के लिए स्पष्ट सीमा नहीं मिली।"},
    "pa": {"low": "ਤੁਹਾਡਾ ਮੁੱਲ ਰਿਪੋਰਟ ਵਿੱਚ ਛਪੀ ਹੱਦ ਤੋਂ ਘੱਟ ਹੈ।", "high": "ਤੁਹਾਡਾ ਮੁੱਲ ਰਿਪੋਰਟ ਵਿੱਚ ਛਪੀ ਹੱਦ ਤੋਂ ਵੱਧ ਹੈ।",
           "normal": "ਤੁਹਾਡਾ ਮੁੱਲ ਰਿਪੋਰਟ ਵਿੱਚ ਛਪੀ ਹੱਦ ਦੇ ਅੰਦਰ ਹੈ।", "unknown": "ਰਿਪੋਰਟ ਵਿੱਚ ਇਸ ਮੁੱਲ ਲਈ ਸਪੱਸ਼ਟ ਹੱਦ ਨਹੀਂ ਮਿਲੀ।"},
}
SUMMARY = {
    "en": "{n} test value(s) were read from this report. {k} of them are outside the range printed in the report.",
    "hi": "इस रिपोर्ट में {n} जाँच के मान पढ़े गए। इनमें से {k} रिपोर्ट में छपी सीमा से बाहर हैं।",
    "pa": "ਇਸ ਰਿਪੋਰਟ ਵਿੱਚ {n} ਜਾਂਚਾਂ ਦੇ ਮੁੱਲ ਪੜ੍ਹੇ ਗਏ। ਇਨ੍ਹਾਂ ਵਿੱਚੋਂ {k} ਰਿਪੋਰਟ ਵਿੱਚ ਛਪੀ ਹੱਦ ਤੋਂ ਬਾਹਰ ਹਨ।",
}


def _pick(table: dict, lang: str):
    return table.get(lang) or table["en"]


def labels(lang: str) -> dict:
    return _pick(LABELS, lang)


def urgency_label(lang: str, u: str) -> str:
    return _pick(URGENCY_LABEL, lang)[u]


def urgency_text(lang: str, u: str) -> str:
    return _pick(URGENCY_TEXT, lang)[u]


def emergency(lang: str) -> str:
    return _pick(EMERGENCY, lang)


def status_meaning(lang: str, status: str) -> str:
    return _pick(STATUS_MEANING, lang)[status]


def summary(lang: str, n: int, k: int) -> str:
    return _pick(SUMMARY, lang).format(n=n, k=k)
