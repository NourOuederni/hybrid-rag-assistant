"""A2 - text vector index and RAG retrieval."""
from __future__ import annotations

from typing import Iterable, Optional

from contracts.schemas import SourceRecord

from .config import settings
from .embeddings import Embedder
from .ingestion import Chunk
from .vectorstore import VectorStore


class TextIndex:
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self.store = VectorStore(settings.index_dir, "text")
        self._chunk_cache: Optional[dict[str, dict]] = None

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        vecs = self.embedder.embed([c.text for c in chunks])
        self.store.add(vecs, [c.__dict__.copy() for c in chunks])
        self._chunk_cache = None
        return len(chunks)

    def search(self, query: str, k: int | None = None,
               doc_ids: Optional[Iterable[str]] = None) -> list[SourceRecord]:
        k = k or settings.TOP_K
        allowed = set(doc_ids) if doc_ids else None
        qv = self.embedder.embed([query])[0]
        where = (lambda m: m["doc_id"] in allowed) if allowed else None
        return [self._record(m, s) for s, m in self.store.search(qv, k, where)]

    @staticmethod
    def _record(m: dict, score: float) -> SourceRecord:
        return SourceRecord(id=m["id"], source_type="local", doc_id=m["doc_id"], file_name=m["file_name"],
                            page=m["page"], chunk_id=m["id"], snippet=m["text"], score=round(score, 4))

    def get_chunk(self, chunk_id: str) -> Optional[SourceRecord]:
        if self._chunk_cache is None:
            self._chunk_cache = {m["id"]: m for m in self.store.metas()}
        m = self._chunk_cache.get(chunk_id)
        return self._record(m, 0.0) if m else None

    def chunks_of(self, doc_id: str) -> list[dict]:
        return [m for m in self.store.metas() if m["doc_id"] == doc_id]

    def delete_by_doc_id(self, doc_id: str) -> int:
        self._chunk_cache = None
        return self.store.delete_where(lambda m: m["doc_id"] == doc_id)

    def doc_ids(self) -> list[str]:
        return sorted({m["doc_id"] for m in self.store.metas()})
