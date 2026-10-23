"""A6 - LangGraph agent: rewrite -> router -> retrieve -> grade -> (web) -> generate -> verify -> finalize.

Every node emits `route` events; the generator emits `token` events; finalize emits `final`.
Events are written with LangGraph's custom stream writer and consumed by `Agent.run`.
"""
from __future__ import annotations

import logging
import operator
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Iterator, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from contracts.schemas import ChatOptions, HistoryMessage, SourceRecord, event

from .citations import build_answer
from .config import settings
from .embeddings import Embedder
from .graph import KnowledgeGraph
from .images import ImageIndex
from .llm import LLM
from .rag import TextIndex
from .websearch import web_enabled, web_search

log = logging.getLogger("core.agent")

IMAGE_RX = re.compile(r"\b(figure|fig\.|diagram|chart|image|picture|photo|illustration|plot|architecture|schema|screenshot)\b", re.I)
FOLLOWUP_RX = re.compile(r"\b(it|its|they|them|their|this|that|those|these|he|she|him|her|also|too|same|above)\b", re.I)

SYSTEM = ("You are a careful research assistant. Answer ONLY from the numbered sources. "
          "Cite every claim with its source number like [1] or [1][2]. "
          "Prefer sources from the user's own documents; when a claim relies on a web source, say 'According to web sources'. "
          "If the sources do not contain the answer, say so plainly instead of guessing. "
          "Be concise and answer in the language of the question.")


class State(TypedDict, total=False):
    question: str
    history: list[HistoryMessage]
    options: ChatOptions
    standalone: str
    qtype: str
    needs_images: bool
    plan: list[str]
    local: list[SourceRecord]
    graph: list[SourceRecord]
    images: list[SourceRecord]
    web: list[SourceRecord]
    best: float
    sufficient: bool
    context: list[SourceRecord]
    text: str
    feedback: str
    loops: int
    retry: bool
    route: Annotated[list[str], operator.add]


