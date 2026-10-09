"""Convert report text into structured measurements and prescription items."""
import re
from typing import Optional

from backend.app.schemas import ExtractionResult, Measurement, PrescriptionItem
from backend.app.services import range_checker
from backend.app.services.range_checker import NUM, RANGE_PATTERN, to_float
from backend.app.utils.text_normalizer import fix_ocr_numbers, normalize_text, sanitize_label

KNOWN_UNIT_RE = re.compile(
    r"(g/dl|mg/dl|g/l|mg/l|ug/dl|µg/dl|mcg/dl|ng/ml|ng/dl|pg/ml|pg\b|fl\b|%|u/l|iu/l|iu/ml|miu/l|uiu/ml|µiu/ml|miu/ml"
    r"|mmol/l|meq/l|umol/l|µmol/l|/cumm|/ul|/µl|/mm3|cells|million|mill/|thou|lakh|10\^|x10|mm/hr|mm/1st|sec\b|"
    r"ratio|index|ml/min|kg/m2|mmhg|bpm)",
    re.IGNORECASE,
)
KNOWN_TESTS = (
    "hemoglobin haemoglobin hb rbc wbc platelet hematocrit pcv mcv mch mchc rdw esr neutrophil lymphocyte monocyte "
    "eosinophil basophil glucose sugar hba1c cholesterol ldl hdl vldl triglyceride creatinine urea bun uric alt sgpt "
    "ast sgot alp alkaline bilirubin albumin globulin protein tsh t3 t4 vitamin b12 ferritin iron sodium potassium "
    "calcium chloride crp egfr"
).split()
NAME_BLACKLIST = {"age", "date", "phone", "mobile", "page", "reg", "registration", "id", "sample", "bill", "pin",
                  "years", "year", "dob", "uhid", "lab", "no", "ref", "collected", "reported", "received", "sr", "barcode"}
FLAG_RE = re.compile(r"^\(?(?:H|L|HH|LL|HIGH|LOW)\)?\*?$", re.IGNORECASE)
_VAL_TOKEN = re.compile(rf"^(?P<q>[<>]=?|≤|≥)?(?P<n>{NUM})$")

RX_RE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?P<form>tab(?:let)?|cap(?:sule)?|syp|syrup|inj(?:ection)?|oint(?:ment)?|drops?|gel|cream|susp(?:ension)?)\b\.?\s*"
    r"(?P<name>[A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*)?)\s*(?P<strength>\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|g|ml|iu|%))?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
FREQ_RE = re.compile(r"\b\d\s*-\s*\d\s*-\s*\d(?:\s*-\s*\d)?\b|\b(?:OD|BD|BID|TDS|TID|QID|HS|SOS|QD|PRN)\b", re.IGNORECASE)
DUR_RE = re.compile(r"(?:x|for)?\s*\d+\s*(?:day|days|week|weeks|month|months|d)\b", re.IGNORECASE)
INSTR_RE = re.compile(r"\b(?:after food|before food|with food|empty stomach|at night|morning|bedtime|AF|BF)\b", re.IGNORECASE)

_NAME_ONLY = re.compile(r"^[A-Za-z][A-Za-z0-9 ()/%.,+\-']{1,60}$")
_VALUE_LINE = re.compile(rf"^(?:[<>]=?|≤|≥)?{NUM}$")
_UNIT_LINE = re.compile(r"^\S{1,20}$")


def _stitch_lines(lines: list[str]) -> list[str]:
    """Join 'name / value / unit / range' cells that were split over several lines (common in OCR)."""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if _NAME_ONLY.match(ln) and not re.search(rf"\s{NUM}(\s|$)", ln) and i + 1 < len(lines) and _VALUE_LINE.match(lines[i + 1]):
            parts, j = [ln, lines[i + 1]], i + 2
            while j < len(lines) and j < i + 5 and (
                RANGE_PATTERN.fullmatch(lines[j]) or FLAG_RE.match(lines[j])
                or (_UNIT_LINE.match(lines[j]) and KNOWN_UNIT_RE.search(lines[j]))
            ):
                parts.append(lines[j])
                j += 1
            out.append(" ".join(parts))
            i = j
        else:
            out.append(ln)
            i += 1
    return out


def _parse_rest(rest: str) -> Optional[dict]:
    rest = rest.strip()
    matches = list(RANGE_PATTERN.finditer(rest))
    head = rest[: matches[0].start()] if matches else rest
    tail = rest[matches[-1].end():] if matches else ""
    range_text = rest[matches[0].start():] if matches else ""
    ambiguous = len(matches) > 1
    if len(matches) == 1:
        range_text = matches[0].group(0)
    flag = None
    head_tokens = []
    for t in head.split():
        if FLAG_RE.match(t) and flag is None:
            flag = t
        elif t.lower().strip("():") not in ("ref", "range", "normal", "reference", "abnormal"):
            head_tokens.append(t)
    for t in tail.split():
        if FLAG_RE.match(t) and flag is None:
            flag = t
    if any(_VAL_TOKEN.match(t) for t in head_tokens):
        return None  # another number sits between this value and its unit/range: this was not the value
    unit = ""
    for t in head_tokens:
        if KNOWN_UNIT_RE.search(t):
            unit = t.strip("(),;:")
            break
    unit_known = bool(unit)
    if not unit and head_tokens:
        # An unrecognised "unit" is accepted only if it is short (e.g. "titre"); long words are part of the test name.
        if len(head_tokens) <= 2 and all(len(t) <= 6 for t in head_tokens):
            unit = " ".join(head_tokens).strip("(),;:")
        else:
            return None
    ok = unit_known or bool(matches) or bool(flag and unit)
    if not ok:
        return None
    return {"unit": unit, "unit_known": unit_known, "range_text": range_text, "ambiguous": ambiguous, "flag": flag}


