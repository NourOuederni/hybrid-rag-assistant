# Lumen: hybrid multimodal RAG research assistant

Upload PDFs, chat with an agent that answers with citations from your documents (text and figures),
and falls back to web search when your documents are not enough.

Keywords: RAG, GraphRAG, CLIP, LangGraph, MCP, DeepEval.

```
frontend/   web interface (vanilla HTML/CSS/JS, no build step)
backend/    FastAPI: documents, conversations, streaming chat (SQLite)
core/       AI core: ingestion, RAG, GraphRAG, CLIP, web search, LangGraph agent, citations, MCP server
contracts/  shared schemas, Mock Core, sample PDFs
eval/       DeepEval benchmark and dataset
tests/      pytest suite (runs fully offline)
GUIDE.md    step-by-step guide to finish and run everything  <-- start here
```

Quick start (offline demo, no API key):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
LLM_PROVIDER=fake ./run.sh          # then open http://localhost:8000
```

For real answers, follow GUIDE.md.
