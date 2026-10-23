"""Real implementation of the CoreService contract (section 3.2)."""
from __future__ import annotations

import logging
import shutil
from typing import Iterator, Optional

from contracts.schemas import (AgentAnswer, ChatOptions, HistoryMessage, IngestReport,
                               SourceRecord, event)

from .agent import Agent
from .config import settings
from .embeddings import get_embedder
from .graph import KnowledgeGraph
from .images import ImageIndex
from .ingestion import parse_pdf
from .llm import get_llm
from .rag import TextIndex
from .websearch import web_search

log = logging.getLogger("core.service")


class Core:
    def __init__(self) -> None:
        settings.ensure_dirs()
        self.llm = get_llm()
        self.embedder = get_embedder()
        self.text = TextIndex(self.embedder)
        self.kg = KnowledgeGraph(self.llm)
        self.images = ImageIndex(self.embedder)
        self.agent = Agent(self.llm, self.embedder, self.text, self.kg, self.images)
        log.info("Core ready: llm=%s embeddings=%s images=%s", self.llm.name, self.embedder.name, self.images.mode)

    # ---- contract ---------------------------------------------------------
    def ingest_document(self, file_path: str, doc_id: str) -> IngestReport:
        from pathlib import Path
        name = Path(file_path).name
        self.delete_document(doc_id)  # re-ingesting replaces the previous version
        parsed = parse_pdf(file_path, doc_id, name)
        if parsed.failed:
            return IngestReport(doc_id=doc_id, status="failed", pages=parsed.pages, errors=parsed.errors)
        errors = list(parsed.errors)
        n_chunks = self.text.add_chunks(parsed.chunks)
        n_img = 0
        try:
            n_img = self.images.add_images(parsed.images)
        except Exception as e:  # noqa: BLE001
            errors.append(f"image indexing failed: {e}")
        n_ent = 0
        if settings.GRAPH_EXTRACTION:
            try:
                n_ent, gerr = self.kg.add_chunks(parsed.chunks)
                errors += [f"graph extraction: {m}" for m in gerr]
            except Exception as e:  # noqa: BLE001
                errors.append(f"graph extraction failed: {e}")
        status = "ok" if not errors else "partial"
        return IngestReport(doc_id=doc_id, status=status, pages=parsed.pages, chunks=n_chunks,
                            images=n_img, entities=n_ent, errors=errors)

    def delete_document(self, doc_id: str) -> None:
        self.text.delete_by_doc_id(doc_id)
        self.kg.delete_by_doc_id(doc_id)
        self.images.delete_by_doc_id(doc_id)
        shutil.rmtree(settings.images_dir / doc_id, ignore_errors=True)

    def list_indexed_documents(self) -> list[str]:
        return self.text.doc_ids()

    def chat(self, question: str, history: list[HistoryMessage], options: ChatOptions) -> Iterator[dict]:
        return self.agent.run(question, history, options)

    # ---- helpers used by MCP / evaluation --------------------------------
    def ask(self, question: str, options: Optional[ChatOptions] = None,
            history: Optional[list[HistoryMessage]] = None) -> AgentAnswer:
        final: Optional[AgentAnswer] = None
        for ev in self.chat(question, history or [], options or ChatOptions()):
            if ev["event"] == "final":
                final = AgentAnswer(**ev["data"]["answer"])
            elif ev["event"] == "error":
                raise RuntimeError(ev["data"]["message"])
        assert final is not None
        return final

    def search_documents(self, query: str, k: int = 5) -> list[SourceRecord]:
        return self.text.search(query, k)

    def search_graph(self, query: str) -> list[SourceRecord]:
        return self.kg.retrieve(query)

    def search_images(self, query: str, k: int = 3) -> list[SourceRecord]:
        return self.images.search_text(query, k)

    def web(self, query: str):
        return web_search(query)
