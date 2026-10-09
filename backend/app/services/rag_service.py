"""Retrieval over APPROVED knowledge sources only. Returns chunks with source metadata."""
import logging
from pathlib import Path

from backend.app.config import Settings
from backend.app.schemas import ContextChunk, Measurement
from rag.chunking import load_chunks

logger = logging.getLogger(__name__)


class RagService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = self._load_store()

    def _load_store(self):
        p = Path(self.settings.vector_store_path)
        if (p / "index.faiss").exists():
            try:
                from rag.embeddings import Embedder
                from rag.vector_store import FaissStore

                logger.info("Loading FAISS index from %s", p)
                return FaissStore.load(str(p), Embedder(self.settings.embedding_model))
            except Exception as e:  # missing ML stack etc.
                logger.warning("FAISS index unavailable (%s); using lexical fallback.", e)
        from rag.vector_store import LexicalStore

        return LexicalStore(load_chunks(self.settings.knowledge_dir))

    @property
    def kind(self) -> str:
        return self.store.kind

    def retrieve(self, measurements: list[Measurement]) -> list[ContextChunk]:
        min_score = self.settings.retrieval_min_score if self.store.kind == "faiss" else 0.0
        seen: dict[str, ContextChunk] = {}
        for m in measurements:
            query = f"{m.test_name} laboratory test meaning"
            for score, ch in self.store.search(query, self.settings.top_k, min_score):
                if ch.chunk_id not in seen:
                    seen[ch.chunk_id] = ContextChunk(
                        id=f"S{len(seen) + 1}", source=ch.source, section=ch.section,
                        version=ch.version, text=ch.text, score=round(score, 3),
                    )
        return list(seen.values())
