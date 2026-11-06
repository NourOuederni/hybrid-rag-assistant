"""LLM access behind one small interface.

Providers: anthropic | openai (any OpenAI-compatible server) | fake (offline, for tests/demo).
The `task` argument is ignored by real models; the fake model uses it to behave sensibly
without any API key so the whole pipeline can be tested offline.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Iterator, Optional

from .config import settings

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}


class LLM:
    name = "base"

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 task: str = "generic") -> str:
        raise NotImplementedError

    def stream(self, prompt: str, system: str = "", max_tokens: int = 1500,
               task: str = "generate") -> Iterator[str]:
        yield self.complete(prompt, system, max_tokens, task)

    def complete_json(self, prompt: str, system: str = "", max_tokens: int = 1024,
                      task: str = "generic") -> Optional[dict]:
        raw = self.complete(prompt, system, max_tokens, task)
        return parse_json(raw)


def parse_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.LLM_MODEL or DEFAULT_MODELS["anthropic"]

    def complete(self, prompt, system="", max_tokens=1024, task="generic"):
        kw = {"system": system} if system else {}
        r = self.client.messages.create(model=self.model, max_tokens=max_tokens,
                                        messages=[{"role": "user", "content": prompt}], **kw)
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")

    def stream(self, prompt, system="", max_tokens=1500, task="generate"):
        kw = {"system": system} if system else {}
        with self.client.messages.stream(model=self.model, max_tokens=max_tokens,
                                         messages=[{"role": "user", "content": prompt}], **kw) as s:
            for t in s.text_stream:
                yield t


class OpenAILLM(LLM):
    name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI
        kw = {"api_key": settings.OPENAI_API_KEY or "none"}
        if settings.OPENAI_BASE_URL:
            kw["base_url"] = settings.OPENAI_BASE_URL
        self.client = OpenAI(**kw)
        self.model = settings.LLM_MODEL or DEFAULT_MODELS["openai"]

    def _msgs(self, prompt, system):
        m = [{"role": "system", "content": system}] if system else []
        return m + [{"role": "user", "content": prompt}]

    def complete(self, prompt, system="", max_tokens=1024, task="generic"):
        r = self.client.chat.completions.create(model=self.model, messages=self._msgs(prompt, system),
                                                max_tokens=max_tokens)
        return r.choices[0].message.content or ""

    def stream(self, prompt, system="", max_tokens=1500, task="generate"):
        s = self.client.chat.completions.create(model=self.model, messages=self._msgs(prompt, system),
                                                max_tokens=max_tokens, stream=True)
        for chunk in s:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# --------------------------------------------------------------------------
# Offline fake model (deterministic heuristics).  NOT intelligent: it exists so
# that the pipeline, the UI and the tests work without any API key.
# --------------------------------------------------------------------------
_STOP = set("the a an of to in on for and or is are was were be by with as at from that this it its what which who how "
            "does do did show me tell about between into than then also can could should would their there these those".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9\u00C0-\u024F]+", text.lower()) if t not in _STOP and len(t) > 2]


class FakeLLM(LLM):
    name = "fake"

    def complete(self, prompt, system="", max_tokens=1024, task="generic"):
        if task == "route":
            q = prompt.split("QUESTION:")[-1].strip().lower()
            image = bool(re.search(r"\b(figure|fig\.|diagram|chart|image|picture|photo|illustration|plot|architecture|schema|screenshot)\b", q))
            multi = bool(re.search(r"\b(compare|comparison|relationship|relate|between|both|improv\w*|versus|vs|and (?:what|which|how)|which .* (?:and|used))\b", q))
            chat = bool(re.fullmatch(r"\s*(hi|hello|hey|thanks|thank you|bonjour|salut|merci)[!. ]*", q))
            kind = "chat" if chat else ("multi_hop" if multi else "factual")
            return json.dumps({"type": kind, "needs_images": image})
        if task == "chat":
            return "Hello! Upload documents to the library and ask me about them. I will answer with citations."
        if task == "rewrite":
            return prompt.split("QUESTION:")[-1].strip()
        if task == "grade":
            return "yes"
        if task == "verify":
            return json.dumps({"ok": True, "issues": []})
        if task == "extract_graph":
            return json.dumps(_fake_extract(prompt.split("TEXT:")[-1]))
        if task == "generate":
            return "".join(self.stream(prompt, system, max_tokens, task))
        return ""

    def stream(self, prompt, system="", max_tokens=1500, task="generate"):
        if task != "generate":
            yield self.complete(prompt, system, max_tokens, task)
            return
        question = prompt.split("QUESTION:")[-1].strip()
        blocks = re.findall(r"^\[(\d+)\][^\n]*\n(.*?)(?=^\[\d+\]|^QUESTION:|\Z)", prompt, flags=re.S | re.M)
        if not blocks:
            yield "[[NOT_IN_SOURCES]]"  # same sentinel as core.agent.NOT_FOUND: the agent decides what to do
            return
        q = Counter(_tokens(question))
        scored = []
        for n, body in blocks:
            for sent in re.split(r"(?<=[.!?])\s+", body.strip()):
                s = sum(q[t] for t in set(_tokens(sent)))
                if s:
                    scored.append((s, int(n), sent.strip()))
        scored.sort(key=lambda x: -x[0])
        if not scored:  # no passage shares a single keyword with the question
            yield "[[NOT_IN_SOURCES]]"
            return
        picked = scored[:3]
        out = "Based on the available sources: " + " ".join(f"{s} [{n}]" for _, n, s in picked)
        for w in out.split(" "):
            yield w + " "


def _fake_extract(text: str) -> dict:
    ents, seen = [], set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+){0,3})\b", text):
        name = m.group(1).strip()
        if len(name) > 3 and name.lower() not in seen and name.lower() not in {"the", "this", "figure", "table"}:
            seen.add(name.lower())
            ents.append({"name": name, "type": "Concept"})
    ents = ents[:8]
    rels = [{"source": ents[i]["name"], "relation": "related_to", "target": ents[i + 1]["name"]}
            for i in range(len(ents) - 1)]
    return {"entities": ents, "relations": rels}


_cached: Optional[LLM] = None


def get_llm() -> LLM:
    global _cached
    if _cached is None:
        p = settings.LLM_PROVIDER.lower()
        if p == "anthropic":
            _cached = AnthropicLLM()
        elif p == "openai":
            _cached = OpenAILLM()
        else:
            _cached = FakeLLM()
    return _cached
