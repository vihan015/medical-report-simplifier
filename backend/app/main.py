import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app import models
from backend.app.config import ROOT, get_settings
from backend.app.database import SessionLocal, init_db
from backend.app.routers import evaluation, health, reports

# Never log report contents, extracted values or generated text.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()


def sync_knowledge_documents() -> None:
    meta = ROOT / "rag" / "metadata" / "documents.json"
    if not meta.exists():
        return
    with SessionLocal() as db:
        for d in json.loads(meta.read_text(encoding="utf-8")):
            row = db.query(models.KnowledgeDocument).filter_by(doc=d["doc"]).first()
            if row:
                row.source, row.version, row.sections = d["source"], d["version"], d["sections"]
            else:
                db.add(models.KnowledgeDocument(doc=d["doc"], source=d["source"], version=d["version"], sections=d["sections"]))
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sync_knowledge_documents()
    yield


app = FastAPI(title="Medical Report Simplifier", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_minute:
        return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429)
    q.append(now)
    return await call_next(request)


app.include_router(health.router)
app.include_router(reports.router)
app.include_router(evaluation.router)
