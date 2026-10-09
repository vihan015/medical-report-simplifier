import pytest

from backend.app.schemas import Measurement
from backend.app.services import range_checker as rc


@pytest.mark.parametrize("text,low,high", [
    ("13.0 - 17.0", 13.0, 17.0), ("13.0 to 17.0", 13.0, 17.0), ("4,000 - 11,000", 4000, 11000),
    ("< 200", None, 200), ("upto 5.0", None, 5.0), (">= 40", 40, None), ("> 40", 40, None),
])
def test_parse(text, low, high):
    r = rc.parse_reference_range(text)
    assert r and not r.ambiguous and r.low == low and r.high == high


def test_multiple_ranges_are_ambiguous():
    assert rc.parse_reference_range("M: 13-17 F: 12-15").ambiguous
    assert rc.parse_reference_range("Optimal <100 Borderline 100-129 High 160-189").ambiguous


def test_no_range():
    assert rc.parse_reference_range("see note") is None


@pytest.mark.parametrize("v,rng,status", [
    (11.2, "13.0-17.0", "low"), (13.0, "13.0-17.0", "normal"), (17.0, "13.0-17.0", "normal"), (17.1, "13.0-17.0", "high"),
    (200, "<200", "high"), (199, "<200", "normal"), (40, ">40", "low"), (41, ">40", "normal"),
])
def test_classify(v, rng, status):
    assert rc.classify(v, rc.parse_reference_range(rng)) == status


def test_unknown_cases():
    assert rc.classify(5, None) == "unknown"
    assert rc.classify(0.5, rc.parse_reference_range("0-1"), qualifier="<") == "unknown"
    assert rc.classify(None, rc.parse_reference_range("0-1")) == "unknown"


def test_flag_conflict_is_unknown():
    m = Measurement(id="m1", test_name="X", value=5, value_text="5", reference_range_text="1-10", report_flag="H")
    assert rc.apply(m).status == "unknown" and m.status_source == "conflict"


def test_flag_without_range():
    m = Measurement(id="m1", test_name="X", value=5, value_text="5", report_flag="L")
    assert rc.apply(m).status == "low" and m.status_source == "report_marker"
