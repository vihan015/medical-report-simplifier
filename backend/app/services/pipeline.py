"""Orchestration: parse/OCR -> extraction -> range check -> retrieval -> LLM -> safety -> response."""
import json
import logging
import os
from functools import lru_cache
from typing import Optional

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import Settings, get_settings
from backend.app.languages import get_language
from backend.app.schemas import (DisplayItem, Draft, EvaluateRequest, ExtractionResult, JudgeResult, PageInfo,
                                 SafetyReport, SimplifyResponse, Violation)
from backend.app.services import extraction_service, i18n, pdf_parser
from backend.app.services.llm_service import LLMError, LLMService, facts_payload
from backend.app.services.ocr_service import OCRService, OCRUnavailable
from backend.app.services.rag_service import RagService
from backend.app.services.safety_service import EVALUATOR_VERSION, Facts, SafetyService

logger = logging.getLogger(__name__)
PROMPT_VERSION = "1"


class Pipeline:
    def __init__(self, settings: Settings, llm: Optional[LLMService] = None):
        self.s = settings
        self.rag = RagService(settings)
        self.llm = llm or LLMService(settings)
        self.safety = SafetyService(settings)
        self.ocr = OCRService(settings.ocr_engine, settings.ocr_langs)

    # ------------------------------------------------------------ extraction
    def extract_file(self, report_id: str, path: str) -> ExtractionResult:
        ext = os.path.splitext(path)[1].lower()
        pages: list[tuple[int, str, str, Optional[float]]] = []
        infos: list[PageInfo] = []
        if ext == ".pdf":
            for pg in pdf_parser.parse_pdf(path, self.s.ocr_min_chars_per_page, self.s.max_pdf_pages):
                if pg.needs_ocr:
                    png = pdf_parser.render_page_png(path, pg.page)
                    text, conf = self.ocr.ocr_image_bytes(png)  # may raise OCRUnavailable
                    pages.append((pg.page, text, "ocr", conf))
                    infos.append(PageInfo(page=pg.page, method="ocr", chars=len(text), ocr_confidence=round(conf, 2)))
                else:
                    pages.append((pg.page, pg.text, "native", None))
                    infos.append(PageInfo(page=pg.page, method="native", chars=len(pg.text)))
        else:
            with open(path, "rb") as f:
                text, conf = self.ocr.ocr_image_bytes(f.read())
            pages.append((1, text, "image-ocr", conf))
            infos.append(PageInfo(page=1, method="image-ocr", chars=len(text), ocr_confidence=round(conf, 2)))
        result = extraction_service.extract_structured(report_id, pages)
        result.pages = infos
        if any(i.method != "native" for i in infos):
            result.warnings.append("Part of this document was read with OCR. Please check the extracted values carefully.")
        return result

    # ------------------------------------------------------------ simplify
    def _fallback(self, language: str, facts: Facts, reason: str) -> list[DisplayItem]:
        items = []
        for m in facts.measurements:
            rng = f" Range in report: {m.reference_range_text}." if m.reference_range_text else ""
            items.append(DisplayItem(
                id=m.id, kind="measurement", title=m.test_name, value_text=m.value_text, unit=m.unit,
                reference_range_text=m.reference_range_text, status=m.status,
                status_label=i18n.status_label(language, m.status), warning=i18n.fixed_warning(language, m.status),
                explanation=f"{m.test_name}: {m.value_text} {m.unit}.{rng}".replace(" .", "."), source="template",
                low_confidence=m.confidence < self.s.min_extraction_confidence))
        for p in facts.prescriptions:
            items.append(DisplayItem(id=p.id, kind="prescription", title=p.name, explanation=p.raw_line, source="template"))
        return items

    def simplify(self, extraction: ExtractionResult, language: str, db: Optional[Session] = None) -> SimplifyResponse:
        lang = get_language(language)
        facts = Facts(extraction.measurements, extraction.prescription_items, extraction.text)
        payload = facts_payload(facts.measurements, facts.prescriptions, self.s.min_extraction_confidence)
        context = self.rag.retrieve(facts.measurements) if facts.measurements else []
        context_text = " ".join(c.text for c in context)
        base = dict(report_id=extraction.report_id, language=language, language_name=lang.name,
                    document_type=extraction.document_type, disclaimer_en=i18n.DISCLAIMER_EN,
                    references=context, model=self.llm.model_name,
                    measurements=extraction.measurements, prescription_items=extraction.prescription_items)

        if not facts.measurements and not facts.prescriptions:
            return SimplifyResponse(**base, items=[], disclaimer=i18n.DISCLAIMER.get(language, i18n.DISCLAIMER_EN),
                                    safety=SafetyReport(passed=True), fallback_used=True,
                                    fallback_reason="Nothing could be read from this document, so no explanation was generated.", attempts=0)

        draft: Optional[Draft] = None
        report: Optional[SafetyReport] = None
        feedback: Optional[list[Violation]] = None
        reason = ""
        attempts = 0
        for attempts in range(1, self.s.llm_max_retries + 2):
            try:
                draft = self.llm.generate(language, payload, context, feedback)
            except (LLMError, Exception) as e:  # network, parse, schema
                logger.warning("LLM generation failed (attempt %s): %s", attempts, type(e).__name__)
                draft, reason = None, f"LLM error: {type(e).__name__}"
                feedback = [Violation(check="format", detail="Return one valid JSON object that follows the schema.")]
                continue
            judge: Optional[JudgeResult] = None
            judge_err = ""
            if self.s.judge_enabled:
                try:
                    judge = self.llm.judge(language, payload, draft, context)
                except Exception as e:
                    judge_err = f"Judge error: {type(e).__name__}"
            report = self.safety.validate(
                draft, facts, language, judge=judge, context_text=context_text,
                judge_required=self.s.judge_enabled, judge_error=judge_err, check_script=self.s.llm_provider != "mock")
            if report.passed:
                reason = ""
                break
            reason = "Safety validation failed: " + ", ".join(sorted({v.check for v in report.violations if v.severity == "critical"}))
            feedback = report.violations
        passed = bool(draft and report and report.passed)

        if passed:
            by_item = {i.id: i for i in draft.items}
            by_rx = {i.id: i for i in draft.prescription_items}
            items = []
            for m in facts.measurements:
                it = by_item[m.id]
                fixed = i18n.fixed_warning(language, m.status)
                warn = fixed + (f"\n{it.warning}" if it.warning and it.warning.strip() != fixed else "")
                items.append(DisplayItem(
                    id=m.id, kind="measurement", title=m.test_name, value_text=m.value_text, unit=m.unit,
                    reference_range_text=m.reference_range_text, status=m.status,
                    status_label=i18n.status_label(language, m.status), warning=warn, explanation=it.explanation,
                    source="llm", low_confidence=m.confidence < self.s.min_extraction_confidence))
            for p in facts.prescriptions:
                items.append(DisplayItem(id=p.id, kind="prescription", title=f"{p.form} {p.name} {p.strength}".strip(),
                                         explanation=by_rx[p.id].explanation, source="llm"))
            disclaimer = i18n.DISCLAIMER.get(language) or draft.localized_disclaimer or i18n.DISCLAIMER_EN
            resp = SimplifyResponse(**base, items=items, overall_summary=draft.overall_summary,
                                    questions_for_doctor=draft.questions_for_doctor, disclaimer=disclaimer,
                                    safety=report, attempts=attempts)
        else:
            resp = SimplifyResponse(
                **base, items=self._fallback(language, facts, reason), disclaimer=i18n.DISCLAIMER.get(language, i18n.DISCLAIMER_EN),
                safety=report or SafetyReport(passed=False, violations=[Violation(check="llm_error", detail=reason)]),
                fallback_used=True, fallback_reason=reason or "The explanation could not be generated safely.", attempts=attempts)

        if db is not None:
            self._persist(db, resp, draft)
        return resp

    def _persist(self, db: Session, resp: SimplifyResponse, draft: Optional[Draft]) -> None:
        db.add(models.GeneratedExplanation(
            report_id=resp.report_id, language=resp.language, draft_json=(draft.model_dump_json() if draft else "{}"),
            response_json=resp.model_dump_json(), model=resp.model, prompt_version=PROMPT_VERSION,
            fallback_used=int(resp.fallback_used)))
        for metric, score in resp.safety.metrics.items():
            db.add(models.EvaluationResult(
                report_id=resp.report_id, metric=metric, score=float(score),
                failure_flags={"violations": [v.check for v in resp.safety.violations if v.severity == "critical"]},
                evaluator_version=EVALUATOR_VERSION))
        db.commit()

    # ------------------------------------------------------------ evaluate (ad hoc)
    def evaluate(self, req: EvaluateRequest) -> SafetyReport:
        facts = Facts(req.measurements, req.prescription_items, req.report_text)
        return self.safety.validate(req.draft or Draft(), facts, req.language, judge=None,
                                    check_script=self.s.llm_provider != "mock")


@lru_cache
def get_pipeline() -> Pipeline:
    return Pipeline(get_settings())
