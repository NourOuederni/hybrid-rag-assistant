"""Backend tests against the Mock Core (B1-B4) - no AI needed."""
import importlib
import io
import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLE = Path(__file__).resolve().parent.parent / "contracts" / "sample_data"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DATA_DIR", tempfile.mkdtemp())
    monkeypatch.setenv("USE_MOCK_CORE", "1")
    import core.config as cfg
    importlib.reload(cfg)
    import backend.db, backend.main
    importlib.reload(backend.db)
    importlib.reload(backend.main)
    with TestClient(backend.main.app) as c:
        yield c


def pdf_bytes():
    return next(SAMPLE.glob("*.pdf")).read_bytes()


def test_upload_list_delete_and_duplicate(client):
    r = client.post("/api/documents", files={"file": ("a.pdf", pdf_bytes(), "application/pdf")})
    assert r.status_code == 201
    did = r.json()["id"]
    assert client.post("/api/documents", files={"file": ("b.pdf", pdf_bytes(), "application/pdf")}).status_code == 409
    import time
    for _ in range(30):
        if client.get(f"/api/documents/{did}").json()["status"] == "ready":
            break
        time.sleep(0.2)
    assert client.get(f"/api/documents/{did}").json()["status"] == "ready"
    assert client.get(f"/api/documents/{did}/file").status_code == 200
    assert len(client.get("/api/documents").json()) == 1
    assert client.delete(f"/api/documents/{did}").status_code == 204
    assert client.get("/api/documents").json() == []


def test_rejects_non_pdf(client):
    assert client.post("/api/documents", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/documents", files={"file": ("a.pdf", b"not a pdf", "application/pdf")}).status_code == 415


def test_conversation_and_streaming_chat(client):
    cid = client.post("/api/conversations").json()["id"]
    with client.stream("POST", f"/api/conversations/{cid}/chat", json={"question": "hi there"}) as r:
        body = "".join(r.iter_text())
    assert "event: token" in body and "event: final" in body
    conv = client.get(f"/api/conversations/{cid}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["title"] == "hi there"
    assert client.patch(f"/api/conversations/{cid}", json={"title": "Renamed"}).json()["title"] == "Renamed"
    assert client.get("/api/conversations", params={"q": "mock"}).json()[0]["id"] == cid
    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_image_route_blocks_traversal(client):
    assert client.get("/api/images/..%2F..%2Fapp.db").status_code == 404
