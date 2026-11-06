import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force un environnement 100 % hors ligne, quel que soit le .env ou le terminal
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["CLIP_MODE"] = "off"
os.environ["WEB_PROVIDER"] = "none"
os.environ["GRAPH_EXTRACTION"] = "true"
os.environ["MIN_LOCAL_SCORE"] = ""