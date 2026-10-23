"""Mock Core: lets the platform be developed and tested with no AI at all."""
from __future__ import annotations

import time
from typing import Iterator

from .schemas import (AgentAnswer, ChatOptions, Citation, HistoryMessage,
                      IngestReport, SourceRecord, event)


class MockCore:
    def __init__(self) -> None:
        self._docs: set[str] = set()

    def ingest_document(self, file_path: str, doc_id: str) -> IngestReport:
        time.sleep(0.3)
        self._docs.add(doc_id)
        return IngestReport(doc_id=doc_id, status="ok", pages=3, chunks=12, images=1, entities=5)

    def delete_document(self, doc_id: str) -> None:
        self._docs.discard(doc_id)

    def list_indexed_documents(self) -> list[str]:
        return sorted(self._docs)

    def chat(self, question: str, history: list[HistoryMessage], options: ChatOptions) -> Iterator[dict]:
        yield event("route", node="router", detail="mock: factual question")
        yield event("route", node="retrieve_rag", detail="mock retrieval")
        src = SourceRecord(id="s1", source_type="local", doc_id="mock", file_name="mock.pdf",
                           page=1, snippet="This is a mock passage.", score=0.9)
        words = f"This is a mock answer to: {question} [1]".split(" ")
        for w in words:
            time.sleep(0.02)
            yield event("token", text=w + " ")
        ans = AgentAnswer(text=" ".join(words), citations=[Citation(marker="[1]", source_id="s1")],
                          sources=[src], route_taken=["router", "retrieve_rag", "generate"])
        yield event("final", answer=ans.model_dump())
