"""A9 - benchmark RAG vs GraphRAG vs the hybrid agent.

  python -m eval.run_eval                  # offline metrics only (no API key needed)
  python -m eval.run_eval --deepeval       # + DeepEval LLM-judged metrics (needs a real LLM_PROVIDER)
  python -m eval.run_eval --ingest         # index --corpus (default contracts/sample_data) first, in an isolated data dir
  python -m eval.run_eval --ingest --corpus my_pdfs --dataset eval/my_dataset.json
  python -m eval.run_eval --limit 3        # quick smoke run

Results: eval/results/latest.json and latest.csv (shown in the web app's Evaluation page).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONFIGS = {
    "RAG": dict(mode="rag", web_search_enabled=False),
    "GraphRAG": dict(mode="graphrag", web_search_enabled=False),
    "Hybrid agent": dict(mode="auto", web_search_enabled=True),
}
OFFLINE_METRICS = ["retrieval_hit", "citation_validity", "answer_overlap"]
DEEPEVAL_METRICS = ["faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall", "hallucination",
                    "citation_correctness"]


def tokens(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2}


def offline_scores(item: dict, ans) -> dict:
    srcs = [s for s in ans.sources if s.source_type in ("local", "image")]
    docs = set(item.get("docs", []))
    hit = 1.0 if (not docs and not srcs) or (docs and any(s.doc_id in docs for s in srcs)) else 0.0
    if not docs:  # out-of-corpus: success if the system answered with web sources
        hit = 1.0 if ans.used_web else 0.0
    markers = set(re.findall(r"\[(\d+)\]", ans.text))
    valid = {c.marker.strip("[]") for c in ans.citations}
    cit = 1.0 if markers <= valid else 0.0
    exp = tokens(item["expected"])
    overlap = len(exp & tokens(ans.text)) / max(1, len(exp))
    return {"retrieval_hit": hit, "citation_validity": cit, "answer_overlap": round(overlap, 3)}


def deepeval_scores(items, outputs, core):
    """Returns {config: {metric: mean}} using DeepEval with our own LLM as the judge."""
    from deepeval.metrics import (AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric,
                                  FaithfulnessMetric, HallucinationMetric)
    from deepeval.models import DeepEvalBaseLLM
    from deepeval.test_case import LLMTestCase

    class Judge(DeepEvalBaseLLM):
        def __init__(self, llm): self.llm = llm
        def load_model(self): return self.llm
        def generate(self, prompt: str, schema=None):
            raw = self.llm.complete(prompt, max_tokens=1500)
            if schema is None:
                return raw
            from core.llm import parse_json
            return schema(**(parse_json(raw) or {}))
        async def a_generate(self, prompt: str, schema=None): return self.generate(prompt, schema)
        def get_model_name(self): return f"{self.llm.name}-judge"

    judge = Judge(core.llm)
    out: dict[str, dict[str, list[float]]] = {}
    for cfg, rows in outputs.items():
        out[cfg] = {m: [] for m in DEEPEVAL_METRICS}
        for item, ans in zip(items, rows):
            ctx = [s.snippet for s in ans.sources] or ["(no context)"]
            tc = LLMTestCase(input=item["question"], actual_output=ans.text, expected_output=item["expected"],
                             retrieval_context=ctx, context=ctx)
            for name, M in [("faithfulness", FaithfulnessMetric), ("answer_relevancy", AnswerRelevancyMetric),
                            ("contextual_precision", ContextualPrecisionMetric),
                            ("contextual_recall", ContextualRecallMetric), ("hallucination", HallucinationMetric)]:
                try:
                    m = M(model=judge, threshold=0.5, async_mode=False)
                    m.measure(tc)
                    out[cfg][name].append(float(m.score))
                except Exception as e:  # noqa: BLE001
                    print(f"  ! {cfg}/{name} on {item['id']}: {e}")
            try:  # A9.3 custom G-Eval metric: are the [n] citations backed by the cited sources?
                from deepeval.metrics import GEval
                from deepeval.test_case import LLMTestCaseParams
                g = GEval(name="Citation correctness", model=judge, async_mode=False,
                          criteria="Every claim in the actual output carries a [n] marker and the passage in the "
                                   "retrieval context supports that claim. Penalise missing, invented or wrong citations.",
                          evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT,
                                             LLMTestCaseParams.RETRIEVAL_CONTEXT])
                g.measure(tc)
                out[cfg]["citation_correctness"].append(float(g.score))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {cfg}/citation_correctness on {item['id']}: {e}")
    return {c: {m: (round(statistics.mean(v), 3) if v else None) for m, v in d.items()} for c, d in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deepeval", action="store_true")
    ap.add_argument("--ingest", action="store_true", help="index the sample corpus in a temporary data dir")
    ap.add_argument("--corpus", default=str(ROOT / "contracts" / "sample_data"),
                    help="folder of PDFs to index with --ingest; the file name (without .pdf) is the document id")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dataset", default=str(ROOT / "eval" / "dataset.json"))
    args = ap.parse_args()

    from core.config import settings
    if args.ingest:
        settings.DATA_DIR = Path(tempfile.mkdtemp(prefix="eval_"))
    from contracts.schemas import ChatOptions
    from core.service import Core
    core = Core()
    if args.ingest:
        for f in sorted(Path(args.corpus).glob("*.pdf")):
            r = core.ingest_document(str(f), f.stem)
            print(f"ingested {f.name}: {r.status}")
    items = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    outputs: dict[str, list] = {}
    for cfg, opt in CONFIGS.items():
        print(f"== {cfg}")
        rows = []
        for it in items:
            try:
                rows.append(core.ask(it["question"], ChatOptions(**opt)))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {it['id']}: {e}")
                from contracts.schemas import AgentAnswer
                rows.append(AgentAnswer(text=f"(error: {e})"))
        outputs[cfg] = rows

    scores = {c: {} for c in CONFIGS}
    per_q = []
    for cfg, rows in outputs.items():
        vals = [offline_scores(it, a) for it, a in zip(items, rows)]
        for m in OFFLINE_METRICS:
            scores[cfg][m] = round(statistics.mean(v[m] for v in vals), 3)
    if args.deepeval:
        for cfg, d in deepeval_scores(items, outputs, core).items():
            scores[cfg].update(d)
    for it, *answers in zip(items, *outputs.values()):
        per_q.append({"id": it["id"], "question": it["question"], "category": it["category"],
                      "results": {c: {"answer": a.text, "sources": [s.model_dump(exclude_none=True) for s in a.sources],
                                      "route": a.route_taken, "used_web": a.used_web}
                                  for c, a in zip(CONFIGS, answers)}})
    hybrid = outputs["Hybrid agent"]
    web_q = [(it, a) for it, a in zip(items, hybrid) if it["category"] == "out_of_corpus"]
    stats = {"hybrid_answers_using_web": round(sum(a.used_web for a in hybrid) / max(1, len(hybrid)), 3),
             "hybrid_answers_local_only": round(sum((not a.used_web) and bool(a.sources) for a in hybrid) / max(1, len(hybrid)), 3),
             "out_of_corpus_answered_with_web": round(sum(a.used_web for _, a in web_q) / max(1, len(web_q)), 3) if web_q else None}
    metrics = OFFLINE_METRICS + (DEEPEVAL_METRICS if args.deepeval else [])
    result = {"sample": False, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "judge": core.llm.name if args.deepeval else None, "llm": core.llm.name, "embeddings": core.embedder.name,
              "configs": list(CONFIGS), "metrics": metrics, "scores": scores, "route_stats": stats, "questions": per_q}
    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out_dir / "latest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["configuration"] + metrics)
        for c in CONFIGS:
            w.writerow([c] + [scores[c].get(m) for m in metrics])
    print("\n" + "configuration".ljust(16) + "".join(m[:18].ljust(20) for m in metrics))
    for c in CONFIGS:
        print(c.ljust(16) + "".join(str(scores[c].get(m)).ljust(20) for m in metrics))
    print("\nroute stats:", stats, "\nwritten to", out_dir)
    if core.llm.name == "fake":
        print("NOTE: LLM_PROVIDER=fake. Numbers only validate the pipeline; set a real provider for meaningful results.")


if __name__ == "__main__":
    main()
