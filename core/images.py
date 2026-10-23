"""A4 - image index. Uses CLIP (sentence-transformers) when available, otherwise falls back to
caption/page-context text search so the feature never breaks."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from contracts.schemas import SourceRecord

from .config import settings
from .embeddings import Embedder
from .ingestion import ImageItem
from .vectorstore import VectorStore

log = logging.getLogger("core.images")


class ImageIndex:
    def __init__(self, text_embedder: Embedder) -> None:
        self.text_embedder = text_embedder
        self.clip = None
        if settings.CLIP_MODE in ("auto", "on"):
            try:
                from sentence_transformers import SentenceTransformer
                self.clip = SentenceTransformer(settings.CLIP_MODEL)
            except Exception as e:  # noqa: BLE001
                if settings.CLIP_MODE == "on":
                    raise
                log.warning("CLIP unavailable (%s); image search falls back to captions.", e)
        self.mode = "clip" if self.clip else "caption"
        self.store = VectorStore(settings.index_dir, f"images_{self.mode}")

    # -------------------------------------------------------------- indexing
    def add_images(self, items: list[ImageItem]) -> int:
        if not items:
            return 0
        if self.clip:
            from PIL import Image
            imgs = [Image.open(i.path).convert("RGB") for i in items]
            vecs = self.clip.encode(imgs, normalize_embeddings=True, convert_to_numpy=True,
                                    show_progress_bar=False)
        else:
            vecs = self.text_embedder.embed([i.context_text or i.figure_label for i in items])
        self.store.add(vecs, [i.__dict__.copy() for i in items])
        return len(items)

    # ---------------------------------------------------------------- search
    def _rec(self, m: dict, score: float) -> SourceRecord:
        try:
            rel = str(Path(m["path"]).relative_to(settings.images_dir))
        except ValueError:
            rel = Path(m["path"]).name
        return SourceRecord(id=m["id"], source_type="image", doc_id=m["doc_id"], file_name=m["file_name"],
                            page=m["page"], figure_label=m["figure_label"], image_path=rel,
                            snippet=m.get("caption") or m["figure_label"], score=round(score, 4))

    def search_text(self, query: str, k: int = 3) -> list[SourceRecord]:
        if len(self.store) == 0:
            return []
        qv = (self.clip.encode([query], normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=False)[0] if self.clip
              else self.text_embedder.embed([query])[0])
        return [self._rec(m, s) for s, m in self.store.search(qv, k)]

    def search_image(self, image_path: str, k: int = 3) -> list[SourceRecord]:
        """Image-to-image search (A4.2). Requires CLIP."""
        if not self.clip:
            raise RuntimeError("Image-to-image search needs CLIP (install requirements-ml.txt).")
        from PIL import Image
        qv = self.clip.encode([Image.open(image_path).convert("RGB")], normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=False)[0]
        return [self._rec(m, s) for s, m in self.store.search(qv, k)]

    def delete_by_doc_id(self, doc_id: str) -> int:
        return self.store.delete_where(lambda m: m["doc_id"] == doc_id)
