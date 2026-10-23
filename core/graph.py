"""A3 - knowledge graph construction and GraphRAG retrieval (NetworkX, persisted as JSON)."""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from contracts.schemas import SourceRecord

from .config import settings
from .ingestion import Chunk
from .llm import LLM, _STOP

log = logging.getLogger("core.graph")
SCHEMA = json.loads((Path(__file__).parent / "graph_schema.json").read_text(encoding="utf-8"))

EXTRACT_PROMPT = """Extract a knowledge graph from the TEXT below.
Allowed entity types: {etypes}
Preferred relation types: {rtypes}
Return ONLY JSON: {{"entities":[{{"name":str,"type":str}}],"relations":[{{"source":str,"relation":str,"target":str}}]}}
Use short canonical names (e.g. "BERT", "GLUE", "self-attention"). At most 12 entities. Relations must use entity names you listed.

TEXT:
{text}"""


def _norm(name: str) -> str:
    n = re.sub(r"[^\w\s\-]", " ", name.lower())
    n = re.sub(r"\s+", " ", n).strip()
    return n[:-1] if len(n) > 4 and n.endswith("s") and not n.endswith("ss") else n


def _toks(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if t not in _STOP and len(t) > 2}


class KnowledgeGraph:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.path = settings.index_dir / "graph.json"
        self.lock = threading.RLock()
        self.g = nx.MultiDiGraph()
        if self.path.exists():
            try:
                self.g = json_graph.node_link_graph(json.loads(self.path.read_text("utf-8")),
                                                    directed=True, multigraph=True, edges="links")
            except Exception as e:  # noqa: BLE001
                log.warning("Could not load graph (%s); starting empty", e)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(json_graph.node_link_data(self.g, edges="links")), "utf-8")

    # ---------------------------------------------------------------- build
    def _extract(self, chunk: Chunk) -> dict:
        prompt = EXTRACT_PROMPT.format(etypes=", ".join(SCHEMA["entity_types"]),
                                       rtypes=", ".join(SCHEMA["relation_types"]), text=chunk.text[:2500])
        try:
            return self.llm.complete_json(prompt, task="extract_graph", max_tokens=900) or {}
        except Exception as e:  # noqa: BLE001
            log.warning("graph extraction failed for %s: %s", chunk.id, e)
            return {"_error": str(e)}

    def _resolve(self, name: str) -> str:
        """Entity deduplication (A3.3): normalise, then fuzzy-match against existing nodes."""
        key = _norm(name)
        if key in self.g:
            return key
        close = difflib.get_close_matches(key, list(self.g.nodes), n=1, cutoff=0.92)
        return close[0] if close else key

    def add_chunks(self, chunks: list[Chunk]) -> tuple[int, list[str]]:
        if not chunks:
            return 0, []
        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(self._extract, chunks))
        errors = sorted({r["_error"] for r in results if "_error" in r})[:3]
        before = self.g.number_of_nodes()
        valid = {t.lower(): t for t in SCHEMA["entity_types"]}
        with self.lock:
            for chunk, r in zip(chunks, results):
                labels: dict[str, str] = {}
                for e in r.get("entities", []) or []:
                    name = str(e.get("name", "")).strip()
                    if len(name) < 2:
                        continue
                    key = self._resolve(name)
                    typ = valid.get(str(e.get("type", "")).lower(), "Concept")
                    if key not in self.g:
                        self.g.add_node(key, label=name, type=typ, docs=[], chunks=[])
                    node = self.g.nodes[key]
                    if chunk.doc_id not in node["docs"]:
                        node["docs"].append(chunk.doc_id)
                    if chunk.id not in node["chunks"]:
                        node["chunks"].append(chunk.id)
                    labels[name.lower()] = key
                for rel in r.get("relations", []) or []:
                    s = labels.get(str(rel.get("source", "")).lower())
                    t = labels.get(str(rel.get("target", "")).lower())
                    if s and t and s != t:
                        self.g.add_edge(s, t, relation=str(rel.get("relation", "related_to")),
                                        doc_id=chunk.doc_id, chunk_ids=[chunk.id])
            self._save()
        return self.g.number_of_nodes() - before, errors

    # ------------------------------------------------------------- retrieve
    def seeds(self, question: str) -> list[str]:
        q = _toks(question)
        qnorm = " " + _norm(question) + " "
        out = []
        with self.lock:
            for key in self.g.nodes:
                kt = _toks(key)
                if not kt:
                    continue
                if f" {key} " in qnorm or (len(kt) == 1 and kt <= q) or \
                        (len(kt) > 1 and len(kt & q) >= max(2, round(0.75 * len(kt)))):
                    out.append(key)
        return out

    def retrieve(self, question: str, hops: int | None = None, max_chunks: int = 6) -> list[SourceRecord]:
        hops = settings.GRAPH_HOPS if hops is None else hops
        seeds = self.seeds(question)
        if not seeds:
            return []
        with self.lock:
            und = self.g.to_undirected(as_view=True)
            visited, frontier = set(seeds), set(seeds)
            for _ in range(hops):
                nxt = set()
                for n in frontier:
                    nxt |= set(und.neighbors(n))
                frontier = nxt - visited
                visited |= nxt
            triples, chunk_ids = [], []

            def add_chunks(ids):
                for c in ids:
                    if c not in chunk_ids:
                        chunk_ids.append(c)

            for s in seeds:
                add_chunks(self.g.nodes[s]["chunks"][:2])
            for u, v, d in self.g.edges(data=True):
                if u in visited and v in visited and (u in seeds or v in seeds):
                    triples.append(f"{self.g.nodes[u]['label']} --{d['relation']}--> {self.g.nodes[v]['label']}")
                    add_chunks(d.get("chunk_ids", []))
            ents = [self.g.nodes[n]["label"] for n in sorted(visited, key=lambda n: (n not in seeds, n))][:15]
        snippet = "Graph facts: " + "; ".join(dict.fromkeys(triples).keys()) if triples else \
            "Entities: " + ", ".join(ents)
        rid = "graph:" + hashlib.md5(question.encode()).hexdigest()[:8]
        score = min(0.9, 0.45 + 0.1 * len(seeds))
        return [SourceRecord(id=rid, source_type="graph", snippet=snippet[:1500], score=score,
                             entities=ents, supporting_chunk_ids=chunk_ids[:max_chunks])]

    # --------------------------------------------------------------- manage
    def delete_by_doc_id(self, doc_id: str) -> None:
        with self.lock:
            for u, v, k, d in list(self.g.edges(keys=True, data=True)):
                if d.get("doc_id") == doc_id:
                    self.g.remove_edge(u, v, k)
            for n in list(self.g.nodes):
                node = self.g.nodes[n]
                if doc_id in node["docs"]:
                    node["docs"].remove(doc_id)
                    node["chunks"] = [c for c in node["chunks"] if not c.startswith(doc_id + ":")]
                if not node["docs"]:
                    self.g.remove_node(n)
            self._save()

    def export(self) -> dict:
        """JSON for visualisation (A3.6)."""
        with self.lock:
            return {
                "nodes": [{"id": n, "label": d["label"], "type": d["type"], "docs": d["docs"],
                           "degree": self.g.degree(n)} for n, d in self.g.nodes(data=True)],
                "links": [{"source": u, "target": v, "relation": d["relation"]}
                          for u, v, d in self.g.edges(data=True)],
            }

    def stats(self) -> dict:
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges()}
