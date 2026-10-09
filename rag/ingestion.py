"""Build the vector index OFFLINE (separate from runtime inference).

    python -m rag.ingestion
"""
import json
import sys
from pathlib import Path

from backend.app.config import get_settings
from rag.chunking import load_chunks


def main() -> int:
    s = get_settings()
    chunks = load_chunks(s.knowledge_dir)
    if not chunks:
        print(f"No knowledge documents found in {s.knowledge_dir}")
        return 1
    meta = Path(__file__).parent / "metadata" / "documents.json"
    docs = {}
    for c in chunks:
        docs.setdefault(c.doc, {"doc": c.doc, "source": c.source, "version": c.version, "sections": []})["sections"].append(c.section)
    meta.write_text(json.dumps(list(docs.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Parsed {len(chunks)} chunks from {len(docs)} document(s).")
    try:
        from rag.embeddings import Embedder
        from rag.vector_store import FaissStore

        store = FaissStore.build(chunks, Embedder(s.embedding_model))
        store.save(s.vector_store_path)
        print(f"FAISS index written to {s.vector_store_path}")
    except ImportError as e:
        print(f"Skipping FAISS index ({e}). The runtime will use the lexical fallback.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
