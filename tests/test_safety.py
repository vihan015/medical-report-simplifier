import json
from pathlib import Path

import pytest

from backend.app.config import get_settings
from backend.app.schemas import Draft
from backend.app.services.extraction_service import extract_structured
from backend.app.services.safety_service import Facts, SafetyService, check_unsafe_english, extract_numbers, script_ratio

DATA = json.loads((Path(__file__).parents[1] / "evaluation" / "datasets" / "test_cases.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in DATA["cases"]}
svc = SafetyService(get_settings())


def _facts(case_id):
    c = CASES[case_id]
    ex = extract_structured("t", [(1, c["report_text"], "native", None)])
    return Facts(ex.measurements, ex.prescription_items, ex.report_text if hasattr(ex, "report_text") else ex.text)


@pytest.mark.parametrize("d", DATA["drafts"], ids=[d["id"] for d in DATA["drafts"]])
def test_detector_on_labelled_drafts(d):
    rep = svc.validate(Draft.model_validate(d["draft"]), _facts(d["case"]), d["language"], check_script=False)
    flagged = {v.check for v in rep.violations if v.severity == "critical"}
    if d["should_pass"]:
        assert rep.passed, rep.violations
    else:
        assert not rep.passed
        assert set(d["expected_checks"]) <= flagged, (d["expected_checks"], flagged)


def test_number_extraction_handles_scripts_and_markers():
    assert extract_numbers("१३.५ and 1,200 and 12.5") == [13.5, 1200.0, 12.5]
    assert extract_numbers("1. first\n2) second 7") == [7.0]
    assert extract_numbers("HbA1c B12 T3") == []  # digits inside words are names, not values


def test_unsafe_exemption_for_doctor_referral():
    assert not check_unsafe_english("You should show this report to your doctor.")
    assert check_unsafe_english("You should take iron tablets.")


def test_script_ratio():
    assert script_ratio("आपका हीमोग्लोबिन कम है", "DEVANAGARI") > 0.9
    assert script_ratio("Your hemoglobin is low", "DEVANAGARI") < 0.1


def test_judge_findings_fail_validation():
    from backend.app.schemas import JudgeResult
    d = next(x for x in DATA["drafts"] if x["id"] == "good_cbc")
    rep = svc.validate(Draft.model_validate(d["draft"]), _facts("cbc_mixed"), "en", check_script=False,
                       judge=JudgeResult(unsafe_claims=["suggests iron tablets"], meaning_preserved=False))
    assert not rep.passed and {"unsafe_recommendation", "translation_quality"} <= {v.check for v in rep.violations}


def test_judge_required_but_missing_fails_closed():
    d = next(x for x in DATA["drafts"] if x["id"] == "good_cbc")
    rep = svc.validate(Draft.model_validate(d["draft"]), _facts("cbc_mixed"), "en", check_script=False, judge_required=True, judge_error="down")
    assert not rep.passed and rep.violations[-1].check == "judge_unavailable"
