"""All configuration comes from environment variables (see .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # storage
    DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data")).resolve()
    # LLM:  anthropic | openai | fake
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake")
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    # embeddings: auto | sentence-transformers | openai | hash
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "auto")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    # CLIP: auto | on | off
    CLIP_MODE = os.getenv("CLIP_MODE", "auto")
    CLIP_MODEL = os.getenv("CLIP_MODEL", "clip-ViT-B-32")
    # chunking (A1.1)
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
    MIN_IMAGE_PX = int(os.getenv("MIN_IMAGE_PX", "120"))
    # retrieval
    TOP_K = int(os.getenv("TOP_K", "5"))
    GRAPH_HOPS = int(os.getenv("GRAPH_HOPS", "1"))
    GRAPH_EXTRACTION = _bool("GRAPH_EXTRACTION", True)
    # agent
    MAX_VERIFY_LOOPS = int(os.getenv("MAX_VERIFY_LOOPS", "1"))
    MIN_LOCAL_SCORE = float(os.environ["MIN_LOCAL_SCORE"]) if os.getenv("MIN_LOCAL_SCORE") else None  # None = embedder default
    # web search: tavily | ddgs | none
    WEB_PROVIDER = os.getenv("WEB_PROVIDER", "tavily")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    WEB_MAX_RESULTS = int(os.getenv("WEB_MAX_RESULTS", "4"))
    WEB_BLOCKED_DOMAINS = [d for d in os.getenv("WEB_BLOCKED_DOMAINS", "").split(",") if d]
    # backend
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
    USE_MOCK_CORE = _bool("USE_MOCK_CORE", False)
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    @property
    def uploads_dir(self) -> Path:
        return self.DATA_DIR / "uploads"

    @property
    def images_dir(self) -> Path:
        return self.DATA_DIR / "images"

    @property
    def index_dir(self) -> Path:
        return self.DATA_DIR / "index"

    @property
    def db_path(self) -> Path:
        return self.DATA_DIR / "app.db"

    def ensure_dirs(self) -> None:
        for p in (self.DATA_DIR, self.uploads_dir, self.images_dir, self.index_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
