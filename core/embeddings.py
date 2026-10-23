"""Text embedding providers. All return L2-normalised float32 matrices."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

import numpy as np

from .config import settings

log = logging.getLogger("core.embeddings")

_STOPWORDS = set("the a an of to in on for and or is are was were be by with as at from that this it its what which who how "
                 "does do did me tell about between into than then also can could should would their there these those "
                 "has have had not but if so such very more most".split())


class Embedder:
    name = "base"
    dim = 0
    relevance_floor = 0.25  # cosine score under which a passage is treated as irrelevant

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class HashEmbedder(Embedder):
    """Offline lexical embedder (feature hashing of words + char trigrams).
    Good enough for tests and demos; use sentence-transformers for real quality."""
    name = "hash"
    dim = 768
    relevance_floor = 0.2

    def embed(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            words = [w for w in re.findall(r"[a-z0-9\u00c0-\u024f]+", t.lower())
                     if w not in _STOPWORDS and len(w) > 1]
            stems = [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words]
            for f in stems:
                h = int(hashlib.md5(f.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0
            for w in stems:  # light sub-word signal for morphological variants
                for j in range(len(w) - 3):
                    h = int(hashlib.md5(("#" + w[j:j + 4]).encode()).hexdigest()[:8], 16)
                    out[i, h % self.dim] += 0.25
        n = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(n, 1e-9)


class SentenceTransformerEmbedder(Embedder):
    name = "sentence-transformers"
    relevance_floor = 0.25

    def __init__(self, model: str) -> None:
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts):
        v = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False,
                              convert_to_numpy=True)
        return v.astype(np.float32)


class OpenAIEmbedder(Embedder):
    name = "openai"
    relevance_floor = 0.3

    def __init__(self) -> None:
        from openai import OpenAI
        kw = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            kw["base_url"] = settings.OPENAI_BASE_URL
        self.client = OpenAI(**kw)
        self.model = settings.EMBEDDING_MODEL if "/" not in settings.EMBEDDING_MODEL else "text-embedding-3-small"
        self.dim = len(self.embed(["probe"])[0])

    def embed(self, texts):
        out = []
        for i in range(0, len(texts), 96):
            r = self.client.embeddings.create(model=self.model, input=texts[i:i + 96])
            out.extend(d.embedding for d in r.data)
        v = np.array(out, dtype=np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


_cached: Optional[Embedder] = None


def get_embedder() -> Embedder:
    global _cached
    if _cached is not None:
        return _cached
    p = settings.EMBEDDING_PROVIDER.lower()
    emb: Optional[Embedder] = None
    if p in ("auto", "sentence-transformers"):
        try:
            emb = SentenceTransformerEmbedder(settings.EMBEDDING_MODEL)
        except Exception as e:  # noqa: BLE001
            if p != "auto":
                raise
            log.warning("sentence-transformers unavailable (%s); using the offline hash embedder. "
                        "Install requirements-ml.txt for real semantic search.", e)
    elif p == "openai":
        emb = OpenAIEmbedder()
    _cached = emb or HashEmbedder()
    return _cached
