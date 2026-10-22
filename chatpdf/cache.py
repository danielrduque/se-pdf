"""Caché en disco (SQLite) de los análisis lentos: descripciones de visión y transcripciones de audio."""
import json
import sqlite3
from contextlib import closing

from . import config


def _conn() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DATA_DIR / "cache.db")
    c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
    return c


def get(key: str):
    with closing(_conn()) as c:
        row = c.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def put(key: str, value) -> None:
    with closing(_conn()) as c, c:
        c.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
