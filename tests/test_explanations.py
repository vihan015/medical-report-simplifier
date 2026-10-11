import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import Measurement
from backend.app.services import i18n, range_checker as rc
from backend.app.services.extraction_service import extract_structured


def _pdf(lines):
    d = pymupdf.open()
    p = d.new_page()
    for i, ln in enumerate(lines):
        p.insert_text((40, 60 + i * 20), ln, fontsize=10)
    return d.tobytes()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _m(v, rng, conf=1.0):
    return rc.apply(Measurement(id="m1", test_name="X", value=v, value_text=str(v), reference_range_text=rng, confidence=conf))


def test_urgency_levels():
    assert rc.urgency(_m(15, "13-17")) == "routine"
    assert rc.urgency(_m(12.5, "13-17")) == "soon"
    assert rc.urgency(_m(6, "13-17")) == "prompt"          # far below
    assert rc.urgency(_m(125, "135-145")) == "prompt"       # narrow range (sodium-like)
    assert rc.urgency(_m(130, "135-145")) == "soon"
    assert rc.urgency(_m(5, "")) == "review"                # no range
    assert rc.urgency(_m(15, "13-17", conf=0.2)) == "review"  # unreliable read


def test_wrapped_table_cell_names():
    txt = "Serum Creatinine (Modified 1.01 mg/dL 0.67 - 1.17\nJaffe, Kinetic)\nTotal Bilirubin\n(DIAZOTIZATION with 0.60 mg/dL 0.3 - 1.2\nSulfanilic Acid)"
    names = [m.test_name for m in extract_structured("r", [(1, txt, "native", None)]).measurements]
    assert names == ["Serum Creatinine (Modified Jaffe, Kinetic)", "Total Bilirubin (DIAZOTIZATION with Sulfanilic Acid)"]


def test_four_parts_localised_and_batched(client, monkeypatch):
    from backend.app.config import get_settings
    from backend.app.services.pipeline import get_pipeline
    pipe = get_pipeline()
    monkeypatch.setattr(pipe.s, "llm_batch_size", 2)
    calls = []
    orig = pipe.llm.generate
    monkeypatch.setattr(pipe.llm, "generate", lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    lines = ["Hemoglobin 11.2 g/dL 13.0 - 17.0", "Total WBC Count 7500 /cumm 4000 - 11000", "Platelet Count 95000 /cumm 150000 - 410000",
             "Serum Creatinine 1.01 mg/dL 0.67 - 1.17", "Serum Ferritin 18 ng/mL"]
    rid = client.post("/api/reports/upload", files={"file": ("a.pdf", _pdf(lines), "application/pdf")}).json()["report_id"]
    client.post("/api/reports/extract", json={"report_id": rid})
    body = client.post("/api/reports/simplify", json={"report_id": rid, "language": "hi"}).json()
    assert len(calls) == 3                        # 5 tests, 2 per call
    assert body["safety"]["passed"] and not body["fallback_used"]
    assert body["section_labels"]["should_i_worry"] == "क्या चिंता करनी चाहिए?"
    assert "आपातकालीन" in body["emergency_note"]
    hb = body["items"][0]
    assert all(hb[k] for k in ("what_it_is", "what_it_means", "should_i_worry", "when_to_see_doctor"))
    assert hb["urgency"] == "soon" and "कुछ दिनों" in hb["when_to_see_doctor"]
    assert body["items"][1]["urgency"] == "routine" and "आपातकालीन" not in body["items"][1]["when_to_see_doctor"]
    assert body["items"][4]["urgency"] == "review"
    assert body["overall_summary"].startswith("इस रिपोर्ट में 5")
    ev = client.post("/api/reports/evaluate", json={"report_id": rid})
    assert ev.status_code == 200 and ev.json()["passed"]


def test_one_bad_batch_does_not_ruin_the_report(client, monkeypatch):
    from backend.app.services.llm_service import MockProvider
    from backend.app.services.pipeline import get_pipeline
    pipe = get_pipeline()
    monkeypatch.setattr(pipe.s, "llm_batch_size", 1)

    class Flaky(MockProvider):
        def complete(self, system, user):
            out = super().complete(system, user)
            if "Platelet" in user and not system.startswith("You are an independent"):
                return out.replace('"claimed_urgency": "soon"', '"claimed_urgency": "routine"')  # violates urgency check
            return out
    monkeypatch.setattr(pipe.llm, "provider", Flaky())
    lines = ["Hemoglobin 11.2 g/dL 13.0 - 17.0", "Platelet Count 95000 /cumm 150000 - 410000"]
    rid = client.post("/api/reports/upload", files={"file": ("a.pdf", _pdf(lines), "application/pdf")}).json()["report_id"]
    client.post("/api/reports/extract", json={"report_id": rid})
    body = client.post("/api/reports/simplify", json={"report_id": rid, "language": "pa"}).json()
    src = {i["title"]: i["source"] for i in body["items"]}
    assert src["Hemoglobin"] == "llm" and src["Platelet Count"] == "template" and body["template_items"] == 1
    plt = body["items"][1]       # template item is still localised and still says when to see a doctor
    assert "ਡਾਕਟਰ" in plt["when_to_see_doctor"] and plt["status_label"] == "ਘੱਟ" and plt["what_it_means"]


def test_missing_section_is_rejected():
    from backend.app.config import get_settings
    from backend.app.schemas import Draft, ItemExplanation
    from backend.app.services.safety_service import Facts, SafetyService
    m = _m(11.2, "13.0 - 17.0")
    d = Draft(items=[ItemExplanation(id="m1", claimed_status="low", claimed_urgency="soon", explanation="X 11.2.", warning="Show your doctor.")])
    rep = SafetyService(get_settings()).validate(d, Facts([m]), "en", check_script=False, urgency={"m1": "soon"}, require_complete=True)
    assert "incomplete_explanation" in {v.check for v in rep.violations}
