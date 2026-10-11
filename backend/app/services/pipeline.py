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
from backend.app.services.range_checker import urgency
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
    def _template_item(self, language: str, m=None, p=None) -> DisplayItem:
        """Deterministic, human-reviewed content. Fully localised for en/hi/pa; English elsewhere."""
        if p is not None:
            return DisplayItem(id=p.id, kind="prescription", title=f"{p.form} {p.name} {p.strength}".strip(),
                               explanation=p.raw_line, source="template")
        urg = urgency(m, self.s.min_extraction_confidence)
        rng = f" Range in report: {m.reference_range_text}." if m.reference_range_text else ""
        when = i18n.urgency_text(language, urg)
        if urg in ("soon", "prompt"):
            when += " " + i18n.emergency(language)
        return DisplayItem(
            id=m.id, kind="measurement", title=m.test_name, value_text=m.value_text, unit=m.unit,
            reference_range_text=m.reference_range_text, status=m.status, status_label=i18n.status_label(language, m.status),
            warning=i18n.fixed_warning(language, m.status), explanation=f"{m.test_name}: {m.value_text} {m.unit}.{rng}".replace(" .", "."),
            what_it_means=i18n.status_meaning(language, m.status), when_to_see_doctor=when, urgency=urg,
            source="template", low_confidence=m.confidence < self.s.min_extraction_confidence)

    def _run_batch(self, language: str, ms: list, ps: list, report_text: str) -> dict:
        """One LLM call (+ retries) for a small group of tests. Never raises."""
        facts = Facts(ms, ps, report_text)
        payload = facts_payload(ms, ps, self.s.min_extraction_confidence)
        urg = {m.id: urgency(m, self.s.min_extraction_confidence) for m in ms}
        context = self.rag.retrieve(ms) if ms else []
        context_text = " ".join(c.text for c in context)
        draft: Optional[Draft] = None
        report: Optional[SafetyReport] = None
        feedback: Optional[list[Violation]] = None
        reason, attempts = "", 0
        for attempts in range(1, self.s.llm_max_retries + 2):
            try:
                draft = self.llm.generate(language, payload, context, feedback)
            except Exception as e:  # network, truncated/invalid JSON, schema mismatch
                logger.warning("LLM generation failed (attempt %s): %s", attempts, type(e).__name__)
                draft, reason = None, f"LLM error ({type(e).__name__})"
                feedback = [Violation(check="format", detail="Return one complete, valid JSON object that follows the schema.")]
                continue
            judge, judge_err = None, ""
            if self.s.judge_enabled:
                try:
                    judge = self.llm.judge(language, payload, draft, context)
                except Exception as e:
                    judge_err = f"Judge error ({type(e).__name__})"
            report = self.safety.validate(
                draft, facts, language, judge=judge, context_text=context_text, judge_required=self.s.judge_enabled,
                judge_error=judge_err, check_script=self.s.llm_provider != "mock", urgency=urg, require_complete=True)
            if report.passed:
                reason = ""
                break
            crit = [v for v in report.violations if v.severity == "critical"]
            reason = "; ".join(f"{v.check}: {v.detail}"[:110] for v in crit[:3])
            feedback = report.violations
        ok = bool(draft and report and report.passed)
        items: list[DisplayItem] = []
        if ok:
            by_item = {i.id: i for i in draft.items}
            by_rx = {i.id: i for i in draft.prescription_items}
            fixed = language in i18n.FIXED_LANGS
            for m in ms:
                it, u = by_item[m.id], urg[m.id]
                fw = i18n.fixed_warning(language, m.status)
                warn = fw + (f"\n{it.warning}" if it.warning and it.warning.strip() != fw else "")
                when = it.when_to_see_doctor
                if fixed:  # hand-written, reviewable wording replaces the model's for en/hi/pa
                    when = i18n.urgency_text(language, u) + (" " + i18n.emergency(language) if u in ("soon", "prompt") else "")
                items.append(DisplayItem(
                    id=m.id, kind="measurement", title=m.test_name, value_text=m.value_text, unit=m.unit,
                    reference_range_text=m.reference_range_text, status=m.status, status_label=i18n.status_label(language, m.status),
                    warning=warn, explanation=it.explanation, what_it_is=it.what_it_is, what_it_means=it.what_it_means,
                    should_i_worry=it.should_i_worry, when_to_see_doctor=when, urgency=u, source="llm",
                    low_confidence=m.confidence < self.s.min_extraction_confidence))
            for p in ps:
                items.append(DisplayItem(id=p.id, kind="prescription", title=f"{p.form} {p.name} {p.strength}".strip(),
                                         explanation=by_rx[p.id].explanation, source="llm"))
        else:
            items = [self._template_item(language, m=m) for m in ms] + [self._template_item(language, p=p) for p in ps]
        return {"ok": ok, "items": items, "draft": draft, "report": report or SafetyReport(
            passed=False, violations=[Violation(check="llm_error", detail=reason)]), "reason": reason, "attempts": attempts,
            "context": context, "ids": [m.id for m in ms] + [p.id for p in ps]}

    @staticmethod
    def _merge_reports(reports: list[SafetyReport]) -> SafetyReport:
        if not reports:
            return SafetyReport(passed=True)
        metrics: dict[str, list[float]] = {}
        for r in reports:
            for k, val in r.metrics.items():
                metrics.setdefault(k, []).append(val)
        merged = {k: (sum(v) if k.endswith("_count") else sum(v) / len(v)) for k, v in metrics.items()}
        return SafetyReport(passed=all(r.passed for r in reports), violations=[v for r in reports for v in r.violations],
                            metrics=merged, judge_used=any(r.judge_used for r in reports), evaluator_version=EVALUATOR_VERSION)

    def simplify(self, extraction: ExtractionResult, language: str, db: Optional[Session] = None) -> SimplifyResponse:
        lang = get_language(language)
        ms, ps = extraction.measurements, extraction.prescription_items
        base = dict(report_id=extraction.report_id, language=language, language_name=lang.name,
                    document_type=extraction.document_type, disclaimer_en=i18n.DISCLAIMER_EN, model=self.llm.model_name,
                    measurements=ms, prescription_items=ps, emergency_note=i18n.emergency(language))
        if not ms and not ps:
            return SimplifyResponse(**base, items=[], disclaimer=i18n.DISCLAIMER.get(language, i18n.DISCLAIMER_EN),
                                    safety=SafetyReport(passed=True), fallback_used=True, attempts=0,
                                    fallback_reason="Nothing could be read from this document, so no explanation was generated.")

        n = max(1, self.s.llm_batch_size)
        groups = [(ms[i:i + n], []) for i in range(0, len(ms), n)] + [([], ps[i:i + n]) for i in range(0, len(ps), n)]
        results = [self._run_batch(language, g_ms, g_ps, extraction.text) for g_ms, g_ps in groups]

        by_id = {it.id: it for r in results for it in r["items"]}
        items = [by_id[m.id] for m in ms] + [by_id[p.id] for p in ps]
        template_items = sum(1 for it in items if it.source == "template" and it.kind == "measurement") + \
            sum(1 for it in items if it.source == "template" and it.kind == "prescription")
        reasons = [r["reason"] for r in results if r["reason"]]
        drafts = [r["draft"] for r in results if r["ok"] and r["draft"]]

        # references: unique sections across batches, renumbered
        refs, seen = [], set()
        for r in results:
            for c in r["context"]:
                if (c.source, c.section) not in seen:
                    seen.add((c.source, c.section))
                    refs.append(c.model_copy(update={"id": f"S{len(refs) + 1}"}))

        fixed = language in i18n.FIXED_LANGS
        labels = i18n.labels(language) if fixed else next((d.section_labels for d in drafts if len(d.section_labels) == 4), i18n.LABELS["en"])
        emergency = i18n.emergency(language) if fixed else next((d.localized_emergency_note for d in drafts if d.localized_emergency_note), i18n.EMERGENCY_EN)
        disclaimer = i18n.DISCLAIMER.get(language) or next((d.localized_disclaimer for d in drafts if d.localized_disclaimer), "") or i18n.DISCLAIMER_EN
        questions = next((d.questions_for_doctor for d in drafts if d.questions_for_doctor), [])
        n_out = sum(1 for m in ms if m.status in ("low", "high"))
        summary = i18n.summary(language, len(ms), n_out) if ms else ""

        base.update(emergency_note=emergency)
        resp = SimplifyResponse(
            **base, items=items, overall_summary=summary, questions_for_doctor=questions, disclaimer=disclaimer,
            references=refs, safety=self._merge_reports([r["report"] for r in results]), fallback_used=template_items > 0,
            template_items=template_items, section_labels=labels, attempts=max(r["attempts"] for r in results),
            fallback_reason=("Some items could not be verified as safe and show plain facts only. Details: " + " | ".join(reasons[:2])) if reasons else "")
        if db is not None:
            self._persist(db, resp, results)
        return resp

    def _persist(self, db: Session, resp: SimplifyResponse, results: list[dict]) -> None:
        batches = [{"ids": r["ids"], "draft": r["draft"].model_dump() if r["draft"] else None} for r in results]
        db.add(models.GeneratedExplanation(
            report_id=resp.report_id, language=resp.language, draft_json=json.dumps(batches, ensure_ascii=False),
            response_json=resp.model_dump_json(), model=resp.model, prompt_version=PROMPT_VERSION, fallback_used=int(resp.fallback_used)))
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
