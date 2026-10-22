import hashlib
import re
import shutil
import threading
import time
import unicodedata
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool, PoolTimeout

from . import config

_WORD = re.compile(r"\w+", re.UNICODE)
_TERM = re.compile(r"[^\W_]+", re.UNICODE)
RRF_K = 60  # constante estándar de Reciprocal Rank Fusion
_COLS = "id, doc, kind, loc, text, extra"
DB_HINT = "Arranca la base de datos con `docker compose up -d db` (ver README)."


def tokenize(text: str) -> list[str]:
    """Minúsculas y sin tildes, para que 'Bogotá' y 'bogota' coincidan."""
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [w for w in _WORD.findall(t) if len(w) > 1 or w.isdigit()]


def _terms(text: str) -> list[str]:
    """Palabras para la búsqueda de texto de PostgreSQL: las de tokenize() partidas por '_' (que PostgreSQL no trata como letra)."""
    return [t for w in tokenize(text) for t in _TERM.findall(w)]


def _clean(text: str) -> str:
    return text.replace("\x00", "")  # PostgreSQL no admite NUL en el texto y algunos PDFs lo traen


def _scrub(obj):
    """_clean() aplicado a todos los textos de una estructura anidada (jsonb tampoco admite NUL)."""
    if isinstance(obj, str):
        return _clean(obj)
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    return obj


def _vec(v) -> str:
    return "[" + ",".join(map(str, np.asarray(v, dtype=np.float32).tolist())) + "]"


# ---------- conexión ----------

_pools: dict[str, ConnectionPool] = {}
_ready: set[tuple[str, str]] = set()
_pool_lock = threading.Lock()


def _pool() -> ConnectionPool:
    with _pool_lock:
        url = config.DB_URL
        if url not in _pools:
            p = ConnectionPool(url, min_size=1, max_size=8, open=False, kwargs={"connect_timeout": 5}, check=ConnectionPool.check_connection)  # descarta conexiones rotas (p. ej. tras reiniciar la base)
            try:
                p.open(wait=True, timeout=8)
            except PoolTimeout:
                p.close()
                raise RuntimeError(f"No hay una base de datos PostgreSQL respondiendo. {DB_HINT}") from None
            _pools[url] = p
        return _pools[url]


def db_problem() -> str | None:
    """Mensaje si no se puede usar la base de datos (None si todo está listo)."""
    try:
        with _pool().connection() as conn:
            conn.execute("SELECT 1")
        return None
    except Exception as e:
        return str(e) if isinstance(e, RuntimeError) else f"No se pudo conectar a PostgreSQL ({type(e).__name__}). {DB_HINT}"


def _schema_for(data_dir: Path) -> str:
    """Cada carpeta de datos tiene su propio esquema: el real es `chatdd`; las pruebas y qa_check usan el suyo y no se pisan."""
    if Path(data_dir).resolve() == (config.ROOT / "data").resolve():
        return "chatdd"
    return "d_" + hashlib.sha1(str(Path(data_dir).resolve()).encode()).hexdigest()[:12]


def _ensure_schema(schema: str):
    key = (config.DB_URL, schema)
    if key in _ready:
        return
    with _pool().connection() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {schema}.documents (
            name   text PRIMARY KEY,
            hash   text NOT NULL DEFAULT '',
            origin text NOT NULL DEFAULT 'upload',
            added  double precision NOT NULL)""")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {schema}.chunks (
            id        bigserial PRIMARY KEY,
            doc       text NOT NULL REFERENCES {schema}.documents(name) ON DELETE CASCADE,
            ord       integer NOT NULL,
            kind      text NOT NULL,
            loc       text NOT NULL,
            text      text NOT NULL,
            extra     jsonb NOT NULL DEFAULT '{{}}',
            tokens    text NOT NULL,
            embedding vector NOT NULL,
            tsv       tsvector GENERATED ALWAYS AS (to_tsvector('simple', tokens)) STORED)""")
        conn.execute(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS suggestions jsonb")  # preguntas sugeridas, se generan al abrir el documento
        conn.execute(f"ALTER TABLE {schema}.chunks ADD COLUMN IF NOT EXISTS embedding_mm vector")  # vector sacado directamente de la imagen o el audio (NULL en el texto)
        conn.execute(f"CREATE INDEX IF NOT EXISTS chunks_doc_idx ON {schema}.chunks (doc, ord)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON {schema}.chunks USING gin (tsv)")
        conn.execute(f"CREATE TABLE IF NOT EXISTS {schema}.index_meta (key text PRIMARY KEY, value text NOT NULL)")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {schema}.chats (
            id      text PRIMARY KEY,
            title   text NOT NULL,
            created double precision NOT NULL,
            updated double precision NOT NULL)""")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {schema}.chat_messages (
            chat_id text NOT NULL REFERENCES {schema}.chats(id) ON DELETE CASCADE,
            pos     integer NOT NULL,
            role    text NOT NULL CHECK (role IN ('user', 'assistant')),
            content text,
            model   text,
            error   text,
            extra   jsonb NOT NULL DEFAULT '{{}}',
            PRIMARY KEY (chat_id, pos))""")
        conn.execute(f"ALTER TABLE {schema}.chats ADD COLUMN IF NOT EXISTS doc text")  # documento sobre el que trata el chat
        conn.execute(f"CREATE INDEX IF NOT EXISTS chats_updated_idx ON {schema}.chats (updated DESC)")
    _ready.add(key)


