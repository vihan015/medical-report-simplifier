import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.languages import LANGUAGES
from backend.app.schemas import ExtractionResult, ExtractRequest, SimplifyRequest, SimplifyResponse, UploadResponse
from backend.app.services import extraction_service
from backend.app.services.ocr_service import OCRUnavailable
from backend.app.services.pipeline import get_pipeline

router = APIRouter(prefix="/api/reports", tags=["reports"])

ALLOWED = {".pdf": {"application/pdf"}, ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}}
MAGIC = {".pdf": (b"%PDF",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",)}


def _get_report(db: Session, report_id: str) -> models.Report:
    r = db.get(models.Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found.")
    return r


@router.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    s = get_settings()
    name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(415, "Unsupported file type. Upload a PDF, PNG, JPG or JPEG.")
    if (file.content_type or "").lower() not in ALLOWED[ext]:
        raise HTTPException(415, "The file's content type does not match its extension.")
    data = file.file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {s.max_upload_mb} MB.")
    if not data or not data.startswith(MAGIC[ext]):
        raise HTTPException(400, "The file content is not a valid " + ext.lstrip(".").upper() + ".")
    os.makedirs(s.upload_dir, exist_ok=True)
    rid = uuid.uuid4().hex
    path = os.path.join(s.upload_dir, rid + ext)  # server-generated name: no path traversal
    with open(path, "wb") as f:
        f.write(data)
    db.add(models.Report(id=rid, filename=name, content_type=file.content_type, size_bytes=len(data), file_path=path))
    db.commit()
    return UploadResponse(report_id=rid, filename=name, size_bytes=len(data), content_type=file.content_type)


@router.post("/extract", response_model=ExtractionResult)
def extract(req: ExtractRequest, db: Session = Depends(get_db)):
    s = get_settings()
    report = _get_report(db, req.report_id)
    if report.extraction_json:
        return ExtractionResult.model_validate_json(report.extraction_json)
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(410, "The original file is no longer available. Please upload again.")
    try:
        result = get_pipeline().extract_file(report.id, report.file_path)
    except OCRUnavailable as e:
        raise HTTPException(503, f"OCR is not available on the server: {e}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        report.status = "failed"
        db.commit()
        raise HTTPException(500, "The document could not be read.")
    report.extraction_json = result.model_dump_json()
    report.status = "extracted"
    for m in result.measurements:
        report.measurements.append(models.ExtractedMeasurement(
            test_name=m.test_name, value_text=m.value_text, unit=m.unit, reference_range_text=m.reference_range_text,
            status=m.status, confidence=m.confidence))
    if not s.retain_uploads:  # medical documents: do not keep them longer than needed
        try:
            os.remove(report.file_path)
        except OSError:
            pass
        report.file_path = None
    db.commit()
    return result


@router.post("/simplify", response_model=SimplifyResponse)
def simplify(req: SimplifyRequest, db: Session = Depends(get_db)):
    if req.language not in LANGUAGES:
        raise HTTPException(422, f"Unsupported language '{req.language}'.")
    report = _get_report(db, req.report_id)
    if not report.extraction_json:
        raise HTTPException(409, "Run /extract first.")
    extraction = ExtractionResult.model_validate_json(report.extraction_json)
    if req.measurements is not None:  # user-corrected values: recompute numbers and status server-side
        extraction.measurements = [extraction_service.rebuild_measurement(m) for m in req.measurements]
        report.extraction_json = extraction.model_dump_json()
    resp = get_pipeline().simplify(extraction, req.language, db)
    report.language, report.status = req.language, "simplified"
    db.commit()
    return resp
