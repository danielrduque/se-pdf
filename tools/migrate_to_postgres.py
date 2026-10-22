"""Pasa los datos de la versión con archivos a PostgreSQL: el índice (vectors.npy + meta.json + index_info.json,
conservando los ids de los fragmentos) y los chats (data/chats/*.json).

Uso:  python tools/migrate_to_postgres.py [carpeta_de_datos]     (por defecto, data/)
Es segura de repetir: lo que ya está en la base no se toca (--force reemplaza el índice). Los archivos viejos se
conservan como respaldo; los originales de los documentos y los ajustes se quedan en la carpeta de datos, como antes.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chatpdf import config, store as st
from chatpdf.chats import ChatStore

args = [a for a in sys.argv[1:] if not a.startswith("--")]
force = "--force" in sys.argv
config.load_settings()
config.DATA_DIR = Path(args[0]).resolve() if args else config.DATA_DIR
data = config.DATA_DIR
store = st.VectorStore()
S = store.schema


def migrate_index():
    vec_path, meta_path, info_path = data / "vectors.npy", data / "meta.json", data / "index_info.json"
    if not (vec_path.exists() and meta_path.exists()):
        return print("índice: no hay archivos viejos que pasar")
    vectors = st.VectorStore._norm(np.load(vec_path).astype(np.float32))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {"docs": {}}
    assert len(vectors) == len(meta), "vectors.npy y meta.json no coinciden"
    with st._pool().connection() as conn:
        if conn.execute(f"SELECT EXISTS (SELECT 1 FROM {S}.documents)").fetchone()[0]:
            if not force:
                return print(f"índice: el esquema `{S}` ya tiene datos; se deja como está (--force para reemplazarlos)")
            conn.execute(f"TRUNCATE {S}.chunks, {S}.documents, {S}.index_meta RESTART IDENTITY")
        now = time.time()
        for name in dict.fromkeys(m["doc"] for m in meta):
            d = info["docs"].get(name, {})
            conn.execute(f"INSERT INTO {S}.documents VALUES (%s, %s, %s, %s)", (name, d.get("hash", ""), d.get("origin", "upload"), d.get("added", now)))
        order: dict[str, int] = {}
        rows = []
        for i, (m, v) in enumerate(zip(meta, vectors)):
            o = order[m["doc"]] = order.get(m["doc"], -1) + 1
            extra = {k: x for k, x in m.items() if k not in ("kind", "loc", "text", "doc")}
            text = st._clean(m["text"])
            rows.append((i, m["doc"], o, m.get("kind", ""), m.get("loc", ""), text, Jsonb(extra), " ".join(st._terms(text)), st._vec(v)))
        with conn.cursor() as cur:
            cur.executemany(f"INSERT INTO {S}.chunks (id, doc, ord, kind, loc, text, extra, tokens, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)", rows)
        conn.execute(f"SELECT setval(pg_get_serial_sequence('{S}.chunks', 'id'), %s)", (len(meta),))
        model = info.get("embed_model") or config.EMBED["model"].split(",")[0].strip()
        for k, v in (("dim", str(vectors.shape[1])), ("embed_model", model)):
            conn.execute(f"INSERT INTO {S}.index_meta VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (k, v))
    print(f"índice: {len(meta)} fragmentos de {len(set(m['doc'] for m in meta))} documentos -> esquema `{S}` ({vectors.shape[1]} dimensiones, modelo {model})")


def migrate_chats():
    chats, done, skipped = ChatStore(), 0, []
    for f in sorted((data / "chats").glob("*.json")):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if chats.exists(c["id"]):
                continue
            chats.save(c["id"], c["title"], c["messages"], created=c["created"], updated=c["updated"])
            done += 1
        except (OSError, ValueError, KeyError):
            skipped.append(f.name)  # un archivo dañado no debe frenar a los demás
    print(f"chats: {done} migrados, {len(chats.summaries())} en total" + (f", {len(skipped)} dañados sin migrar: {skipped}" if skipped else ""))


def backfill_chat_docs():
    """Los chats de antes no sabían de qué documento trataban: si todas sus fuentes son de uno solo, se le asigna."""
    chats, fixed = ChatStore(), 0
    with st._pool().connection() as conn:
        for c in chats.summaries():
            if c["doc"]:
                continue
            docs = {s["doc"] for m in chats.get(c["id"])["messages"] for s in m.get("sources", []) if isinstance(s, dict) and s.get("doc")}
            if len(docs) == 1:
                conn.execute(f"UPDATE {S}.chats SET doc = %s WHERE id = %s", (docs.pop(), c["id"]))
                fixed += 1
    print(f"chats: {fixed} asociados a su documento")


migrate_index()
migrate_chats()
backfill_chat_docs()
