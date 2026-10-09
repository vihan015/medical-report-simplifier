"""Vector stores: FAISS (semantic) with a BM25 lexical fallback that needs no ML dependencies."""
import json
import math
import re
from pathlib import Path

from rag.chunking import Chunk

_STOP = {"total", "serum", "blood", "count", "test", "level", "levels", "absolute", "of", "and", "the", "in", "ratio",
         "direct", "indirect", "plasma", "random", "fasting", "post", "prandial", "pp", "fbs", "rbs"}


def _tok(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for t in toks:
        if t in _STOP:
            continue
        out.append(t[:-1] if len(t) > 3 and t.endswith("s") else t)
    return out


class LexicalStore:
    """BM25 over section titles + aliases only, so a hit means the test NAME matched."""
    kind = "lexical"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.docs = [_tok(f"{c.section} {' '.join(c.aliases)}") for c in chunks]
        self.N = len(self.docs)
        self.avg = sum(len(d) for d in self.docs) / max(self.N, 1)
        self.df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                self.df[t] = self.df.get(t, 0) + 1

    def search(self, query: str, k: int, min_score: float = 0.0) -> list[tuple[float, Chunk]]:
        q, k1, b = _tok(query), 1.5, 0.75
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in set(q):
                f = d.count(t)
                if not f:
                    continue
                idf = math.log((self.N - self.df[t] + 0.5) / (self.df[t] + 0.5) + 1)
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / max(self.avg, 1e-9)))
            if s > 0:
                scored.append((s, self.chunks[i]))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]


class FaissStore:
    kind = "faiss"

    def __init__(self, chunks: list[Chunk], index, embedder):
        self.chunks, self.index, self.embedder = chunks, index, embedder

    @classmethod
    def build(cls, chunks: list[Chunk], embedder) -> "FaissStore":
        import faiss

        vecs = embedder.encode([c.index_text() for c in chunks])
        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        return cls(chunks, index, embedder)

    def save(self, directory: str) -> None:
        import faiss

        p = Path(directory)
        p.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(p / "index.faiss"))
        (p / "chunks.json").write_text(json.dumps([c.to_dict() for c in self.chunks], ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, directory: str, embedder) -> "FaissStore":
        import faiss

        p = Path(directory)
        chunks = [Chunk(**d) for d in json.loads((p / "chunks.json").read_text(encoding="utf-8"))]
        return cls(chunks, faiss.read_index(str(p / "index.faiss")), embedder)

    def search(self, query: str, k: int, min_score: float = 0.0) -> list[tuple[float, Chunk]]:
        scores, ids = self.index.search(self.embedder.encode([query]), k)
        return [(float(s), self.chunks[i]) for s, i in zip(scores[0], ids[0]) if i >= 0 and s >= min_score]
