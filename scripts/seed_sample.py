"""B11.4 - upload the sample PDFs through the running server's API (demo seed).
Usage: python scripts/seed_sample.py [http://localhost:8000]"""
import sys
from pathlib import Path

import httpx

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
for f in sorted((Path(__file__).resolve().parent.parent / "contracts" / "sample_data").glob("*.pdf")):
    r = httpx.post(f"{base}/api/documents", files={"file": (f.name, f.read_bytes(), "application/pdf")}, timeout=60)
    print(f.name, r.status_code, r.json().get("id") or r.json().get("error", {}).get("message"))