def drop_schema(schema: str):
    with _pool().connection() as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    _ready.discard((config.DB_URL, schema))


class VectorStore:
    """Índice en PostgreSQL + pgvector. Vectores normalizados y búsqueda por coseno (`<=>`); el texto exacto
    (nombres, códigos, cifras) lo busca el índice de texto completo (tsvector) y ambos rankings se fusionan con RRF."""

    def __init__(self):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.files_dir = config.DATA_DIR / "files"  # copias de los originales (para mostrar la página o el minuto citado)
        self.schema = _schema_for(config.DATA_DIR)
        self._lock = threading.RLock()  # el servidor web atiende preguntas mientras otro hilo indexa
        _ensure_schema(self.schema)

    def _conn(self):
        return _pool().connection()

    # ---------- coherencia del índice ----------

    @staticmethod
    def _model() -> str:
        return config.EMBED["model"].split(",")[0].strip()

    def _check(self, conn, dim: int):
        """Falla si el índice no es compatible con el modelo actual. Dos modelos pueden dar vectores del mismo tamaño (768)
        pero de espacios distintos, por eso se guarda también el nombre del modelo."""
        S = self.schema
        if not conn.execute(f"SELECT EXISTS (SELECT 1 FROM {S}.chunks)").fetchone()[0]:
            return
        meta = dict(conn.execute(f"SELECT key, value FROM {S}.index_meta").fetchall())
        if int(meta.get("dim", dim)) != dim:
            raise ValueError(
                f"Los embeddings del índice tienen {meta['dim']} dimensiones y el modelo actual produce {dim}. "
                "Cambiaste de modelo de embeddings: borra los documentos y vuelve a indexarlos."
            )
        saved = meta.get("embed_model")
        if saved and saved != self._model():
            raise ValueError(
                f"El índice se creó con `{saved}` y ahora los embeddings son de `{self._model()}`. "
                "Ejecuta `python tools/reembed.py` para recalcularlos sin volver a leer los archivos."
            )

    def _stamp(self, conn, dim: int):
        for k, v in (("dim", str(dim)), ("embed_model", self._model())):
            conn.execute(f"INSERT INTO {self.schema}.index_meta VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (k, v))

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

    # ---------- documentos ----------

    @property
    def info(self) -> dict:
        """{"docs": {nombre: {hash, origin, added}}}: una copia, para modificar usa add() / set_added()."""
        with self._conn() as conn:
            rows = conn.execute(f"SELECT name, hash, origin, added FROM {self.schema}.documents").fetchall()
        return {"docs": {n: {"hash": h, "origin": o, "added": a} for n, h, o, a in rows}}

    def docs(self) -> list[str]:
        with self._conn() as conn:
            return [r[0] for r in conn.execute(f"SELECT name FROM {self.schema}.documents ORDER BY name").fetchall()]

    def suggestions(self, doc: str) -> list[str] | None:
        """Preguntas sugeridas ya generadas para el documento (None si todavía no)."""
        with self._conn() as conn:
            row = conn.execute(f"SELECT suggestions FROM {self.schema}.documents WHERE name = %s", (doc,)).fetchone()
        return row[0] if row else None

    def set_suggestions(self, doc: str, questions: list[str]):
        with self._conn() as conn:
            conn.execute(f"UPDATE {self.schema}.documents SET suggestions = %s WHERE name = %s", (Jsonb(_scrub(questions)), doc))

    def set_added(self, doc: str, when: float):
        with self._conn() as conn:
            conn.execute(f"UPDATE {self.schema}.documents SET added = %s WHERE name = %s", (when, doc))

    @staticmethod
    def _mm(media, n: int) -> list:
        """Vectores multimedia alineados con los fragmentos (None = ese fragmento no tiene imagen ni audio propios), normalizados."""
        media = list(media) if media is not None else [None] * n
        if len(media) != n:
            raise ValueError("Hay que dar un vector multimedia (o None) por cada fragmento.")
        return [None if v is None else VectorStore._norm(np.asarray(v, dtype=np.float32)) for v in media]

    def add(self, doc: str, chunks: list[dict], vectors: list[list[float]], file_hash: str = "", origin: str = "upload", media: list | None = None):
        """Sustituye el documento (si existía) por estos fragmentos, todo en una transacción: si algo falla no queda a medias.
        `vectors`: el vector del texto de cada fragmento. `media`: el vector de su imagen o audio original, si lo tiene."""
        S, new = self.schema, self._norm(np.asarray(vectors, dtype=np.float32))
        mm = self._mm(media, len(chunks))
        with self._lock, self._conn() as conn:
            conn.execute(f"DELETE FROM {S}.documents WHERE name = %s", (doc,))  # no borra su copia: pudo ser la fuente de esta lectura
            self._check(conn, new.shape[1])
            self._stamp(conn, new.shape[1])
            conn.execute(f"INSERT INTO {S}.documents (name, hash, origin, added) VALUES (%s, %s, %s, %s)", (doc, file_hash, origin, time.time()))
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {S}.chunks (doc, ord, kind, loc, text, extra, tokens, embedding, embedding_mm) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s::vector)",
                    [
                        (doc, i, c.get("kind", ""), c.get("loc", ""), _clean(c["text"]),
                         Jsonb(_scrub({k: v for k, v in c.items() if k not in ("kind", "loc", "text", "doc")})),
                         " ".join(_terms(_clean(c["text"]))), _vec(v), None if m is None else _vec(m))
                        for i, (c, v, m) in enumerate(zip(chunks, new, mm))
                    ],
                )

    def delete(self, doc: str, remove_file: bool = True):
        with self._lock:
            if remove_file:
                (self.files_dir / doc).unlink(missing_ok=True)
            with self._conn() as conn:
                conn.execute(f"DELETE FROM {self.schema}.documents WHERE name = %s", (doc,))  # sus fragmentos caen en cascada

    def save_file(self, path):
        """Guarda una copia del original para poder mostrar la página o el minuto citado."""
        self.files_dir.mkdir(parents=True, exist_ok=True)
        dest = self.files_dir / Path(path).name
        if dest.exists() and Path(path).resolve() == dest.resolve():
            return  # ya es la copia guardada (releer un documento desde su propia copia)
        shutil.copy2(path, dest)

    def file_path(self, doc: str) -> Path | None:
        p = self.files_dir / doc
        return p if p.exists() else None

    # ---------- fragmentos ----------

    @staticmethod
    def _chunk(r) -> dict:
        return {**r[5], "id": r[0], "doc": r[1], "kind": r[2], "loc": r[3], "text": r[4]}

    def chunk_count(self) -> int:
        with self._conn() as conn:
            return conn.execute(f"SELECT count(*) FROM {self.schema}.chunks").fetchone()[0]

    def chunks_of(self, doc: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT {_COLS} FROM {self.schema}.chunks WHERE doc = %s ORDER BY ord", (doc,)).fetchall()
        return [self._chunk(r) for r in rows]

    def get_chunks(self, ids: list[int]) -> dict[int, dict]:
        """Fragmentos por id (los ids que no existen simplemente no aparecen)."""
        if not ids:
            return {}
        with self._conn() as conn:
            rows = conn.execute(f"SELECT {_COLS} FROM {self.schema}.chunks WHERE id = ANY(%s)", (list(ids),)).fetchall()
        return {r[0]: self._chunk(r) for r in rows}

    def all_chunks(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT {_COLS} FROM {self.schema}.chunks ORDER BY id").fetchall()
        return [self._chunk(r) for r in rows]

    def reembed(self, ids: list[int], vectors: list[list[float]], media: list | None = None):
        """Sustituye los vectores de estos fragmentos (en una sola transacción) por los de otro modelo. Con `media`, también los de imagen/audio."""
        new = self._norm(np.asarray(vectors, dtype=np.float32))
        mm = self._mm(media, len(ids)) if media is not None else None
        if len(new) != len(ids):
            raise ValueError("Hay que recalcular un vector por cada fragmento.")
        with self._lock, self._conn() as conn:
            if len(ids) != conn.execute(f"SELECT count(*) FROM {self.schema}.chunks").fetchone()[0]:
                raise ValueError("Hay que recalcular todos los fragmentos del índice, no solo algunos.")
            with conn.cursor() as cur:
                cur.executemany(f"UPDATE {self.schema}.chunks SET embedding = %s::vector WHERE id = %s", [(_vec(v), i) for i, v in zip(ids, new)])
                if mm is not None:
                    cur.executemany(f"UPDATE {self.schema}.chunks SET embedding_mm = %s::vector WHERE id = %s", [(None if m is None else _vec(m), i) for i, m in zip(ids, mm)])
            self._stamp(conn, new.shape[1])

    # ---------- búsqueda ----------

    def search(self, qvec: list[float], k: int, docs: list[str] | None = None) -> list[dict]:
        """Solo por similitud de significado (coseno)."""
        S, q = self.schema, _vec(self._norm(np.asarray(qvec, dtype=np.float32)))
        with self._conn() as conn:
            self._check(conn, len(qvec))
            rows = conn.execute(
                f"SELECT {_COLS}, 1 - (embedding <=> %s::vector) FROM {S}.chunks WHERE (%s::text[] IS NULL OR doc = ANY(%s)) "
                "ORDER BY embedding <=> %s::vector LIMIT %s", (q, docs, docs, q, k),
            ).fetchall()
        return [{**self._chunk(r), "score": float(r[6])} for r in rows]

    def hybrid_search(self, qvec: list[float], query: str, k: int, docs: list[str] | None = None, pool: int = 50) -> list[dict]:
        """El texto manda: RRF de dos rankings (el significado, por embeddings, y las palabras exactas: nombres, códigos, cifras).
        Además, hasta `MM_SLOTS` de los k resultados pueden venir de coincidir DIRECTAMENTE con la imagen o el audio original del fragmento
        (embeddings multimedia): la pregunta se compara con su vector y, si la similitud pasa `MM_TAU`, entra en esa ranura.

        Por qué ranuras y no un ranking más en la RRF (ni un bono de puntaje): la similitud entre una pregunta escrita y una imagen o un audio
        es alta (0,5-0,78) aunque no tengan nada que ver, y en una base real casi todo es multimedia. Como ranking, desplazaba al texto
        correcto (preguntas de texto: la fuente correcta bajó de 25/25 a 16/25) y, con un bono, dentro de un video los fotogramas sacaban
        del top la transcripción con la respuesta. Con ranuras acotadas el texto conserva k-MM_SLOTS lugares pase lo que pase."""
        S, q = self.schema, _vec(self._norm(np.asarray(qvec, dtype=np.float32)))
        words = list(dict.fromkeys(_terms(query)))
        slots, tau = max(0, min(config.MM_SLOTS, k - 1)), config.MM_TAU
        with self._conn() as conn:
            self._check(conn, len(qvec))
            by_vec = [r[0] for r in conn.execute(
                f"SELECT id FROM {S}.chunks WHERE (%s::text[] IS NULL OR doc = ANY(%s)) ORDER BY embedding <=> %s::vector LIMIT %s",
                (docs, docs, q, pool)).fetchall()]
            lex = conn.execute(
                f"SELECT id, ts_rank(tsv, query) FROM {S}.chunks, to_tsquery('simple', %s) query "
                "WHERE tsv @@ query AND (%s::text[] IS NULL OR doc = ANY(%s)) ORDER BY 2 DESC, id LIMIT %s",
                (" | ".join(f"'{w}'" for w in words), docs, docs, pool)).fetchall() if words else []
            by_text, rank_text = [r[0] for r in lex], {r[0]: float(r[1]) for r in lex}
            media = [r[0] for r in conn.execute(
                f"SELECT id FROM {S}.chunks WHERE embedding_mm IS NOT NULL AND (%s::text[] IS NULL OR doc = ANY(%s)) "
                "AND 1 - (embedding_mm <=> %s::vector) > %s ORDER BY embedding_mm <=> %s::vector LIMIT %s",
                (docs, docs, q, tau, q, k + slots)).fetchall()] if slots else []
            fused: dict[int, float] = {}
            for ranking in (by_vec, by_text):
                for rank, i in enumerate(ranking):
                    fused[i] = fused.get(i, 0.0) + 1 / (RRF_K + rank)
            by_score = sorted(fused, key=fused.get, reverse=True)
            picks: list[int] = []
            for i in media:  # los más parecidos por imagen/audio que el texto no trajo ya entre sus primeros resultados
                if len(picks) == slots:
                    break
                if i not in by_score[: k - slots] and i not in picks:
                    picks.append(i)
            top = [i for i in by_score if i not in picks][: k - len(picks)] + picks
            if not top:
                return []
            rows = {r[0]: r for r in conn.execute(
                f"SELECT {_COLS}, 1 - (embedding <=> %s::vector), CASE WHEN embedding_mm IS NULL THEN NULL ELSE 1 - (embedding_mm <=> %s::vector) END "
                f"FROM {S}.chunks WHERE id = ANY(%s)", (q, q, top)).fetchall()}
        out = []
        for i in top:
            r = rows[i]
            out.append({**self._chunk(r), "score": float(r[6]), "mm_score": None if r[7] is None else float(r[7]), "via": "media" if i in picks else "texto",
                        "bm25": rank_text.get(i, 0.0), "rrf": fused.get(i, 0.0)})
        return out
