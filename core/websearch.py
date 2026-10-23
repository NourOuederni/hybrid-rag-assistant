"""A5 - web search tool returning SourceRecords with full source metadata."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from contracts.schemas import SourceRecord

from .config import settings

log = logging.getLogger("core.web")


def web_enabled() -> bool:
    p = settings.WEB_PROVIDER.lower()
    if p == "tavily":
        return bool(settings.TAVILY_API_KEY)
    return p == "ddgs"


def _blocked(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in settings.WEB_BLOCKED_DOMAINS)


def web_search(query: str, max_results: int | None = None) -> tuple[list[SourceRecord], str | None]:
    """Returns (results, error). Never raises: a failure gives ([], 'message')."""
    n = max_results or settings.WEB_MAX_RESULTS
    provider = settings.WEB_PROVIDER.lower()
    if not web_enabled():
        return [], "web search is not configured (set WEB_PROVIDER and TAVILY_API_KEY)"
    err = None
    for attempt in range(2):  # A5.2 retry
        try:
            raw = _tavily(query, n + 3) if provider == "tavily" else _ddgs(query, n + 3)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            out = []
            for i, r in enumerate(raw):
                if not r["url"] or _blocked(r["url"]):
                    continue
                out.append(SourceRecord(id=f"web:{abs(hash(r['url'])) % 10**8}", source_type="web", url=r["url"],
                                        title=r["title"] or r["url"], snippet=r["content"][:1200],
                                        score=float(r.get("score") or 0.5), retrieved_at=now))
                if len(out) >= n:
                    break
            return out, None
        except Exception as e:  # noqa: BLE001
            err = str(e)
            log.warning("web search attempt %d failed: %s", attempt + 1, e)
            time.sleep(0.6)
    return [], err


def _tavily(query: str, n: int) -> list[dict]:
    r = httpx.post("https://api.tavily.com/search", timeout=15,
                   headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
                   json={"query": query, "max_results": n, "search_depth": "basic"})
    r.raise_for_status()
    return [{"url": x.get("url"), "title": x.get("title"), "content": x.get("content", ""),
             "score": x.get("score")} for x in r.json().get("results", [])]


def _ddgs(query: str, n: int) -> list[dict]:
    from ddgs import DDGS
    return [{"url": x.get("href"), "title": x.get("title"), "content": x.get("body", ""), "score": 0.5}
            for x in DDGS().text(query, max_results=n)]
