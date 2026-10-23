import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("CLIP_MODE", "off")
os.environ.setdefault("WEB_PROVIDER", "none")
