"""Historial de chats en PostgreSQL: una fila por conversación (`chats`) y una por mensaje (`chat_messages`).

Cada mensaje guarda en columnas lo que se consulta (rol, texto, modelo, error) y en `extra` (jsonb) lo que es estructura
anidada: las fuentes citadas, el examen y el mapa mental. Comparte esquema con el índice, así que sigue a la carpeta de datos.
"""
import time

from psycopg.types.json import Jsonb

from . import config
from .store import _ensure_schema, _pool, _schema_for, _scrub

_EXTRA = ("sources", "quiz", "map", "zone")


class ChatStore:
    def __init__(self):
        self.schema = _schema_for(config.DATA_DIR)
        _ensure_schema(self.schema)

    def summaries(self) -> list[dict]:
        """Resumen de cada chat, el más reciente primero."""
        with _pool().connection() as conn:
            rows = conn.execute(
                f"SELECT c.id, c.title, c.updated, (SELECT count(*) FROM {self.schema}.chat_messages m WHERE m.chat_id = c.id), c.doc "
                f"FROM {self.schema}.chats c ORDER BY c.updated DESC, c.id").fetchall()
        return [{"id": i, "title": t, "updated": u, "count": n, "doc": d} for i, t, u, n, d in rows]

    def get(self, chat_id: str) -> dict | None:
        with _pool().connection() as conn:
            head = conn.execute(f"SELECT id, title, created, updated, doc FROM {self.schema}.chats WHERE id = %s", (chat_id,)).fetchone()
            if head is None:
                return None
            rows = conn.execute(
                f"SELECT role, content, model, error, extra FROM {self.schema}.chat_messages WHERE chat_id = %s ORDER BY pos", (chat_id,)).fetchall()
        messages = []
        for role, content, model, error, extra in rows:
            m = {"role": role, "content": content, "model": model, "error": error, **extra}
            messages.append({k: v for k, v in m.items() if v not in (None, "")})
        return {"id": head[0], "title": head[1], "created": head[2], "updated": head[3], "doc": head[4], "messages": messages}

    def exists(self, chat_id: str) -> bool:
        with _pool().connection() as conn:
            return conn.execute(f"SELECT EXISTS (SELECT 1 FROM {self.schema}.chats WHERE id = %s)", (chat_id,)).fetchone()[0]

    def save(self, chat_id: str, title: str, messages: list[dict], created: float | None = None, updated: float | None = None, doc: str | None = None) -> dict:
        """Crea o reemplaza el chat entero en una transacción: un corte a medias no deja un chat roto."""
        now = updated or time.time()
        S = self.schema
        with _pool().connection() as conn:
            conn.execute(
                f"INSERT INTO {S}.chats (id, title, created, updated, doc) VALUES (%s, %s, %s, %s, %s) "
                f"ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, updated = EXCLUDED.updated, doc = COALESCE({S}.chats.doc, EXCLUDED.doc)",
                (chat_id, title, created or now, now, doc))
            conn.execute(f"DELETE FROM {S}.chat_messages WHERE chat_id = %s", (chat_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {S}.chat_messages (chat_id, pos, role, content, model, error, extra) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    [(chat_id, i, m["role"], _scrub(m.get("content")) or None, _scrub(m.get("model")), _scrub(m.get("error")),
                      Jsonb(_scrub({k: m[k] for k in _EXTRA if m.get(k) not in (None, "")}))) for i, m in enumerate(messages)])
            created, doc = conn.execute(f"SELECT created, doc FROM {S}.chats WHERE id = %s", (chat_id,)).fetchone()
        return {"id": chat_id, "title": title, "created": created, "updated": now, "doc": doc, "messages": messages}

    def delete(self, chat_id: str) -> bool:
        with _pool().connection() as conn:
            return conn.execute(f"DELETE FROM {self.schema}.chats WHERE id = %s", (chat_id,)).rowcount > 0  # sus mensajes caen en cascada
