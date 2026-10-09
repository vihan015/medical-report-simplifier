from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["low", "normal", "high", "unknown"]


class ReferenceRange(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    low_inclusive: bool = True
    high_inclusive: bool = True
    raw: str = ""
    ambiguous: bool = False  # several ranges / sex-specific bands: refuse to judge


class Measurement(BaseModel):
    id: str
    test_name: str
    value: Optional[float] = None
    value_text: str = ""  # canonical original text
    qualifier: Optional[str] = None  # "<", ">" ...
    unit: str = ""  # canonical original text
    reference_range_text: str = ""
    reference_range: Optional[ReferenceRange] = None
    report_flag: Optional[str] = None  # H / L printed in the report
    status: Status = "unknown"
    status_source: str = "none"  # reference_range | report_marker | conflict | none
    confidence: float = 0.5
    source_line: str = ""
    page: int = 1
    notes: list[str] = Field(default_factory=list)


class PrescriptionItem(BaseModel):
    id: str
    form: str = ""
    name: str
    strength: str = ""
    frequency: str = ""
    duration: str = ""
    instructions: str = ""
    raw_line: str = ""
    confidence: float = 0.5


class PageInfo(BaseModel):
    page: int
    method: Literal["native", "ocr", "image-ocr"]
    chars: int
    ocr_confidence: Optional[float] = None


class ExtractionResult(BaseModel):
    report_id: str
    document_type: Literal["lab_report", "prescription", "mixed", "unknown"] = "unknown"
    text: str = ""
    pages: list[PageInfo] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)
    prescription_items: list[PrescriptionItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------- LLM draft ----------------
class ItemExplanation(BaseModel):
    id: str
    claimed_status: Status = "unknown"
    explanation: str = ""
    warning: str = ""
    english_back_translation: str = ""


class PrescriptionExplanation(BaseModel):
    id: str
    explanation: str = ""
    english_back_translation: str = ""


class Draft(BaseModel):
    overall_summary: str = ""
    overall_summary_en: str = ""
    items: list[ItemExplanation] = Field(default_factory=list)
    prescription_items: list[PrescriptionExplanation] = Field(default_factory=list)
    questions_for_doctor: list[str] = Field(default_factory=list)
    questions_for_doctor_en: list[str] = Field(default_factory=list)
    localized_disclaimer: str = ""


class JudgeResult(BaseModel):
    back_translation: str = ""
    unsupported_claims: list[str] = Field(default_factory=list)
    unsafe_claims: list[str] = Field(default_factory=list)
    contradictions_with_facts: list[str] = Field(default_factory=list)
    meaning_preserved: bool = True
    fluency_score: int = 5


# ---------------- Safety ----------------
class Violation(BaseModel):
    check: str
    severity: Literal["critical", "warning"] = "critical"
    detail: str = ""
    item_id: Optional[str] = None


class SafetyReport(BaseModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    judge_used: bool = False
    evaluator_version: str = "1.0"


# ---------------- API ----------------
class UploadResponse(BaseModel):
    report_id: str
    filename: str
    size_bytes: int
    content_type: str


class ExtractRequest(BaseModel):
    report_id: str


class ContextChunk(BaseModel):
    id: str  # S1, S2 ...
    source: str
    section: str
    version: str
    text: str
    score: float = 0.0


class DisplayItem(BaseModel):
    id: str
    kind: Literal["measurement", "prescription"]
    title: str
    value_text: str = ""
    unit: str = ""
    reference_range_text: str = ""
    status: Status = "unknown"
    status_label: str = ""
    warning: str = ""
    explanation: str = ""
    source: Literal["llm", "template"] = "llm"
    low_confidence: bool = False


class SimplifyRequest(BaseModel):
    report_id: str
    language: str = "hi"
    # Optional user-corrected values (OCR can be wrong). Status is always recomputed server-side.
    measurements: Optional[list[Measurement]] = None


class SimplifyResponse(BaseModel):
    report_id: str
    language: str
    language_name: str
    document_type: str
    items: list[DisplayItem]
    overall_summary: str = ""
    questions_for_doctor: list[str] = Field(default_factory=list)
    disclaimer: str
    disclaimer_en: str
    references: list[ContextChunk] = Field(default_factory=list)
    safety: SafetyReport
    fallback_used: bool = False
    fallback_reason: str = ""
    attempts: int = 1
    model: str = ""
    measurements: list[Measurement] = Field(default_factory=list)
    prescription_items: list[PrescriptionItem] = Field(default_factory=list)


class EvaluateRequest(BaseModel):
    report_id: Optional[str] = None  # re-evaluate the latest stored explanation
    # or evaluate an arbitrary draft against facts:
    language: str = "en"
    report_text: str = ""
    measurements: list[Measurement] = Field(default_factory=list)
    prescription_items: list[PrescriptionItem] = Field(default_factory=list)
    draft: Optional[Draft] = None
