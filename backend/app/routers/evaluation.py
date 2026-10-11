from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.database import get_db
from backend.app.schemas import EvaluateRequest, SafetyReport, SimplifyResponse
from backend.app.services.pipeline import get_pipeline

router = APIRouter(prefix="/api/reports", tags=["evaluation"])


@router.post("/evaluate", response_model=SafetyReport)
def evaluate(req: EvaluateRequest, db: Session = Depends(get_db)):
    """Either re-evaluate the latest stored explanation of a report, or evaluate an arbitrary draft against facts."""
    if req.report_id:
        row = db.scalars(select(models.GeneratedExplanation).where(models.GeneratedExplanation.report_id == req.report_id)
                         .order_by(models.GeneratedExplanation.pk.desc())).first()
        if not row:
            raise HTTPException(404, "No explanation stored for this report.")
        import json

        from backend.app.schemas import Draft
        from backend.app.services.range_checker import urgency
        from backend.app.services.safety_service import Facts

        resp = SimplifyResponse.model_validate_json(row.response_json)
        pipeline = get_pipeline()
        reports = []
        for b in json.loads(row.draft_json):
            if not b["draft"]:
                continue
            ms = [m for m in resp.measurements if m.id in b["ids"]]
            ps = [p for p in resp.prescription_items if p.id in b["ids"]]
            reports.append(pipeline.safety.validate(
                Draft.model_validate(b["draft"]), Facts(ms, ps), resp.language, check_script=pipeline.s.llm_provider != "mock",
                urgency={m.id: urgency(m, pipeline.s.min_extraction_confidence) for m in ms}, require_complete=True))
        return pipeline._merge_reports(reports)
    if req.draft is None:
        raise HTTPException(422, "Provide report_id or a draft.")
    return get_pipeline().evaluate(req)
