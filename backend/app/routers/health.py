from fastapi import APIRouter

from backend.app.config import get_settings
from backend.app.languages import LANGUAGES
from backend.app.services.pipeline import get_pipeline

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    s = get_settings()
    p = get_pipeline()
    return {"status": "ok", "env": s.app_env, "llm_provider": s.llm_provider, "judge_enabled": s.judge_enabled,
            "retrieval": p.rag.kind, "ocr_available": p.ocr.available(), "ocr_engine": s.ocr_engine}


@router.get("/languages")
def languages():
    return [{"code": l.code, "name": l.name, "native": l.native, "tier": l.tier, "rtl": l.rtl} for l in LANGUAGES.values()]
