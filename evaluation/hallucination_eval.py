"""Strict hallucination / safety evaluation.

Modes
  detector  Runs the safety checker on hand-written GOOD and deliberately HALLUCINATED/UNSAFE drafts and reports
            precision/recall per check. No LLM needed. Run this whenever safety rules change.
  pipeline  Runs the full pipeline (extraction -> RAG -> your configured LLM -> safety) on every annotated case in
            every requested language and reports numerical accuracy, unit preservation, range accuracy,
            unsupported-claim rate, unsafe-recommendation rate, prohibited-claim hits, fallback rate, etc.
            It reports BOTH the first-draft failure rate (how often the LLM misbehaves) and the released-output
            violations (must be zero).

    python -m evaluation.hallucination_eval --mode detector
    python -m evaluation.hallucination_eval --mode pipeline --languages hi,pa,bn,ta,te
    python -m evaluation.hallucination_eval --mode both --fail-on-regression
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from backend.app.schemas import Draft, SafetyReport
from backend.app.services.extraction_service import extract_structured
from backend.app.services.safety_service import Facts, SafetyService
from evaluation.metrics import aggregate, prf

DATASET = Path(__file__).parent / "datasets" / "test_cases.json"
RESULTS = Path(__file__).parent / "results"


def _extract(case: dict):
    method = "ocr" if case.get("ocr") else "native"
    return extract_structured(case["id"], [(1, case["report_text"], method, 0.9 if method == "ocr" else None)])


# ------------------------------------------------------------------ detector
def run_detector(data: dict, safety: SafetyService) -> dict:
    cases = {c["id"]: c for c in data["cases"]}
    per_check = defaultdict(lambda: [0, 0, 0])  # tp, fp, fn
    good_ok = good_total = bad_caught = bad_total = 0
    failures = []
    for d in data["drafts"]:
        ex = _extract(cases[d["case"]])
        rep = safety.validate(Draft.model_validate(d["draft"]), Facts(ex.measurements, ex.prescription_items, ex.text),
                              d["language"], check_script=False)
        flagged = {v.check for v in rep.violations if v.severity == "critical"}
        expected = set(d["expected_checks"])
        if d["should_pass"]:
            good_total += 1
            good_ok += rep.passed
            if not rep.passed:
                failures.append({"draft": d["id"], "problem": "false positive", "flagged": sorted(flagged)})
        else:
            bad_total += 1
            bad_caught += (not rep.passed) and expected <= flagged
            if rep.passed or not expected <= flagged:
                failures.append({"draft": d["id"], "problem": "missed", "expected": sorted(expected), "flagged": sorted(flagged)})
        for c in expected | flagged:
            t = per_check[c]
            t[0] += c in expected and c in flagged
            t[1] += c in flagged and c not in expected and not d["should_pass"]
            t[2] += c in expected and c not in flagged
    return {"good_drafts_passed": f"{good_ok}/{good_total}", "bad_drafts_caught": f"{bad_caught}/{bad_total}",
            "detection_recall": round(bad_caught / bad_total, 4) if bad_total else None,
            "false_positive_rate": round(1 - good_ok / good_total, 4) if good_total else None,
            "per_check": {k: prf(*v) for k, v in sorted(per_check.items())}, "failures": failures}


# ------------------------------------------------------------------ extraction accuracy
def extraction_accuracy(case: dict, ex) -> dict:
    exp = case["expected"]
    total = ok = 0
    errs = []
    for i, e in enumerate(exp["measurements"]):
        total += 1
        m = ex.measurements[i] if i < len(ex.measurements) else None
        good = bool(m and m.value_text == e["value_text"] and m.unit == e["unit"] and m.status == e["status"]
                    and (e.get("test_name") is None or m.test_name == e["test_name"]))
        ok += good
        if not good:
            errs.append({"case": case["id"], "expected": e, "got": m.model_dump(include={"test_name", "value_text", "unit", "status"}) if m else None})
    for i, e in enumerate(exp["prescriptions"]):
        total += 1
        p = ex.prescription_items[i] if i < len(ex.prescription_items) else None
        good = bool(p and p.name == e["name"] and p.strength == e["strength"] and p.frequency == e["frequency"])
        ok += good
        if not good:
            errs.append({"case": case["id"], "expected": e, "got": p.model_dump(include={"name", "strength", "frequency"}) if p else None})
    return {"total": total, "correct": ok, "errors": errs}


# ------------------------------------------------------------------ pipeline
def run_pipeline(data: dict, languages: list[str] | None) -> dict:
    from backend.app.config import get_settings
    from backend.app.services.pipeline import get_pipeline

    pipe = get_pipeline()
    captured_drafts: list[Draft] = []
    first_reports: list[SafetyReport] = []
    orig_gen, orig_val = pipe.llm.generate, pipe.safety.validate

    def gen(*a, **k):
        d = orig_gen(*a, **k)
        captured_drafts.append(d)
        return d

    def val(*a, **k):
        r = orig_val(*a, **k)
        attempt_reports.append(r)
        return r

    pipe.llm.generate, pipe.safety.validate = gen, val
    released, first_attempt, rows = [], [], []
    ext_total = ext_ok = prohibited_hits = fallbacks = runs = 0
    ext_errors = []
    try:
        for case in data["cases"]:
            ex = _extract(case)
            acc = extraction_accuracy(case, ex)
            ext_total += acc["total"]
            ext_ok += acc["correct"]
            ext_errors += acc["errors"]
            for lang in languages or [case["language"]]:
                captured_drafts.clear()
                attempt_reports = []
                resp = pipe.simplify(ex, lang, None)
                runs += 1
                fallbacks += resp.fallback_used
                if attempt_reports:
                    first_attempt.append(attempt_reports[0])
                released.append(resp.safety)
                shipped = " ".join(f"{i.title} {i.explanation} {i.warning}" for i in resp.items if i.source == "llm") + " " + resp.overall_summary
                hits = [t for t in case.get("prohibited_claims", []) if t.lower() in shipped.lower()]
                if resp.fallback_used is False:  # also scan the English back-translations of the released draft
                    for dr in captured_drafts[-1:]:
                        blob = " ".join([dr.overall_summary_en] + [i.english_back_translation for i in dr.items] +
                                        [i.english_back_translation for i in dr.prescription_items]).lower()
                        hits += [t for t in case.get("prohibited_claims", []) if t.lower() in blob and t not in hits]
                prohibited_hits += bool(hits)
                rows.append({"case": case["id"], "language": lang, "passed": resp.safety.passed, "fallback": resp.fallback_used,
                             "attempts": resp.attempts, "prohibited_claim_hits": hits,
                             "critical_violations": sorted({v.check for v in resp.safety.violations if v.severity == "critical"})})
    finally:
        pipe.llm.generate, pipe.safety.validate = orig_gen, orig_val
    return {
        "provider": get_settings().llm_provider, "model": pipe.llm.model_name, "runs": runs,
        "extraction_accuracy": round(ext_ok / ext_total, 4) if ext_total else None, "extraction_errors": ext_errors,
        "first_draft_metrics": aggregate(first_attempt),
        "released_output_metrics": aggregate([r for r, row in zip(released, rows) if not row["fallback"]]),
        "fallback_rate": round(fallbacks / runs, 4) if runs else None,
        "prohibited_claim_rate_in_released_text": round(prohibited_hits / runs, 4) if runs else None,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["detector", "pipeline", "both"], default="both")
    ap.add_argument("--languages", default="", help="comma separated codes; default: each case's own language")
    ap.add_argument("--fail-on-regression", action="store_true", help="exit 1 if detector misses a bad draft or released text has violations")
    a = ap.parse_args()
    from backend.app.config import get_settings

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    out: dict = {"timestamp": datetime.now(timezone.utc).isoformat(), "dataset_version": data["version"]}
    bad = False
    if a.mode in ("detector", "both"):
        out["detector"] = run_detector(data, SafetyService(get_settings()))
        bad |= bool(out["detector"]["failures"])
    if a.mode in ("pipeline", "both"):
        out["pipeline"] = run_pipeline(data, [x for x in a.languages.split(",") if x] or None)
        p = out["pipeline"]
        bad |= (p["prohibited_claim_rate_in_released_text"] or 0) > 0 or (p["extraction_accuracy"] or 0) < 1.0
    RESULTS.mkdir(exist_ok=True)
    f = RESULTS / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "pipeline"}, ensure_ascii=False, indent=1))
    if "pipeline" in out:
        s = {k: v for k, v in out["pipeline"].items() if k not in ("rows", "extraction_errors")}
        print(json.dumps(s, ensure_ascii=False, indent=1))
    print(f"\nFull results: {f}")
    return 1 if (a.fail_on_regression and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
