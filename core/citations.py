"""A7 - turn generated text + context sources into a validated AgentAnswer."""
from __future__ import annotations

import re

from contracts.schemas import AgentAnswer, Citation, SourceRecord

_MARK = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")


def build_answer(text: str, context: list[SourceRecord], route: list[str], used_web: bool) -> AgentAnswer:
    """`context` is the numbered list the generator saw: marker [n] means context[n-1].

    - markers that do not exist are removed (A7.2)
    - remaining markers are renumbered by first appearance, with a stable mapping to sources
    """
    order: dict[int, int] = {}

    def repl(m: re.Match) -> str:
        nums = [int(x) for x in re.split(r"[,;]", m.group(1))]
        new = []
        for n in nums:
            if 1 <= n <= len(context):
                order.setdefault(n, len(order) + 1)
                new.append(f"[{order[n]}]")
        return "".join(dict.fromkeys(new))

    clean = _MARK.sub(repl, text)
    clean = re.sub(r"[ \t]+([.,;:!?])", r"\1", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    sources, citations = [], []
    for old, new in sorted(order.items(), key=lambda kv: kv[1]):
        src = context[old - 1]
        sources.append(src)
        citations.append(Citation(marker=f"[{new}]", source_id=src.id))
    return AgentAnswer(text=clean, citations=citations, sources=sources, route_taken=route,
                       used_web=any(s.source_type == "web" for s in sources) or (used_web and not sources))


def format_sources_text(answer: AgentAnswer) -> str:
    """Plain-text reference list; web claims are explicitly labelled (A7.3)."""
    lines = []
    for c in answer.citations:
        s = next(x for x in answer.sources if x.id == c.source_id)
        if s.source_type == "web":
            lines.append(f"{c.marker} [web] {s.title} - {s.url}")
        elif s.source_type == "image":
            lines.append(f"{c.marker} [image] {s.file_name}, p.{s.page}, {s.figure_label}")
        elif s.source_type == "graph":
            lines.append(f"{c.marker} [graph] {', '.join(s.entities[:6])}")
        else:
            lines.append(f"{c.marker} [local] {s.file_name}, p.{s.page}")
    return "\n".join(lines)
