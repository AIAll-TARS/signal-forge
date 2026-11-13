from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(query), ""))


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    def init(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
          authority TEXT, topics TEXT NOT NULL DEFAULT '[]', scan_method TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY, source_id INTEGER REFERENCES sources(id), title TEXT NOT NULL,
          url TEXT NOT NULL, canonical_url TEXT NOT NULL UNIQUE, published_at TEXT,
          content TEXT NOT NULL DEFAULT '', content_hash TEXT NOT NULL UNIQUE,
          topics TEXT NOT NULL DEFAULT '[]', geography TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analyses (
          id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL UNIQUE REFERENCES items(id) ON DELETE CASCADE,
          score INTEGER NOT NULL, priority TEXT NOT NULL, confidence TEXT NOT NULL,
          impact TEXT NOT NULL, why_it_matters TEXT NOT NULL, recommendation TEXT NOT NULL,
          rationale TEXT NOT NULL, analyst TEXT NOT NULL DEFAULT 'deterministic-v1', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_logs (
          id INTEGER PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
          detail TEXT, created_at TEXT NOT NULL
        );
        """)
        self.conn.commit()

    def log(self, command: str, status: str, detail: str = "") -> None:
        self.conn.execute("INSERT INTO run_logs(command,status,detail,created_at) VALUES(?,?,?,?)", (command, status, detail, now()))
        self.conn.commit()

    def add_source(self, source: dict) -> tuple[int, bool]:
        url = canonical_url(source["url"])
        row = self.conn.execute("SELECT id FROM sources WHERE url=?", (url,)).fetchone()
        if row: return int(row["id"]), False
        cur = self.conn.execute("INSERT INTO sources(name,url,authority,topics,scan_method,created_at) VALUES(?,?,?,?,?,?)", (
            source["name"], url, source.get("authority", "unknown"), json_dump(source.get("topics", [])), source.get("scan_method", "rss"), now()))
        self.conn.commit(); return cur.lastrowid, True

    def upsert_source(self, source: dict) -> tuple[int, bool]:
        url = canonical_url(source["url"])
        topics = json_dump(source.get("topics", []))
        active = 1 if source.get("active", True) else 0
        row = self.conn.execute("SELECT id FROM sources WHERE url=?", (url,)).fetchone()
        if row:
            self.conn.execute("UPDATE sources SET name=?, authority=?, topics=?, scan_method=?, active=? WHERE id=?", (
                source["name"], source.get("authority", "unknown"), topics, source.get("scan_method", "rss"), active, row["id"]))
            self.conn.commit(); return int(row["id"]), False
        cur = self.conn.execute("INSERT INTO sources(name,url,authority,topics,scan_method,active,created_at) VALUES(?,?,?,?,?,?,?)", (
            source["name"], url, source.get("authority", "unknown"), topics, source.get("scan_method", "rss"), active, now()))
        self.conn.commit(); return cur.lastrowid, True

    def source_by_url(self, url: str):
        return self.conn.execute("SELECT * FROM sources WHERE url=?", (canonical_url(url),)).fetchone()

    def all_sources(self):
        return self.conn.execute("SELECT * FROM sources ORDER BY id").fetchall()

    def deactivate_except(self, urls: set[str]) -> int:
        changed = 0
        for row in self.all_sources():
            if row["url"] not in urls and row["active"]:
                self.conn.execute("UPDATE sources SET active=0 WHERE id=?", (row["id"],)); changed += 1
        self.conn.commit(); return changed

    def last_log(self, command: str):
        return self.conn.execute("SELECT * FROM run_logs WHERE command=? ORDER BY id DESC LIMIT 1", (command,)).fetchone()

    def sources(self):
        return self.conn.execute("SELECT * FROM sources WHERE active=1 ORDER BY id").fetchall()

    def source(self, source_id: int):
        return self.conn.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()

    def add_item(self, item: dict) -> tuple[int, bool]:
        content = item.get("content", "")
        url = canonical_url(item["url"])
        digest = content_hash(content or item.get("title", ""))
        found = self.conn.execute("SELECT id FROM items WHERE canonical_url=? OR content_hash=?", (url, digest)).fetchone()
        if found: return int(found["id"]), False
        cur = self.conn.execute("""INSERT INTO items(source_id,title,url,canonical_url,published_at,content,content_hash,topics,geography,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?)""", (item.get("source_id"), item.get("title") or url, item["url"], url,
          item.get("published_at"), content, digest, json_dump(item.get("topics", [])), item.get("geography"), now()))
        self.conn.commit(); return cur.lastrowid, True

    def items(self, date: str | None = None, query: str | None = None):
        sql = "SELECT i.*, s.name AS source_name, s.authority, a.score,a.priority,a.confidence,a.impact,a.why_it_matters,a.recommendation,a.rationale FROM items i LEFT JOIN sources s ON s.id=i.source_id LEFT JOIN analyses a ON a.item_id=i.id"
        clauses, params = [], []
        if date: clauses.append("substr(i.created_at,1,10)=?"); params.append(date)
        if query: clauses.append("(i.title LIKE ? OR i.content LIKE ? OR i.topics LIKE ?)"); params += [f"%{query}%"] * 3
        if clauses: sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY COALESCE(a.score,0) DESC, i.created_at DESC"
        return self.conn.execute(sql, params).fetchall()

    def unanalysed(self, item_id: int | None = None):
        sql = "SELECT i.*, s.authority, s.name AS source_name FROM items i LEFT JOIN sources s ON s.id=i.source_id LEFT JOIN analyses a ON a.item_id=i.id WHERE a.id IS NULL"
        params = []
        if item_id: sql += " AND i.id=?"; params.append(item_id)
        return self.conn.execute(sql, params).fetchall()

    def save_analysis(self, item_id: int, result: dict) -> None:
        self.conn.execute("""INSERT INTO analyses(item_id,score,priority,confidence,impact,why_it_matters,recommendation,rationale,analyst,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET score=excluded.score,priority=excluded.priority,confidence=excluded.confidence,impact=excluded.impact,why_it_matters=excluded.why_it_matters,recommendation=excluded.recommendation,rationale=excluded.rationale,created_at=excluded.created_at""",
        (item_id, result["score"], result["priority"], result["confidence"], result["impact"], result["why_it_matters"], result["recommendation"], result["rationale"], result.get("analyst", "deterministic-v1"), now()))
        self.conn.commit()


def json_dump(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
