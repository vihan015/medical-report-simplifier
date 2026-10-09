from backend.app.services.extraction_service import extract_structured, rebuild_measurement
from backend.app.utils.text_normalizer import normalize_text, to_ascii_digits

REPORT = """Patient Name: Test Person   Age 45 Years
Page 1 of 2
Test Name Result Unit Reference Range
Hemoglobin 11.2 g/dL 13.0 - 17.0
Total WBC Count 7500 /cumm 4000 - 11000
Platelet Count 95000 /cumm 150000 - 410000
Serum Ferritin 18 ng/mL
Glucose Fasting 126 mg/dL 70 - 100 H
LDL Cholesterol 150 mg/dL Optimal <100 Near optimal 100-129 High 160-189
Vitamin D 25 Hydroxy 22.3 ng/mL 30 - 100
"""


def _by_name(res):
    return {m.test_name: m for m in res.measurements}


def test_extracts_and_statuses():
    res = extract_structured("r1", [(1, REPORT, "native", None)])
    m = _by_name(res)
    assert m["Hemoglobin"].status == "low" and m["Hemoglobin"].unit == "g/dL" and m["Hemoglobin"].value_text == "11.2"
    assert m["Total WBC Count"].status == "normal"
    assert m["Platelet Count"].status == "low"
    assert m["Serum Ferritin"].status == "unknown"  # no range printed
    assert m["Glucose Fasting"].status == "high"
    assert m["LDL Cholesterol"].status == "unknown"  # ambiguous ranges
    assert m["Vitamin D 25 Hydroxy"].value == 22.3 and m["Vitamin D 25 Hydroxy"].status == "low"
    assert "Age" not in " ".join(m) and not any("Page" in k for k in m)


def test_prescription():
    res = extract_structured("r1", [(1, "Tab. Metformin 500 mg 1-0-1 after food for 30 days\nCap Amoxicillin 250mg TDS x 5 days", "native", None)])
    assert len(res.prescription_items) == 2 and not res.measurements
    p = res.prescription_items[0]
    assert p.name == "Metformin" and p.strength == "500 mg" and p.frequency == "1-0-1" and "30" in p.duration
    assert res.document_type == "prescription"


def test_stitched_cells():
    res = extract_structured("r1", [(1, "Hemoglobin\n11.2\ng/dL\n13.0 - 17.0", "ocr", 0.9)])
    assert res.measurements and res.measurements[0].status == "low"


def test_ocr_confidence_lowers_confidence():
    a = extract_structured("r", [(1, "Hemoglobin 11.2 g/dL 13.0 - 17.0", "native", None)]).measurements[0]
    b = extract_structured("r", [(1, "Hemoglobin 11.2 g/dL 13.0 - 17.0", "ocr", 0.3)]).measurements[0]
    assert b.confidence < a.confidence


def test_devanagari_digits_and_dash_normalised():
    assert to_ascii_digits("१३.५") == "13.5"
    assert normalize_text("13.0 \u2013 17.0") == "13.0 - 17.0"
    assert "10³" in to_ascii_digits("10³")  # superscripts untouched


def test_rebuild_after_user_correction():
    res = extract_structured("r1", [(1, "Hemoglobin 11.2 g/dL 13.0 - 17.0", "native", None)])
    m = res.measurements[0]
    m.value_text = "14.2"
    assert rebuild_measurement(m).status == "normal"
