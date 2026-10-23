"""FastAPI backend (B1-B4). Talks to the AI core only through the CoreService contract (B1.2)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from contracts.schemas import ChatOptions, CoreService, HistoryMessage
from core.config import ROOT, settings

from . import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend")

core: CoreService = None  # type: ignore[assignment]
_ingest_pool = ThreadPoolExecutor(max_workers=1)  # one ingestion at a time keeps memory and API usage sane
_core_lock = threading.Lock()


def make_core() -> CoreService:
    """B1.2: switch between the Mock Core and the real core with USE_MOCK_CORE."""
    if settings.USE_MOCK_CORE:
        from contracts.mock_core import MockCore
        return MockCore()
    from core.service import Core
    return Core()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global core
    db.init_db()
    core = make_core()
    for d in db.pending_documents():  # B2.7: resume work interrupted by a restart
        _ingest_pool.submit(_ingest, d["id"], d["path"])
    yield


app = FastAPI(title="Hybrid RAG Research Assistant", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):  # B1.3 consistent JSON errors
    return JSONResponse({"error": {"code": exc.status_code, "message": exc.detail}}, status_code=exc.status_code)


# ----------------------------------------------------------------- system
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    from core.websearch import web_enabled
    info = {"llm": settings.LLM_PROVIDER, "mock_core": settings.USE_MOCK_CORE, "web_search_available": web_enabled(),
            "embeddings": settings.EMBEDDING_PROVIDER, "max_upload_mb": settings.MAX_UPLOAD_MB}
    for k, attr in (("embeddings_active", "embedder"), ("llm_active", "llm")):
        o = getattr(core, attr, None)
        if o is not None:
            info[k] = o.name
    images = getattr(core, "images", None)
    if images is not None:
        info["image_search"] = images.mode
    return info


@app.get("/api/stats")
def stats():
    docs = db.list_documents()
    g = getattr(getattr(core, "kg", None), "stats", lambda: {"nodes": 0, "edges": 0})()
    return {"documents": len(docs), "ready": sum(d["status"] == "ready" for d in docs),
            "chunks": sum(d["chunks"] for d in docs), "graph": g}


@app.get("/api/graph")
def graph():
    kg = getattr(core, "kg", None)
    return kg.export() if kg else {"nodes": [], "links": []}


# -------------------------------------------------------------- documents
def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", Path(name).name)[:120] or "document.pdf"


def _ingest(doc_id: str, path: str) -> None:
    db.update_document(doc_id, status="processing")
    try:
        report = core.ingest_document(path, doc_id)
        status = "failed" if report.status == "failed" else "ready"
        db.update_document(doc_id, status=status, pages=report.pages, chunks=report.chunks,
                           images=report.images, entities=report.entities, errors=report.errors)
    except Exception as e:  # noqa: BLE001
        log.exception("ingestion failed")
        db.update_document(doc_id, status="failed", errors=[str(e)])


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    name = _safe_name(file.filename or "document.pdf")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files are supported.")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.MAX_UPLOAD_MB} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "This file is not a valid PDF.")
    sha = hashlib.sha256(data).hexdigest()
    dup = db.find_document_by_hash(sha)  # B2.6
    if dup:
        raise HTTPException(409, f"'{dup['name']}' is already in your library.")
    doc_id_dir = settings.uploads_dir / hashlib.md5(sha.encode()).hexdigest()[:10]
    doc_id_dir.mkdir(parents=True, exist_ok=True)
    path = doc_id_dir / name  # keep the original name so citations show it
    path.write_bytes(data)
    doc = db.create_document(name, len(data), sha, str(path))
    _ingest_pool.submit(_ingest, doc["id"], str(path))
    return doc


@app.get("/api/documents")
def list_documents():
    return db.list_documents()


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "Document not found.")
    return d


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    d = db.get_document(doc_id, with_path=True)
    if not d or not Path(d["path"]).exists():
        raise HTTPException(404, "Document not found.")
    return FileResponse(d["path"], media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{d["name"]}"'})


@app.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    d = db.get_document(doc_id, with_path=True)
    if not d:
        raise HTTPException(404, "Document not found.")
    with _core_lock:
        core.delete_document(doc_id)
    shutil.rmtree(Path(d["path"]).parent, ignore_errors=True)
    db.delete_document(doc_id)


@app.get("/api/images/{path:path}")
def image_file(path: str):
    """B4.5: serve extracted figures, refusing anything outside the images directory."""
    base = settings.images_dir.resolve()
    target = (base / path).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(404, "Image not found.")
    return FileResponse(target)


# ---------------------------------------------------------- conversations
class TitleBody(BaseModel):
    title: str


@app.get("/api/conversations")
def list_conversations(q: str = ""):
    return db.list_conversations(q)


@app.post("/api/conversations", status_code=201)
def create_conversation():
    return db.create_conversation()


@app.get("/api/conversations/{cid}")
def get_conversation(cid: str):
    c = db.get_conversation(cid)
    if not c:
        raise HTTPException(404, "Conversation not found.")
    return {**c, "messages": db.list_messages(cid)}


@app.patch("/api/conversations/{cid}")
def rename_conversation(cid: str, body: TitleBody):
    if not db.get_conversation(cid):
        raise HTTPException(404, "Conversation not found.")
    db.rename_conversation(cid, body.title.strip()[:80] or "New chat")
    return db.get_conversation(cid)


@app.delete("/api/conversations/{cid}", status_code=204)
def delete_conversation(cid: str):
    if not db.get_conversation(cid):
        raise HTTPException(404, "Conversation not found.")
    db.delete_conversation(cid)


# ------------------------------------------------------------------- chat
class ChatBody(BaseModel):
    question: str
    web_search_enabled: bool = True
    mode: Literal["auto", "rag", "graphrag"] = "auto"


def _sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/conversations/{cid}/chat")
def chat(cid: str, body: ChatBody):
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    q = body.question.strip()
    if not q:
        raise HTTPException(422, "The question is empty.")
    history = [HistoryMessage(role=m["role"], content=m["text"]) for m in db.list_messages(cid)][-10:]
    db.add_message(cid, "user", q)
    if conv["title"] == "New chat":
        db.rename_conversation(cid, q[:48])
    options = ChatOptions(web_search_enabled=body.web_search_enabled, mode=body.mode)

    def stream():
        text, images, route, saved = "", [], [], False
        events = None
        try:
            events = core.chat(q, history, options)
            for ev in events:
                name, data = ev["event"], ev["data"]
                if name == "token":
                    text = data["text"] if data.get("reset") else text + data["text"]
                elif name == "image":
                    images.append(data["source"])
                elif name == "route":
                    route.append(data)
                elif name == "final":
                    a = data["answer"]
                    db.add_message(cid, "assistant", a["text"], a["citations"], a["sources"],
                                   route, images, a["used_web"])
                    saved = True
                yield _sse(name, data)
        except GeneratorExit:  # B4.3/B4.4: the user pressed stop or closed the tab
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("chat failed")
            yield _sse("error", {"message": str(e), "code": type(e).__name__})
        finally:
            if events is not None and hasattr(events, "close"):
                events.close()
            if not saved and text.strip():
                db.add_message(cid, "assistant", text.strip() + "\n\n*(stopped)*", route=route)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------- evaluation
@app.get("/api/eval")
def eval_results():
    for p in (ROOT / "eval" / "results" / "latest.json", ROOT / "eval" / "results" / "sample_results.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {"configs": [], "metrics": [], "questions": [], "generated_at": None}


# ---------------------------------------------------------------- frontend
FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
