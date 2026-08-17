"""새 기사 중복 수집을 막기 위한 SQLite 기반 seen-store."""

import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seen.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_utc TEXT NOT NULL
);
"""


def make_id(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


class SeenStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def is_new(self, url: str) -> bool:
        item_id = make_id(url)
        cur = self.conn.execute(
            "SELECT 1 FROM seen_items WHERE id = ?", (item_id,)
        )
        return cur.fetchone() is None

    def mark_seen(self, url: str, source: str, title: str, first_seen_utc: str):
        item_id = make_id(url)
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_items (id, source, title, url, first_seen_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (item_id, source, title, url, first_seen_utc),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
