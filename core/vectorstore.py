"""Small persistent cosine-similarity vector store (numpy + JSON).

Plenty for a corpus of a few hundred documents.  The class is the only thing the rest of the
code touches, so it can be swapped for Chroma/Qdrant/FAISS without changing other modules.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np


class VectorStore:
    def __init__(self, directory: Path, name: str) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.vec_path = self.dir / f"{name}.npy"
        self.meta_path = self.dir / f"{name}.json"
        self.lock = threading.RLock()
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.meta: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.vec_path.exists() and self.meta_path.exists():
            self.vectors = np.load(self.vec_path)
            self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        np.save(self.vec_path, self.vectors)
        self.meta_path.write_text(json.dumps(self.meta), encoding="utf-8")

    def __len__(self) -> int:
        return len(self.meta)

    def add(self, vectors: np.ndarray, metas: list[dict]) -> None:
        if len(metas) == 0:
            return
        with self.lock:
            if self.vectors.size == 0:
                self.vectors = vectors.astype(np.float32)
            else:
                self.vectors = np.vstack([self.vectors, vectors.astype(np.float32)])
            self.meta.extend(metas)
            self._save()

    def search(self, qvec: np.ndarray, k: int = 5,
               where: Optional[Callable[[dict], bool]] = None) -> list[tuple[float, dict]]:
        with self.lock:
            if not self.meta:
                return []
            sims = self.vectors @ qvec.astype(np.float32)
            order = np.argsort(-sims)
            out = []
            for i in order:
                m = self.meta[int(i)]
                if where and not where(m):
                    continue
                out.append((float(sims[i]), m))
                if len(out) >= k:
                    break
            return out

    def delete_where(self, pred: Callable[[dict], bool]) -> int:
        with self.lock:
            keep = [i for i, m in enumerate(self.meta) if not pred(m)]
            removed = len(self.meta) - len(keep)
            if removed:
                self.vectors = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
                self.meta = [self.meta[i] for i in keep]
                self._save()
            return removed

    def metas(self) -> list[dict]:
        with self.lock:
            return list(self.meta)
