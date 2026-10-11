"""Compare measured values with the reference range PRINTED IN THE REPORT.
Returns low / normal / high / unknown. It never invents a range."""
import re
from typing import Optional

from backend.app.schemas import Measurement, ReferenceRange
from backend.app.utils.text_normalizer import normalize_text

NUM = r"(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)"
_BETWEEN = rf"{NUM}\s*(?:-|\bto\b)\s*{NUM}"
_UPPER = rf"(?:<=?|≤|\b(?:up\s*to|upto|less\s+than|below|upper\s+limit)\b)\s*{NUM}"
_LOWER = rf"(?:>=?|≥|\b(?:more\s+than|greater\s+than|above|over)\b)\s*{NUM}"
# Order matters: "between" first so "13 - 17" is not split.
RANGE_PATTERN = re.compile(rf"(?:{_BETWEEN}|{_UPPER}|{_LOWER})", re.IGNORECASE)

_BETWEEN_RE = re.compile(rf"^(?P<lo>{NUM})\s*(?:-|\bto\b)\s*(?P<hi>{NUM})$", re.IGNORECASE)
_UPPER_RE = re.compile(rf"^(?P<op><=?|≤|up\s*to|upto|less\s+than|below|upper\s+limit)\s*(?P<n>{NUM})$", re.IGNORECASE)
_LOWER_RE = re.compile(rf"^(?P<op>>=?|≥|more\s+than|greater\s+than|above|over)\s*(?P<n>{NUM})$", re.IGNORECASE)


def to_float(s: str) -> float:
    return float(s.replace(",", ""))


def parse_reference_range(text: str) -> Optional[ReferenceRange]:
    text = normalize_text(text or "")
    if not text:
        return None
    matches = [m.group(0) for m in RANGE_PATTERN.finditer(text)]
    if not matches:
        return None
    if len(matches) > 1:
        return ReferenceRange(raw=text, ambiguous=True)
    raw = matches[0].strip()
    if m := _BETWEEN_RE.match(raw):
        lo, hi = to_float(m["lo"]), to_float(m["hi"])
        if lo >= hi:
            return ReferenceRange(raw=raw, ambiguous=True)
        return ReferenceRange(low=lo, high=hi, raw=raw)
    if m := _UPPER_RE.match(raw):
        op = m["op"].lower()
        inclusive = op in ("<=", "≤") or op.startswith("up") or op.startswith("upper")
        return ReferenceRange(high=to_float(m["n"]), high_inclusive=inclusive, raw=raw)
    if m := _LOWER_RE.match(raw):
        op = m["op"].lower()
        inclusive = op in (">=", "≥")
        return ReferenceRange(low=to_float(m["n"]), low_inclusive=inclusive, raw=raw)
    return ReferenceRange(raw=raw, ambiguous=True)


def classify(value: Optional[float], rng: Optional[ReferenceRange], qualifier: Optional[str] = None) -> str:
    if value is None or rng is None or rng.ambiguous:
        return "unknown"
    if qualifier:  # e.g. "<0.5": the exact value is not known, so do not judge
        return "unknown"
    if rng.low is None and rng.high is None:
        return "unknown"
    if rng.low is not None and (value < rng.low or (value == rng.low and not rng.low_inclusive)):
        return "low"
    if rng.high is not None and (value > rng.high or (value == rng.high and not rng.high_inclusive)):
        return "high"
    return "normal"


_FLAG_MAP = {"h": "high", "hh": "high", "high": "high", "l": "low", "ll": "low", "low": "low"}


def flag_to_status(flag: Optional[str]) -> Optional[str]:
    if not flag:
        return None
    return _FLAG_MAP.get(flag.strip("()* ").lower())


def apply(m: Measurement) -> Measurement:
    """Fill reference_range and status of a measurement (idempotent)."""
    if m.reference_range is None and m.reference_range_text:
        m.reference_range = parse_reference_range(m.reference_range_text)
    computed = classify(m.value, m.reference_range, m.qualifier)
    marker = flag_to_status(m.report_flag)
    m.notes = [n for n in m.notes if not n.startswith("status:")]
    if computed != "unknown":
        m.status, m.status_source = computed, "reference_range"
        if marker and marker != computed:
            m.status, m.status_source = "unknown", "conflict"
            m.notes.append("status: report flag disagrees with the range comparison; please verify the values")
    elif marker:
        m.status, m.status_source = marker, "report_marker"
    else:
        m.status, m.status_source = "unknown", "none"
    return m


# ---------------------------------------------------------------------------------------------
# Urgency (decided by code, never by the LLM). HEURISTIC: needs validation by a clinician.
#   routine : inside the range printed in the report
#   review  : no usable range (or low read-confidence): ask a doctor to review
#   soon    : outside the range: show the report to a doctor within a few days
#   prompt  : far outside the range: contact a doctor today / as soon as possible
# "far outside" = further than PROMPT_BOUND_FRACTION of the nearest bound, or further than
# PROMPT_WIDTH_FRACTION of the width of the range (so narrow ranges such as sodium or potassium are handled).
# A proper per-test critical-value table should replace this before real clinical use.
PROMPT_BOUND_FRACTION = 0.5
PROMPT_WIDTH_FRACTION = 0.75


def urgency(m: Measurement, min_conf: float = 0.5) -> str:
    if m.status == "unknown" or m.confidence < min_conf:
        return "review"
    if m.status == "normal":
        return "routine"
    rng, v = m.reference_range, m.value
    if rng is None or v is None:
        return "soon"
    bound = rng.low if m.status == "low" else rng.high
    if bound is None:
        return "soon"
    dev = (bound - v) if m.status == "low" else (v - bound)
    if dev <= 0:
        return "soon"
    width = (rng.high - rng.low) if (rng.low is not None and rng.high is not None) else None
    if (bound and dev / abs(bound) >= PROMPT_BOUND_FRACTION) or (width and dev / width >= PROMPT_WIDTH_FRACTION):
        return "prompt"
    return "soon"
