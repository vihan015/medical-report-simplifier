import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


def make_pdf(lines):
    doc = fitz.open()
    page = doc.new_page()
    for i, ln in enumerate(lines):
        page.insert_text((50, 72 + i * 22), ln, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _upload(client, data, name="r.pdf", ctype="application/pdf"):
    return client.post("/api/reports/upload", files={"file": (name, data, ctype)})


def test_health_and_languages(client):
    assert client.get("/api/health").json()["status"] == "ok"
    codes = {l["code"] for l in client.get("/api/languages").json()}
    assert {"hi", "pa", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "en"} <= codes and len(codes) >= 30


def test_upload_validation(client):
    assert _upload(client, b"hello", "x.txt", "text/plain").status_code == 415
    assert _upload(client, b"not a pdf", "x.pdf").status_code == 400
    assert _upload(client, make_pdf(["a"]), "x.pdf", "image/png").status_code == 415


def test_end_to_end_pdf(client):
    pdf = make_pdf(["Hemoglobin 11.2 g/dL 13.0 - 17.0", "Total WBC Count 7500 /cumm 4000 - 11000", "Serum Ferritin 18 ng/mL"])
    rid = _upload(client, pdf).json()["report_id"]
    ex = client.post("/api/reports/extract", json={"report_id": rid}).json()
    assert [m["status"] for m in ex["measurements"]] == ["low", "normal", "unknown"]
    assert ex["pages"][0]["method"] == "native"
    r = client.post("/api/reports/simplify", json={"report_id": rid, "language": "hi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["safety"]["passed"] and not body["fallback_used"]
    hb = body["items"][0]
    assert hb["status"] == "low" and hb["status_label"] == "कम" and "डॉक्टर" in hb["warning"]
    assert body["disclaimer"].startswith("यह टूल")
    # another language from the same extraction, no re-upload
    r2 = client.post("/api/reports/simplify", json={"report_id": rid, "language": "ta"}).json()
    assert r2["language_name"] == "Tamil" and r2["items"][0]["status"] == "low"
    # stored explanation can be re-evaluated
    ev = client.post("/api/reports/evaluate", json={"report_id": rid})
    assert ev.status_code == 200 and ev.json()["passed"]


def test_user_correction_recomputes_status(client):
    rid = _upload(client, make_pdf(["Hemoglobin 11.2 g/dL 13.0 - 17.0"])).json()["report_id"]
    ex = client.post("/api/reports/extract", json={"report_id": rid}).json()
    m = ex["measurements"][0]
    m["value_text"] = "14.1"
    body = client.post("/api/reports/simplify", json={"report_id": rid, "language": "pa", "measurements": [m]}).json()
    assert body["items"][0]["status"] == "normal" and body["items"][0]["warning"] == ""


def test_unsafe_llm_output_falls_back_to_template(client, monkeypatch):
    from backend.app.services import pipeline as pl
    from backend.app.services.llm_service import MockProvider

    class Evil(MockProvider):
        def complete(self, system, user):
            out = super().complete(system, user)
            if system.startswith("You are an independent"):
                return out
            return out.replace('"english_back_translation": "[mock', '"english_back_translation": "You have anemia. You should take iron tablets. [mock', 1)

    p = pl.get_pipeline()
    monkeypatch.setattr(p.llm, "provider", Evil())
    rid = _upload(client, make_pdf(["Hemoglobin 11.2 g/dL 13.0 - 17.0"])).json()["report_id"]
    client.post("/api/reports/extract", json={"report_id": rid})
    body = client.post("/api/reports/simplify", json={"report_id": rid, "language": "hi"}).json()
    assert body["fallback_used"] and body["items"][0]["source"] == "template"
    assert "anemia" not in str(body["items"]).lower() and body["attempts"] == 2


def test_nothing_recognised_abstains(client):
    rid = _upload(client, make_pdf(["Dear patient, thank you for visiting."])).json()["report_id"]
    client.post("/api/reports/extract", json={"report_id": rid})
    body = client.post("/api/reports/simplify", json={"report_id": rid, "language": "hi"}).json()
    assert body["items"] == [] and body["fallback_used"]


def test_unsupported_language(client):
    rid = _upload(client, make_pdf(["Hemoglobin 11.2 g/dL 13.0 - 17.0"])).json()["report_id"]
    assert client.post("/api/reports/simplify", json={"report_id": rid, "language": "xx"}).status_code == 422
