"""Shared data contracts (specification section 3.1).

Both tracks (AI core and platform) depend ONLY on these definitions.
Change them by mutual agreement.
"""
from __future__ import annotations

from typing import Any, Iterator, Literal, Optional, Protocol

from pydantic import BaseModel, Field

SourceType = Literal["local", "graph", "image", "web"]


class SourceRecord(BaseModel):
    id: str
    source_type: SourceType
    snippet: str = ""
    score: float = 0.0
    # local / image
    doc_id: Optional[str] = None
    file_name: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    # image
    figure_label: Optional[str] = None
    image_path: Optional[str] = None
    # graph
    entities: list[str] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    # web
    url: Optional[str] = None
    title: Optional[str] = None
    retrieved_at: Optional[str] = None


class Citation(BaseModel):
    marker: str  # e.g. "[1]"
    source_id: str


class AgentAnswer(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    route_taken: list[str] = Field(default_factory=list)
    used_web: bool = False


class IngestReport(BaseModel):
    doc_id: str
    status: Literal["ok", "partial", "failed"]
    pages: int = 0
    chunks: int = 0
    images: int = 0
    entities: int = 0
    errors: list[str] = Field(default_factory=list)


class ChatOptions(BaseModel):
    web_search_enabled: bool = True
    mode: Literal["auto", "rag", "graphrag"] = "auto"


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# ---- Streaming events (section 3.3) -------------------------------------
# Every event is a plain dict: {"event": <name>, "data": {...}}
#   route : {"node": str, "detail": str}
#   token : {"text": str}
#   image : {"source": SourceRecord-dict}
#   final : {"answer": AgentAnswer-dict}
#   error : {"message": str, "code": str}
EVENT_NAMES = ("route", "token", "image", "final", "error")


def event(name: str, **data: Any) -> dict:
    assert name in EVENT_NAMES, name
    return {"event": name, "data": data}


class CoreService(Protocol):
    """Interface the backend uses to talk to the AI core (section 3.2)."""

    def ingest_document(self, file_path: str, doc_id: str) -> IngestReport: ...

    def delete_document(self, doc_id: str) -> None: ...

    def list_indexed_documents(self) -> list[str]: ...

    def chat(
        self, question: str, history: list[HistoryMessage], options: ChatOptions
    ) -> Iterator[dict]: ...
