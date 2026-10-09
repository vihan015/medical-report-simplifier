"""Safety and hallucination validation of generated explanations.

Deterministic checks (always run):
  numerical_fidelity, unit_preservation, range_accuracy, entity_preservation,
  unsafe_recommendation, unsupported_claim (diagnosis terms), abstention, language_script
LLM-judge checks (optional, independent second call):
  unsupported claims, unsafe claims, contradictions, translation meaning
Language-agnostic by design: numbers are compared after converting any script's digits to ASCII, and English
rule checks run on BOTH the model's own back-translation and the judge's independent back-translation.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional

from backend.app.config import Settings
from backend.app.languages import get_language
from backend.app.schemas import (Draft, JudgeResult, Measurement, PrescriptionItem, SafetyReport, Violation)
from backend.app.utils.text_normalizer import normalize_unit, to_ascii_digits

EVALUATOR_VERSION = "1.0"
_NUM_RE = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)")


@dataclass
class Facts:
    measurements: list[Measurement] = field(default_factory=list)
    prescriptions: list[PrescriptionItem] = field(default_factory=list)
    report_text: str = ""


def extract_numbers(text: str) -> list[float]:
    text = to_ascii_digits(text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)  # list markers
    out = []
    for m in _NUM_RE.finditer(text):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def _nums_of(*strings: str) -> set[float]:
    s: set[float] = set()
    for x in strings:
        s.update(extract_numbers(x or ""))
    return s


def measurement_numbers(m: Measurement) -> set[float]:
    nums = _nums_of(m.test_name, m.value_text, m.unit, m.reference_range_text)
    if m.value is not None:
        nums.add(m.value)
    if m.reference_range:
        nums.update(x for x in (m.reference_range.low, m.reference_range.high) if x is not None)
    return nums


def prescription_numbers(p: PrescriptionItem) -> set[float]:
    return _nums_of(p.name, p.strength, p.frequency, p.duration, p.instructions, p.raw_line)


def _close(x: float, allowed: Iterable[float]) -> bool:
    return any(abs(x - a) < 1e-9 for a in allowed)


# ---------------- unit helpers ----------------
_UNIT_TOKENS = r"mg/dl|g/dl|mmol/l|meq/l|iu/l|u/l|ng/ml|pg/ml|ng/dl|ug/dl|mcg/dl|uiu/ml|miu/l|miu/ml|g/l|mg/l|umol/l|fl|pg|mm/hr|/cumm|/ul"
_UNIT_RE = re.compile(rf"(?<![a-z/])({_UNIT_TOKENS})(?![a-z])")


def _norm(s: str) -> str:
    return normalize_unit(to_ascii_digits(s)).lower()


# ---------------- unsafe / diagnosis patterns ----------------
_DIRECTIVE = [re.compile(p, re.I) for p in [
    r"\byou (?:should|must|need to|have to|ought to|can|could|may want to) (?:take|start|stop|begin|continue|increase|decrease|reduce|skip|avoid|eat|drink|consume|try|use|add|cut|exercise)\b",
    r"\b(?:start|stop|begin|continue|increase|decrease|reduce|skip|avoid) (?:taking|using|eating|drinking|the dose|your (?:medicine|medication|dose|tablets?))\b",
    r"\b(?:i|we) (?:recommend|suggest|advise|prescribe)\b",
    r"\btake (?:\d|one|two|a|an|some|more|extra|iron|vitamin|calcium|supplements?|tablets?|pills?|medicines?|medications?|antibiotics?)\b",
    r"\b(?:supplements?|supplementation|treatment|therapy|medication|medicine|dose|dosage) (?:is|are|will be) (?:needed|required|necessary|recommended|advised)\b",
    r"\bhome remed(?:y|ies)\b",
]]
_DIRECTIVE_EXEMPT = re.compile(
    r"\b(?:doctor|physician|clinician|pharmacist|medical professional|prescription|prescribed|as written|as per|according to the (?:report|prescription))\b", re.I)
_REASSURE = [re.compile(p, re.I) for p in [
    r"\bnothing to worry\b", r"\bno need to (?:worry|see|visit|consult)\b", r"\bdon'?t worry\b", r"\bnot (?:a )?(?:serious|dangerous|harmful)\b",
    r"\byou(?:'ll| will) be (?:fine|ok|okay)\b", r"\bnothing serious\b", r"\b(?:no|not a) (?:cause for|reason for) (?:concern|worry|alarm)\b",
    r"\bnothing (?:is )?wrong\b", r"\b(?:completely|perfectly) (?:fine|healthy)\b", r"\bgood news\b", r"\bis healthy\b",
]]
_DIAGNOSIS = [re.compile(p, re.I) for p in [
    r"\byou (?:have|may have|might have|probably have|likely have|are suffering from|suffer from|are (?:diabetic|anemic|anaemic))\b",
    r"\b(?:this|it|the result|the value) (?:indicates|confirms|suggests|points to|is a sign of|is a symptom of|is caused by|is due to)\b",
    r"\bdiagnos(?:is|ed|e|tic of)\b", r"\bat risk of\b",
]]
_DIAG_TERMS = re.compile(
    r"\b(?:diabet\w*|prediabet\w*|an?emi[ac]\w*|cancer\w*|leuk[a]?emia|infection\w*|kidney (?:failure|disease|damage|problem\w*)|"
    r"liver (?:disease|damage|failure|problem\w*)|hepatitis|jaundice|hypothyroid\w*|hyperthyroid\w*|dengue|malaria|typhoid|tuberculosis|"
    r"thalass[a]?emia|thrombocytopeni\w*|leukopeni\w*|leukocytosis|polycyth[a]?emia|dehydrat\w*|heart (?:disease|attack|failure)|stroke|"
    r"hypertension|gout|deficien\w*|fatty liver|sepsis|inflammation of)\b", re.I)
# Native-script patterns (Hindi, Punjabi). Other languages rely on the back-translation checks and the judge.
_NATIVE_UNSAFE = [re.compile(p) for p in [
    r"(?:दवा|दवाई|गोली|टैबलेट|कैप्सूल).{0,20}(?:लें|लीजिए|लीजिये|खाएं|खाइए|बंद करें|बढ़ाएं|घटाएं|शुरू करें)",
    r"घबराने की (?:कोई )?(?:ज़रूरत|जरूरत) नहीं|चिंता की कोई बात नहीं|कोई चिंता नहीं",
    r"आपको .{0,20}(?:बीमारी|रोग) है",
    r"(?:ਦਵਾਈ|ਗੋਲੀ|ਟੈਬਲੇਟ|ਕੈਪਸੂਲ).{0,20}(?:ਲਵੋ|ਖਾਓ|ਬੰਦ ਕਰੋ|ਵਧਾਓ|ਘਟਾਓ|ਸ਼ੁਰੂ ਕਰੋ)",
    r"ਚਿੰਤਾ ਕਰਨ ਦੀ ਲੋੜ ਨਹੀਂ|ਕੋਈ ਚਿੰਤਾ ਨਹੀਂ|ਘਬਰਾਉਣ ਦੀ ਲੋੜ ਨਹੀਂ",
    r"ਤੁਹਾਨੂੰ .{0,20}(?:ਬਿਮਾਰੀ|ਰੋਗ) ਹੈ",
]]
_SENT_SPLIT = re.compile(r"(?<=[.!?।॥])\s+|\n+")


def check_unsafe_english(text: str) -> list[tuple[str, str]]:
    """Returns list of (kind, sentence)."""
    hits = []
    for sent in _SENT_SPLIT.split(text or ""):
        if not sent.strip():
            continue
        if any(p.search(sent) for p in _DIRECTIVE) and not _DIRECTIVE_EXEMPT.search(sent):
            hits.append(("treatment_or_advice", sent.strip()))
        if any(p.search(sent) for p in _REASSURE):
            hits.append(("false_reassurance", sent.strip()))
        if any(p.search(sent) for p in _DIAGNOSIS):
            hits.append(("diagnosis", sent.strip()))
    return hits


def check_unsafe_native(text: str) -> list[tuple[str, str]]:
    return [("native_pattern", m.group(0)) for p in _NATIVE_UNSAFE for m in [p.search(text or "")] if m]


def script_ratio(text: str, script: str) -> float:
    keys = tuple(script.split("|"))
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0
    hits = 0
    for c in letters:
        try:
            name = unicodedata.name(c)
        except ValueError:
            continue
        if name.startswith(keys) or any(k in name for k in keys):
            hits += 1
    return hits / len(letters)


class SafetyService:
    def __init__(self, settings: Settings):
        self.s = settings

    # ------------------------------------------------------------------
    def validate(self, draft: Draft, facts: Facts, language: str, judge: Optional[JudgeResult] = None,
                 context_text: str = "", judge_required: bool = False, judge_error: str = "",
                 check_script: bool = True) -> SafetyReport:
        v: list[Violation] = []
        metrics: dict[str, float] = {}
        by_id = {m.id: m for m in facts.measurements}
        rx_by_id = {p.id: p for p in facts.prescriptions}
        items = {i.id: i for i in draft.items}
        rx_items = {i.id: i for i in draft.prescription_items}

        # --- entity preservation (completeness, no extras, no duplicates) ---
        dup = len(draft.items) - len(items) + len(draft.prescription_items) - len(rx_items)
        missing = [i for i in by_id if i not in items] + [i for i in rx_by_id if i not in rx_items]
        extra = [i for i in items if i not in by_id] + [i for i in rx_items if i not in rx_by_id]
        for i in missing:
            v.append(Violation(check="entity_preservation", detail=f"No explanation returned for {i}.", item_id=i))
        for i in extra:
            v.append(Violation(check="entity_preservation", detail=f"Explanation for unknown id {i}.", item_id=i))
        if dup > 0:
            v.append(Violation(check="entity_preservation", detail="Duplicate ids in output."))
        total_ids = len(by_id) + len(rx_by_id)
        metrics["entity_preservation"] = 1.0 - (len(missing) + len(extra) + max(dup, 0)) / max(total_ids, 1) if total_ids else 1.0

        # --- numerical fidelity ---
        global_allowed: set[float] = set()
        for m in facts.measurements:
            global_allowed |= measurement_numbers(m)
        for p in facts.prescriptions:
            global_allowed |= prescription_numbers(p)
        if self.s.allow_context_numbers:
            global_allowed |= set(extract_numbers(context_text))
        n_total = n_ok = 0

        def check_numbers(text: str, allowed: set[float], item_id: Optional[str], where: str):
            nonlocal n_total, n_ok
            for x in extract_numbers(text):
                n_total += 1
                if _close(x, allowed):
                    n_ok += 1
                else:
                    v.append(Violation(check="numerical_fidelity", item_id=item_id,
                                       detail=f"Number {x:g} in {where} does not belong to the report facts."))

        for iid, it in items.items():
            if iid in by_id:
                allowed = measurement_numbers(by_id[iid])
                for where, t in (("explanation", it.explanation), ("warning", it.warning), ("back-translation", it.english_back_translation)):
                    check_numbers(t, allowed, iid, where)
        for iid, it in rx_items.items():
            if iid in rx_by_id:
                for where, t in (("explanation", it.explanation), ("back-translation", it.english_back_translation)):
                    check_numbers(t, prescription_numbers(rx_by_id[iid]), iid, where)
        for where, t in (("summary", draft.overall_summary), ("summary back-translation", draft.overall_summary_en),
                         ("questions", " ".join(draft.questions_for_doctor + draft.questions_for_doctor_en)),
                         ("disclaimer", draft.localized_disclaimer)):
            check_numbers(t, global_allowed, None, where)
        metrics["numerical_accuracy"] = n_ok / n_total if n_total else 1.0

        # --- unit preservation ---
        allowed_units = {_norm(m.unit) for m in facts.measurements if m.unit} | {_norm(p.strength.lstrip("0123456789. ")) for p in facts.prescriptions if p.strength}
        unit_checks = unit_fail = 0
        for iid, it in items.items():
            m = by_id.get(iid)
            if not m:
                continue
            for t in (it.explanation, it.english_back_translation):
                text = to_ascii_digits(t or "")
                if m.unit and m.value_text:
                    pat = re.compile(r"(?<![\d.])" + re.escape(m.value_text) + r"(?!\d|\.\d)")
                    for mt in pat.finditer(text):
                        unit_checks += 1
                        after = _norm(text[mt.end(): mt.end() + 30])
                        if _norm(m.unit) not in after:
                            unit_fail += 1
                            v.append(Violation(check="unit_preservation", item_id=iid,
                                               detail=f"Value {m.value_text} must be followed by its unit '{m.unit}'."))
                            break
        for it in list(draft.items) + []:
            for t in (it.explanation, it.warning, it.english_back_translation):
                for mt in _UNIT_RE.finditer(_norm(to_ascii_digits(t or ""))):
                    if mt.group(1) not in allowed_units:
                        v.append(Violation(check="unit_preservation", item_id=it.id,
                                           detail=f"Unit '{mt.group(1)}' does not appear in the report."))
        metrics["unit_preservation"] = 1.0 - unit_fail / unit_checks if unit_checks else 1.0

        # --- range accuracy ---
        r_total = r_ok = 0
        for iid, it in items.items():
            m = by_id.get(iid)
            if not m:
                continue
            r_total += 1
            ok = True
            if it.claimed_status != m.status:
                ok = False
                v.append(Violation(check="range_accuracy", item_id=iid,
                                   detail=f"claimed_status '{it.claimed_status}' but the software status is '{m.status}'."))
            if m.status in ("low", "high") and not it.warning.strip():
                ok = False
                v.append(Violation(check="range_accuracy", item_id=iid, detail="Out-of-range value has no warning."))
            r_ok += ok
        metrics["range_accuracy"] = r_ok / r_total if r_total else 1.0

        # --- abstention on low confidence / unknown status ---
        a_total = a_ok = 0
        for iid, it in items.items():
            m = by_id.get(iid)
            if m and (m.status == "unknown" or m.confidence < self.s.min_extraction_confidence):
                a_total += 1
                ok = bool(it.warning.strip()) and it.claimed_status == "unknown" if m.status == "unknown" else bool(it.warning.strip())
                if not ok:
                    v.append(Violation(check="abstention", item_id=iid,
                                       detail="Unknown status or low extraction confidence requires a cautious warning and claimed_status 'unknown'."))
                a_ok += ok
        metrics["abstention"] = a_ok / a_total if a_total else 1.0

        # --- unsafe recommendation / diagnosis (rules) ---
        english_texts: list[tuple[Optional[str], str]] = [(None, draft.overall_summary_en), (None, " ".join(draft.questions_for_doctor_en))]
        native_texts: list[tuple[Optional[str], str]] = [(None, draft.overall_summary), (None, " ".join(draft.questions_for_doctor)), (None, draft.localized_disclaimer)]
        for it in draft.items:
            english_texts += [(it.id, it.english_back_translation)]
            native_texts += [(it.id, it.explanation), (it.id, it.warning)]
        for it in draft.prescription_items:
            english_texts += [(it.id, it.english_back_translation)]
            native_texts += [(it.id, it.explanation)]
        if judge and judge.back_translation:
            english_texts.append((None, judge.back_translation))
        if get_language(language).code == "en":
            english_texts += native_texts
        seen_unsafe = set()
        for iid, t in english_texts:
            for kind, sent in check_unsafe_english(t):
                if (kind, sent) not in seen_unsafe:
                    seen_unsafe.add((kind, sent))
                    v.append(Violation(check="unsafe_recommendation", item_id=iid, detail=f"{kind}: \"{sent[:140]}\""))
        for iid, t in native_texts:
            for kind, sent in check_unsafe_native(t):
                v.append(Violation(check="unsafe_recommendation", item_id=iid, detail=f"{kind}: \"{sent[:140]}\""))
        unsafe_count = sum(1 for x in v if x.check == "unsafe_recommendation")
        metrics["unsafe_recommendation_count"] = float(unsafe_count)

        # --- unsupported claims: disease / deficiency terms not present in the report itself ---
        report_lower = (facts.report_text or "").lower()
        diag_hits = 0
        for iid, t in english_texts:
            for mt in _DIAG_TERMS.finditer(t or ""):
                if mt.group(0).lower() not in report_lower:
                    diag_hits += 1
                    v.append(Violation(check="unsupported_claim", item_id=iid,
                                       detail=f"Condition term '{mt.group(0)}' is not in the report."))
        metrics["unsupported_claim_count"] = float(diag_hits)

        # --- output language / script ---
        lang = get_language(language)
        if check_script and lang.script:
            body = " ".join(i.explanation for i in draft.items) + " " + draft.overall_summary
            body = re.sub(r"[A-Za-z0-9/%.,()\-\s]+", " ", body)  # ignore test names, units, numbers
            ratio = script_ratio(body, lang.script)
            metrics["script_ratio"] = ratio
            if body.strip() and ratio < 0.6:
                v.append(Violation(check="language_script", detail=f"Output is not mainly in {lang.name} script (ratio {ratio:.2f})."))

        # --- LLM judge ---
        judge_used = judge is not None
        if judge is not None:
            for c in judge.unsupported_claims:
                v.append(Violation(check="unsupported_claim", detail=f"[judge] {c[:160]}"))
            for c in judge.unsafe_claims:
                v.append(Violation(check="unsafe_recommendation", detail=f"[judge] {c[:160]}"))
            for c in judge.contradictions_with_facts:
                v.append(Violation(check="contradiction", detail=f"[judge] {c[:160]}"))
            if not judge.meaning_preserved:
                v.append(Violation(check="translation_quality", detail="[judge] meaning of the facts is not preserved."))
            metrics["judge_fluency"] = float(judge.fluency_score)
            metrics["meaning_preserved"] = 1.0 if judge.meaning_preserved else 0.0
            metrics["unsupported_claim_count"] += len(judge.unsupported_claims)
            metrics["unsafe_recommendation_count"] += len(judge.unsafe_claims)
        elif judge_required:
            v.append(Violation(check="judge_unavailable", severity="critical" if self.s.judge_fail_closed else "warning",
                               detail=judge_error or "The independent judge could not run."))

        # de-duplicate
        uniq, seen = [], set()
        for x in v:
            key = (x.check, x.item_id, x.detail)
            if key not in seen:
                seen.add(key)
                uniq.append(x)
        return SafetyReport(passed=not any(x.severity == "critical" for x in uniq), violations=uniq, metrics=metrics,
                            judge_used=judge_used, evaluator_version=EVALUATOR_VERSION)
