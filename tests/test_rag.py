from backend.app.config import get_settings
from backend.app.schemas import Measurement
from backend.app.services.rag_service import RagService


def _m(name):
    return Measurement(id="m1", test_name=name, value=1, value_text="1")


def test_retrieves_expected_documents():
    rag = RagService(get_settings())
    for name, expected in [("Hemoglobin", "Hemoglobin"), ("Haemoglobin", "Hemoglobin"), ("Total WBC Count", "White blood cell count"),
                           ("Platelet Count", "Platelet count"), ("SGPT (ALT)", "Liver enzymes"), ("HbA1c", "HbA1c"),
                           ("Vitamin B12", "Vitamin B12")]:
        ctx = rag.retrieve([_m(name)])
        assert ctx and ctx[0].section == expected, (name, [c.section for c in ctx])
        assert ctx[0].source and ctx[0].version


def test_unknown_test_retrieves_nothing():
    assert RagService(get_settings()).retrieve([_m("Zorblax quotient")]) == []
