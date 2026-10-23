"""Core tests (A1, A2, A3, A4, A6, A7) - fully offline using the fake LLM and hash embedder."""
import tempfile
from pathlib import Path

import pytest

from contracts.schemas import ChatOptions, HistoryMessage, SourceRecord
from core.citations import build_answer
from core.config import settings
from core.ingestion import parse_pdf, split_text

SAMPLE = Path(__file__).resolve().parent.parent / "contracts" / "sample_data"


@pytest.fixture()
def core():
    settings.DATA_DIR = Path(tempfile.mkdtemp())
    settings.ensure_dirs()
    from core.service import Core
    c = Core()
    for f in sorted(SAMPLE.glob("*.pdf")):
        assert c.ingest_document(str(f), f.stem).status == "ok"
    return c


def test_split_text_keeps_overlap_and_size():
    chunks = split_text("Sentence number one. " * 200, 300, 50)
    assert len(chunks) > 5 and all(len(c) <= 300 for c in chunks)


def test_parse_pdf_pages_chunks_images():
    r = parse_pdf(SAMPLE / "transformers_overview.pdf", "d", "transformers_overview.pdf", Path(tempfile.mkdtemp()))
    assert r.pages == 1 and r.chunks and r.images and not r.errors
    assert r.chunks[0].page == 1 and r.images[0].figure_label == "Figure 1"


def test_corrupted_pdf_reports_error_not_crash():
    bad = Path(tempfile.mkdtemp()) / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 garbage")
    r = parse_pdf(bad, "d", "bad.pdf", Path(tempfile.mkdtemp()))
    assert r.failed and r.errors


def test_rag_finds_right_document(core):
    top = core.search_documents("What dataset was BERT pretrained on?", 3)
    assert top[0].doc_id == "transformers_overview"


def test_delete_removes_everywhere(core):
    core.delete_document("clip_and_multimodal")
    assert "clip_and_multimodal" not in core.list_indexed_documents()
    assert all(s.doc_id != "clip_and_multimodal" for s in core.search_documents("CLIP shared embedding space", 5))
    assert core.search_images("CLIP diagram", 3) == [] or all(s.doc_id != "clip_and_multimodal" for s in core.search_images("CLIP diagram", 3))


def test_graph_retrieval_returns_entities(core):
    res = core.search_graph("What does GraphRAG add?")
    assert res and res[0].source_type == "graph" and res[0].supporting_chunk_ids


def test_image_search(core):
    res = core.search_images("diagram of the RAG pipeline", 2)
    assert res and res[0].image_path


def test_agent_answers_with_valid_citations(core):
    ans = core.ask("What dataset was BERT pretrained on?")
    assert ans.sources and "route_taken" and ans.route_taken[:2] == ["rewrite", "router"]
    for c in ans.citations:
        assert any(s.id == c.source_id for s in ans.sources)


def test_out_of_corpus_without_web_says_not_found(core):
    ans = core.ask("What is the capital of France?", ChatOptions(web_search_enabled=False))
    assert not ans.sources and "could not find" in ans.text.lower()


def test_modes_change_the_route(core):
    rag = core.ask("Which methods relate to GraphRAG?", ChatOptions(mode="rag"))
    gr = core.ask("Which methods relate to GraphRAG?", ChatOptions(mode="graphrag"))
    assert "retrieve" in rag.route_taken and "retrieve" in gr.route_taken


def test_chat_greeting_skips_retrieval(core):
    ans = core.ask("hello")
    assert "retrieve" not in ans.route_taken and not ans.sources


def test_stream_event_order(core):
    names = [e["event"] for e in core.chat("What is CLIP?", [], ChatOptions())]
    assert names[0] == "route" and "token" in names and names[-1] == "final"


def test_citation_cleanup():
    ctx = [SourceRecord(id=f"s{i}", source_type="local", file_name="a.pdf", page=i) for i in (1, 2)]
    a = build_answer("A [2] and B [9]. C [1, 2].", ctx, [], False)
    assert "[9]" not in a.text and a.text.startswith("A [1]") and [c.marker for c in a.citations] == ["[1]", "[2]"]


def test_web_failure_does_not_crash(core, monkeypatch):
    import core.agent as agent
    monkeypatch.setattr(agent, "web_enabled", lambda: True)
    monkeypatch.setattr(agent, "web_search", lambda q: ([], "network down"))
    ans = core.ask("What is the capital of France?")
    assert "web_search" in ans.route_taken and not ans.used_web
