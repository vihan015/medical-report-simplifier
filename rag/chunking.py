"""Parse curated knowledge documents into chunks with source/section/version metadata.

Document format (see rag/documents/*.md):
    source: <name>
    version: <x.y>
    ## Section title
    aliases: a, b, c
    <body text>
"""
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Chunk:
    chunk_id: str
    doc: str
    source: str
    version: str
    section: str
    aliases: list[str]
    text: str

    def index_text(self) -> str:
        return f"{self.section}. Also called: {', '.join(self.aliases)}. {self.text}"

    def to_dict(self) -> dict:
        return asdict(self)


def chunk_document(path: Path) -> list[Chunk]:
    source, version, chunks = path.stem, "0", []
    section, aliases, body = None, [], []

    def flush():
        if section and body:
            text = " ".join(body).strip()
            cid = hashlib.sha1(f"{path.name}:{section}:{text}".encode()).hexdigest()[:10]
            chunks.append(Chunk(cid, path.name, source, version, section, aliases, text))

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            flush()
            section, aliases, body = line[3:].strip(), [], []
        elif section is None and line.lower().startswith("source:"):
            source = line.split(":", 1)[1].strip()
        elif section is None and line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
        elif section is not None and line.lower().startswith("aliases:"):
            aliases = [a.strip() for a in line.split(":", 1)[1].split(",") if a.strip()]
        elif section is not None:
            body.append(line)
    flush()
    for c in chunks:  # version/source are known only after the header was read
        c.source, c.version = source, version
    return chunks


def load_chunks(directory: str) -> list[Chunk]:
    out: list[Chunk] = []
    for p in sorted(Path(directory).glob("*.md")):
        out.extend(chunk_document(p))
    return out
