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
        resp = SimplifyResponse.model_validate_json(row.response_json)
        from backend.app.schemas import Draft
        from backend.app.services.safety_service import Facts

        draft = Draft.model_validate_json(row.draft_json)
        pipeline = get_pipeline()
        return pipeline.safety.validate(draft, Facts(resp.measurements, resp.prescription_items), resp.language,
                                        check_script=pipeline.s.llm_provider != "mock")
    if req.draft is None:
        raise HTTPException(422, "Provide report_id or a draft.")
    return get_pipeline().evaluate(req)