class Agent:
    def __init__(self, llm: LLM, embedder: Embedder, text_index: TextIndex,
                 graph: KnowledgeGraph, images: ImageIndex) -> None:
        self.llm, self.embedder, self.ti, self.kg, self.ii = llm, embedder, text_index, graph, images
        self.floor = settings.MIN_LOCAL_SCORE if settings.MIN_LOCAL_SCORE is not None else embedder.relevance_floor
        self.graph = self._build()

    # ------------------------------------------------------------------ nodes
    def n_rewrite(self, st: State) -> dict:
        w = get_stream_writer()
        q, hist = st["question"], st.get("history") or []
        standalone = q
        if hist and (len(q.split()) < 9 or FOLLOWUP_RX.search(q)):
            conv = "\n".join(f"{m.role}: {m.content[:400]}" for m in hist[-6:])
            try:
                out = self.llm.complete(
                    "Rewrite the last user question so it is fully self-contained, using the conversation for "
                    "context. Return ONLY the rewritten question.\n\nCONVERSATION:\n" + conv + "\n\nQUESTION: " + q,
                    task="rewrite", max_tokens=150).strip()
                standalone = out or q
            except Exception as e:  # noqa: BLE001
                log.warning("rewrite failed: %s", e)
        w(event("route", node="rewrite", detail=standalone if standalone != q else "no rewrite needed"))
        return {"standalone": standalone, "route": ["rewrite"], "loops": 0}

    def n_router(self, st: State) -> dict:
        w = get_stream_writer()
        q, opts = st["standalone"], st["options"]
        kind, imgs = "factual", bool(IMAGE_RX.search(q))
        try:
            r = self.llm.complete_json(
                'Classify the question for a system that searches the user\'s documents. Return ONLY JSON '
                '{"type":"factual"|"multi_hop"|"chat","needs_images":true|false}. multi_hop = needs several facts, '
                'relationships or a comparison; chat = greeting/thanks/small talk; needs_images = asks to see or find a '
                'figure, diagram, chart or image.\n\nQUESTION: ' + q, task="route", max_tokens=60)
            if r and r.get("type") in ("factual", "multi_hop", "chat"):
                kind, imgs = r["type"], bool(r.get("needs_images", imgs))
        except Exception as e:  # noqa: BLE001
            log.warning("router failed, using defaults: %s", e)
        plan: list[str] = []
        if kind != "chat":
            if opts.mode == "rag":
                plan = ["rag"]
            elif opts.mode == "graphrag":
                plan = ["graph"]
            else:
                plan = ["rag"] + (["graph"] if kind == "multi_hop" and self.kg.stats()["nodes"] else [])
            if imgs and len(self.ii.store):
                plan.append("images")
        w(event("route", node="router", detail=f"{kind}; retrievers: {', '.join(plan) or 'none'}"))
        return {"qtype": kind, "needs_images": imgs, "plan": plan, "route": ["router"]}

    def n_retrieve(self, st: State) -> dict:
        w = get_stream_writer()
        q, plan = st["standalone"], st["plan"]
        tasks = {"rag": lambda: self.ti.search(q, settings.TOP_K),
                 "graph": lambda: self.kg.retrieve(q),
                 "images": lambda: self.ii.search_text(q, 3)}
        res: dict[str, list[SourceRecord]] = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {name: ex.submit(tasks[name]) for name in plan}
            for name, f in futs.items():
                try:
                    res[name] = f.result()
                except Exception as e:  # noqa: BLE001  (NF2: one failing retriever must not stop the answer)
                    log.warning("retriever %s failed: %s", name, e)
                    res[name] = []
                    w(event("route", node=f"retrieve_{name}", detail=f"failed: {e}"))
                else:
                    w(event("route", node=f"retrieve_{name}", detail=f"{len(res[name])} result(s)"))
        local = list(res.get("rag", []))
        graph = list(res.get("graph", []))
        seen = {s.id for s in local}
        for g in graph:  # resolve graph -> supporting text chunks so they can be cited
            for cid in g.supporting_chunk_ids:
                if cid not in seen:
                    rec = self.ti.get_chunk(cid)
                    if rec:
                        rec.score = g.score
                        local.append(rec)
                        seen.add(cid)
        local.sort(key=lambda s: -s.score)
        best = max([s.score for s in local] + [0.0])
        images = res.get("images", [])
        if st.get("needs_images"):
            for im in images[:2]:
                w(event("image", source=im.model_dump()))
        return {"local": local[: settings.TOP_K + 2], "graph": graph, "images": images, "best": best,
                "route": ["retrieve"]}

    def n_grade(self, st: State) -> dict:
        w = get_stream_writer()
        best, ok = st.get("best", 0.0), False
        if st.get("local"):
            ok = best >= self.floor
            if ok and best < self.floor + 0.15 and self.llm.name != "fake":  # borderline: ask the model
                ctx = "\n".join(f"- {s.snippet[:300]}" for s in st["local"][:3])
                try:
                    ans = self.llm.complete("Do these passages contain what is needed to answer the question? "
                                            "Reply yes or no.\n\n" + ctx + "\n\nQUESTION: " + st["standalone"],
                                            task="grade", max_tokens=5)
                    ok = ans.strip().lower().startswith("y")
                except Exception:  # noqa: BLE001
                    pass
        w(event("route", node="grade", detail=f"local context {'sufficient' if ok else 'insufficient'} (best score {best:.2f})"))
        return {"sufficient": ok, "route": ["grade"]}

    def n_web(self, st: State) -> dict:
        w = get_stream_writer()
        if not st["options"].web_search_enabled:
            w(event("route", node="web_search", detail="skipped: web search disabled"))
            return {"web": [], "route": ["web_search"]}
        if not web_enabled():
            w(event("route", node="web_search", detail="skipped: not configured"))
            return {"web": [], "route": ["web_search"]}
        results, err = web_search(st["standalone"])
        w(event("route", node="web_search", detail=f"{len(results)} result(s)" + (f" (error: {err})" if err else "")))
        return {"web": results, "route": ["web_search"]}

    def n_generate(self, st: State) -> dict:
        w = get_stream_writer()
        ctx: list[SourceRecord] = []
        # only passages that are actually relevant go to the model (irrelevant ones would be cited as "sources")
        ctx += [s for s in st.get("local", []) if s.score >= self.floor]
        ctx += st.get("graph", [])
        if st.get("needs_images"):
            ctx += st.get("images", [])[:2]
        ctx += st.get("web", [])  # local first, web last (A6.9)
        ctx = ctx[:10]
        reset = st.get("loops", 0) > 0
        text = ""
        if st["qtype"] == "chat":
            for t in self.llm.stream(st["question"], system="You are a friendly assistant for a document research "
                                     "tool. Keep it short.", task="chat", max_tokens=200):
                text += t
                w(event("token", text=t, reset=reset))
                reset = False
        else:
            blocks = []
            for i, s in enumerate(ctx, 1):
                blocks.append(f"[{i}] ({_label(s)})\n{s.snippet.strip()}\n")
            fb = f"REVIEWER FEEDBACK (fix these problems): {st['feedback']}\n\n" if st.get("feedback") else ""
            prompt = ("SOURCES:\n" + ("\n".join(blocks) if blocks else "(none)") + "\n\n" + fb +
                      "QUESTION: " + st["standalone"])
            for t in self.llm.stream(prompt, system=SYSTEM, task="generate", max_tokens=1500):
                text += t
                w(event("token", text=t, reset=reset))
                reset = False
        w(event("route", node="generate", detail=f"{len(ctx)} source(s) in context"))
        return {"text": text, "context": ctx, "route": ["generate"]}

    def n_verify(self, st: State) -> dict:
        w = get_stream_writer()
        loops = st.get("loops", 0)
        if not st.get("context") or st["qtype"] == "chat" or loops >= settings.MAX_VERIFY_LOOPS:
            return {"retry": False}
        blocks = "\n".join(f"[{i}] {s.snippet[:600]}" for i, s in enumerate(st["context"], 1))
        try:
            r = self.llm.complete_json(
                'Check the ANSWER against the SOURCES. Is every claim supported and cited correctly? Return ONLY JSON '
                '{"ok":true|false,"issues":["..."]}.\n\nSOURCES:\n' + blocks + "\n\nANSWER:\n" + st["text"],
                task="verify", max_tokens=300) or {"ok": True}
        except Exception:  # noqa: BLE001
            r = {"ok": True}
        ok = bool(r.get("ok", True))
        w(event("route", node="verify", detail="answer supported by sources" if ok else
                "revising: " + "; ".join(map(str, r.get("issues", [])))[:200]))
        return {"retry": not ok, "feedback": "; ".join(map(str, r.get("issues", []))), "loops": loops + 1,
                "route": ["verify"]}

    def n_finalize(self, st: State) -> dict:
        w = get_stream_writer()
        route = list(dict.fromkeys(st.get("route", [])))
        ans = build_answer(st["text"], st.get("context", []), route, bool(st.get("web")))
        w(event("final", answer=ans.model_dump()))
        return {}

    # ------------------------------------------------------------------ graph
    def _build(self):
        g = StateGraph(State)
        for name, fn in [("rewrite", self.n_rewrite), ("router", self.n_router), ("retrieve", self.n_retrieve),
                         ("grade", self.n_grade), ("web", self.n_web), ("generate", self.n_generate),
                         ("verify", self.n_verify), ("finalize", self.n_finalize)]:
            g.add_node(name, fn)
        g.add_edge(START, "rewrite")
        g.add_edge("rewrite", "router")
        g.add_conditional_edges("router", lambda s: "generate" if not s["plan"] else "retrieve",
                                {"generate": "generate", "retrieve": "retrieve"})
        g.add_edge("retrieve", "grade")
        g.add_conditional_edges("grade", lambda s: "generate" if s["sufficient"] else "web",
                                {"generate": "generate", "web": "web"})
        g.add_edge("web", "generate")
        g.add_edge("generate", "verify")
        g.add_conditional_edges("verify", lambda s: "generate" if s.get("retry") else "finalize",
                                {"generate": "generate", "finalize": "finalize"})
        g.add_edge("finalize", END)
        return g.compile()

    # -------------------------------------------------------------------- run
    def run(self, question: str, history: list[HistoryMessage], options: ChatOptions) -> Iterator[dict]:
        init: State = {"question": question, "history": history, "options": options, "route": []}
        try:
            for ev in self.graph.stream(init, stream_mode="custom"):
                yield ev
        except Exception as e:  # noqa: BLE001
            log.exception("agent failed")
            yield event("error", message=str(e), code=type(e).__name__)


def _label(s: SourceRecord) -> str:
    if s.source_type == "web":
        return f"web: {s.title} - {s.url}"
    if s.source_type == "image":
        return f"image: {s.figure_label} in {s.file_name}, p.{s.page}"
    if s.source_type == "graph":
        return "knowledge graph: " + ", ".join(s.entities[:5])
    return f"local: {s.file_name}, p.{s.page}"
