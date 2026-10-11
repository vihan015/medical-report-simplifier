"""Central configuration. All secrets and model settings come from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_env: str = "development"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'app.db'}"

    # LLM. provider: anthropic | openai | huggingface | mock
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # used by the "openai" provider (any OpenAI-compatible server)
    llm_temperature: float = 0.0
    llm_max_tokens: int = 8192
    llm_timeout_s: int = 120
    llm_batch_size: int = 4  # tests explained per LLM call (keeps output short enough to never be cut off)
    llm_max_retries: int = 1  # regeneration attempts after a failed safety check

    # Independent second LLM pass that audits the generated text
    judge_enabled: bool = True
    judge_fail_closed: bool = True  # if the judge cannot run, treat the draft as unsafe

    # RAG
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_store_path: str = str(ROOT / "rag" / "index")
    knowledge_dir: str = str(ROOT / "rag" / "documents")
    top_k: int = 2  # chunks retrieved per test
    retrieval_min_score: float = 0.30  # cosine threshold for the embedding index

    # Upload / OCR
    max_upload_mb: int = 15
    max_pdf_pages: int = 20
    allowed_origins: str = "http://localhost:8501"
    upload_dir: str = str(ROOT / "data" / "uploads")
    retain_uploads: bool = False  # delete the original file after text extraction
    ocr_engine: str = "tesseract"  # tesseract | paddle
    ocr_langs: str = "eng"  # e.g. eng+hin+pan  (needs matching Tesseract language packs)
    ocr_min_chars_per_page: int = 40

    # Safety
    allow_context_numbers: bool = False  # strict: only numbers from the report may appear
    min_extraction_confidence: float = 0.5
    rate_limit_per_minute: int = 60

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
