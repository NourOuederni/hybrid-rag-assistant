"""SQLite persistence for documents, conversations and messages (B2.2, B3)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from core.config import settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, size INTEGER, sha256 TEXT, path TEXT,
  status TEXT NOT NULL, pages INTEGER DEFAULT 0, chunks INTEGER DEFAULT 0, images INTEGER DEFAULT 0,
  entities INTEGER DEFAULT 0, errors TEXT DEFAULT '[]', uploaded_at TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
  citations TEXT DEFAULT '[]', sources TEXT DEFAULT '[]', route TEXT DEFAULT '[]', images TEXT DEFAULT '[]',
  used_web INTEGER DEFAULT 0, created_at TEXT,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(settings.db_path, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        with _lock:
            yield c
            c.commit()
    finally:
        c.close()


def init_db() -> None:
    settings.ensure_dirs()
    with conn() as c:
        c.executescript(SCHEMA)


def _doc(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["errors"] = json.loads(d.get("errors") or "[]")
    d.pop("path", None)
    return d


# ------------------------------------------------------------------ documents
def create_document(name: str, size: int, sha: str, path: str) -> dict:
    did = new_id()
    with conn() as c:
        c.execute("INSERT INTO documents(id,name,size,sha256,path,status,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                  (did, name, size, sha, path, "uploaded", now()))
    return get_document(did)  # type: ignore[return-value]


def get_document(did: str, with_path: bool = False) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone()
    if not r:
        return None
    d = _doc(r)
    if with_path:
        d["path"] = r["path"]
    return d


def find_document_by_hash(sha: str) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT * FROM documents WHERE sha256=?", (sha,)).fetchone()
    return _doc(r) if r else None


def list_documents() -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
    return [_doc(r) for r in rows]


def pending_documents() -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM documents WHERE status IN ('uploaded','processing')").fetchall()
    return [{**_doc(r), "path": r["path"]} for r in rows]


def update_document(did: str, **fields: Any) -> None:
    if "errors" in fields:
        fields["errors"] = json.dumps(fields["errors"])
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE documents SET {cols} WHERE id=?", (*fields.values(), did))


def delete_document(did: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM documents WHERE id=?", (did,))


# -------------------------------------------------------------- conversations
def create_conversation(title: str = "New chat") -> dict:
    cid = new_id()
    with conn() as c:
        c.execute("INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                  (cid, title, now(), now()))
    return get_conversation(cid)  # type: ignore[return-value]


def get_conversation(cid: str) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        last = c.execute("SELECT text FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1",
                         (cid,)).fetchone()
    d = dict(r)
    d["preview"] = (last["text"][:90] if last else "")
    return d


def list_conversations(q: str = "") -> list[dict]:
    with conn() as c:
        if q:
            rows = c.execute(
                "SELECT DISTINCT c.id FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id "
                "WHERE c.title LIKE ? OR m.text LIKE ? ORDER BY c.updated_at DESC", (f"%{q}%", f"%{q}%")).fetchall()
        else:
            rows = c.execute("SELECT id FROM conversations ORDER BY updated_at DESC").fetchall()
    return [get_conversation(r["id"]) for r in rows]  # type: ignore[misc]


def rename_conversation(cid: str, title: str) -> None:
    with conn() as c:
        c.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?", (title, now(), cid))


def delete_conversation(cid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM conversations WHERE id=?", (cid,))


def add_message(cid: str, role: str, text: str, citations=None, sources=None, route=None,
                images=None, used_web: bool = False) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO messages(conversation_id,role,text,citations,sources,route,images,used_web,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, role, text, json.dumps(citations or []), json.dumps(sources or []), json.dumps(route or []),
             json.dumps(images or []), int(used_web), now()))
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), cid))
        return cur.lastrowid  # type: ignore[return-value]


def list_messages(cid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("citations", "sources", "route", "images"):
            d[k] = json.loads(d[k] or "[]")
        d["used_web"] = bool(d["used_web"])
        out.append(d)
    return out