def _try_measurement(line: str, idx: int, page: int, src_conf: float) -> Optional[Measurement]:
    line = re.sub(r"([<>]=?|≤|≥)\s+(?=\d)", r"\1", line)
    tokens = line.split()
    for pos in range(1, len(tokens)):
        mt = _VAL_TOKEN.match(tokens[pos])
        if not mt:
            continue
        name_tokens = tokens[:pos]
        name = sanitize_label(" ".join(name_tokens).strip(" :-.|"))
        letters = sum(c.isalpha() for c in name)
        if letters < 2 or {w.lower().strip(".:") for w in name.split()} & NAME_BLACKLIST:
            continue
        parsed = _parse_rest(" ".join(tokens[pos + 1:]))
        if not parsed:
            continue
        value_text = mt.group(0)
        try:
            value = to_float(mt["n"])
        except ValueError:
            continue
        conf = 0.45 + (0.2 if parsed["unit_known"] else 0.0) + (0.2 if parsed["range_text"] and not parsed["ambiguous"] else 0.0)
        if any(k in name.lower() for k in KNOWN_TESTS):
            conf += 0.1
        m = Measurement(
            id=f"m{idx}", test_name=name, value=value, value_text=value_text, qualifier=mt["q"],
            unit=parsed["unit"], reference_range_text=parsed["range_text"], report_flag=parsed["flag"],
            confidence=round(min(conf, 1.0) * (0.5 + 0.5 * src_conf), 2), source_line=line, page=page,
        )
        if parsed["ambiguous"]:
            m.notes.append("status: several reference ranges were printed for this test; not compared")
        return range_checker.apply(m)
    return None


def _try_prescription(line: str, idx: int) -> Optional[PrescriptionItem]:
    m = RX_RE.match(line)
    if not m:
        return None
    rest = m["rest"] or ""
    freq = FREQ_RE.search(rest)
    dur = DUR_RE.search(rest)
    instr = INSTR_RE.findall(rest)
    return PrescriptionItem(
        id=f"p{idx}", form=m["form"].title(), name=sanitize_label(m["name"]),
        strength=(m["strength"] or "").strip(), frequency=freq.group(0).strip() if freq else "",
        duration=dur.group(0).strip(" x") if dur else "", instructions=", ".join(dict.fromkeys(i.lower() for i in instr)),
        raw_line=line.strip(), confidence=0.6 + (0.2 if freq else 0) + (0.1 if m["strength"] else 0),
    )


def extract_structured(report_id: str, pages: list[tuple[int, str, str, Optional[float]]]) -> ExtractionResult:
    """pages: list of (page_number, text, method, ocr_confidence)."""
    measurements: list[Measurement] = []
    rx: list[PrescriptionItem] = []
    warnings: list[str] = []
    all_text = []
    for page_no, text, method, ocr_conf in pages:
        text = normalize_text(text)
        if method != "native":
            text = fix_ocr_numbers(text)
        all_text.append(text)
        src_conf = ocr_conf if (method != "native" and ocr_conf is not None) else 1.0
        lines = _stitch_lines([ln.strip() for ln in text.splitlines() if ln.strip()])
        for ln in lines:
            if p := _try_prescription(ln, len(rx) + 1):
                rx.append(p)
                continue
            if m := _try_measurement(ln, len(measurements) + 1, page_no, src_conf):
                measurements.append(m)
    if not measurements and not rx:
        warnings.append("No lab measurements or prescription lines could be recognised in this document.")
    low = [m.test_name for m in measurements if m.confidence < 0.5]
    if low:
        warnings.append("Low extraction confidence for: " + ", ".join(low) + ". Please verify these values.")
    doc_type = "mixed" if measurements and rx else "lab_report" if measurements else "prescription" if rx else "unknown"
    return ExtractionResult(report_id=report_id, document_type=doc_type, text="\n\n".join(all_text),
                            measurements=measurements, prescription_items=rx, warnings=warnings)


def rebuild_measurement(m: Measurement) -> Measurement:
    """Re-derive numeric fields and status from user-corrected text fields."""
    m.test_name = sanitize_label(m.test_name)
    m.value_text = normalize_text(m.value_text)
    mt = _VAL_TOKEN.match(m.value_text.replace(" ", ""))
    m.value = to_float(mt["n"]) if mt else None
    m.qualifier = mt["q"] if mt else None
    m.reference_range = None
    m.notes = []
    if m.value is None:
        m.notes.append("status: value could not be read as a number")
    m.confidence = 1.0  # confirmed by the user
    return range_checker.apply(m)
