"""API web (FastAPI) sobre el núcleo `chatpdf`. También sirve el frontend React compilado (web/dist).

Arrancar:  uvicorn server.main:app --port 8000      (o run_web.bat)
"""
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from urllib.parse import quote
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chatpdf import config, llm, media, rag, viewer  # noqa: E402
from chatpdf.ingest import AUDIO_EXT, SUPPORTED_EXT, VIDEO_EXT  # noqa: E402
from chatpdf.chats import ChatStore  # noqa: E402
from chatpdf.store import VectorStore, db_problem  # noqa: E402

app = FastAPI(title=config.APP_NAME)
config.load_settings()


class State:
    store: VectorStore | None = None
    chats: ChatStore | None = None
    jobs: dict[str, "Job"] = {}
    index_lock = threading.Lock()  # el indexado es pesado (GPU/CPU): un trabajo a la vez
    previews: dict[str, str] = {}  # nombre -> "converting" | "error: …" (copias H.264 de videos que el navegador no reproduce)


state = State()


def get_store() -> VectorStore:
    if state.store is None:
        state.store = VectorStore()
    return state.store


# ---------- trabajos en segundo plano (subida y sincronización) ----------

class Cancelled(Exception):
    pass


@dataclass
class Job:
    id: str
    kind: str
    state: str = "queued"  # queued | running | done | error | cancelled
    progress: float = 0.0
    message: str = ""
    current: str = ""
    done: int = 0
    total: int = 0
    result: dict = field(default_factory=dict)
    error: str = ""
    started: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict:
        eta = None
        if self.state == "running" and self.progress > 0.05:
            eta = int((time.time() - self.started) / self.progress * (1 - self.progress))
        return {"id": self.id, "kind": self.kind, "state": self.state, "progress": round(self.progress, 4), "message": self.message,
                "current": self.current, "done": self.done, "total": self.total, "result": self.result, "error": self.error, "eta_seconds": eta}


def start_job(kind: str, work) -> Job:
    """work(job) hace el trabajo; debe llamar a job_callbacks() para informar el progreso y poder cancelarse."""
    job = Job(id=uuid.uuid4().hex[:10], kind=kind)
    state.jobs[job.id] = job

    def run():
        with state.index_lock:
            if job.cancel.is_set():
                job.state = "cancelled"
                return
            job.state, job.started = "running", time.time()
            try:
                work(job)
                job.state, job.progress = "done", 1.0
            except Cancelled:
                job.state, job.message = "cancelled", "Cancelado. Lo ya analizado queda en caché."
            except Exception as e:  # noqa: BLE001
                job.state, job.error = "error", f"{type(e).__name__}: {e}"

    threading.Thread(target=run, daemon=True).start()
    return job


def job_callbacks(job: Job, index: int = 0, count: int = 1, name: str = ""):
    """(log, progress) para rag.index_file; ambos revisan si se pidió cancelar."""
    def check():
        if job.cancel.is_set():
            raise Cancelled()

    def progress(frac: float, msg: str):
        check()
        job.progress, job.message, job.current = (index + frac) / count, msg, name

    return (lambda _m: check()), progress


def start_preview(name: str, path: Path) -> None:
    """Crea en segundo plano la copia H.264 de un video que el navegador no puede reproducir (p. ej. HEVC de TikTok)."""
    if state.previews.get(name) == "converting":
        return
    state.previews[name] = "converting"

    def run():
        try:
            media.make_preview(path)
            state.previews.pop(name, None)
        except Exception as e:  # noqa: BLE001
            state.previews[name] = f"error: {type(e).__name__}: {e}"

    threading.Thread(target=run, daemon=True).start()


def prepare_previews(names) -> None:
    for name in names:
        path = get_store().file_path(name)
        if path and path.suffix.lower() in VIDEO_EXT and not media.preview_ready(path) and media.needs_preview(path)[0]:
            start_preview(name, path)


def apply_options(use_vision: bool, lang: str):
    config.WHISPER_LANG = lang or None
    return use_vision


# ---------- estado y configuración ----------

class ModelCfg(BaseModel):
    backend: str
    model: str
    base_url: str = ""


class SettingsReq(BaseModel):
    chat: ModelCfg
    embed: ModelCfg
    api_key: str | None = None


def public_cfg(cfg: dict) -> dict:
    return {k: cfg[k] for k in ("backend", "model", "base_url")}


def docs_info() -> list[dict]:
    store = get_store()
    out = []
    info = store.info["docs"]
    for d in store.docs():
        chunks = store.chunks_of(d)
        out.append({"name": d, "origin": info.get(d, {}).get("origin", "upload"), "chunks": len(chunks),
                    "kinds": dict(Counter(c["kind"] for c in chunks)), "ext": Path(d).suffix.lower().lstrip(".")})
    return out


@app.get("/api/status")
def status():
    db = db_problem()
    return {
        "app": config.APP_NAME, "problems": ([db] if db else []) + llm.check_backends(), "chat": public_cfg(config.CHAT), "embed": public_cfg(config.EMBED),
        "has_key": bool(config.CHAT["api_key"]), "cloud": "openai" in (config.CHAT["backend"], config.EMBED["backend"]),
        "backends": {k: {"label": v["label"], "default_url": v["default_url"]} for k, v in config.BACKENDS.items()},
        "docs": [] if db else docs_info(), "kb_dir": str(config.KB_DIR), "extensions": sorted(SUPPORTED_EXT),
    }


@app.post("/api/settings")
def set_settings(req: SettingsReq):
    for cfg in (req.chat, req.embed):
        if cfg.backend not in config.BACKENDS:
            raise HTTPException(400, f"Proveedor desconocido: {cfg.backend}")
    for cfg in (req.chat, req.embed):
        if not cfg.model.strip():
            raise HTTPException(400, "El modelo no puede estar vacío")
    config.CHAT.update(req.chat.model_dump())
    config.EMBED.update(req.embed.model_dump())
    if req.api_key is not None:  # la clave vive solo en memoria; nunca se guarda en disco
        config.CHAT["api_key"] = config.EMBED["api_key"] = req.api_key
    config.save_settings()
    return status()


# ---------- documentos ----------

@app.get("/api/docs")
def list_docs():
    return docs_info()


def safe_name(name: str) -> str:
    if not name or name in (".", "..") or Path(name).name != name:
        raise HTTPException(400, "Nombre de archivo no válido")
    return name


def indexed_file(doc: str) -> Path:
    """Ruta del original de un documento indexado (404 si no existe). Evita servir cualquier otra cosa del disco."""
    safe_name(doc)
    path = get_store().file_path(doc)
    if doc not in get_store().docs() or not path or not path.is_file():
        raise HTTPException(404, "Archivo no encontrado")
    return path


@app.delete("/api/docs/{name}")
def delete_doc(name: str):
    safe_name(name)
    if name not in get_store().docs():
        raise HTTPException(404, "Documento no encontrado")
    media.remove_preview(get_store().file_path(name))
    state.previews.pop(name, None)
    get_store().delete(name)
    return {"deleted": name}


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), use_vision: bool = Form(True), lang: str = Form("")):
    tmp = Path(tempfile.mkdtemp(prefix="chatpdf_up_"))
    paths = []
    for f in files:
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in SUPPORTED_EXT:
            shutil.rmtree(tmp, ignore_errors=True)
            raise HTTPException(400, f"Formato no soportado: {name or '(sin nombre)'}")
        dest = tmp / name
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        paths.append(dest)
    vision = apply_options(use_vision, lang)

    def work(job: Job):
        job.total = len(paths)
        try:
            for i, p in enumerate(paths):
                log, progress = job_callbacks(job, i, len(paths), p.name)
                job.current = p.name
                try:
                    n = rag.index_file(get_store(), p, vision, log, progress)
                    job.result[p.name] = {"chunks": n}
                    prepare_previews([p.name])
                except Cancelled:
                    raise
                except Exception as e:  # noqa: BLE001  un archivo malo no impide indexar los demás
                    job.result[p.name] = {"error": f"{type(e).__name__}: {e}"}
                job.done = i + 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return start_job("upload", work).public()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    return job.public()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    job.cancel.set()
    return job.public()


# ---------- base de conocimiento (carpeta) ----------

@app.get("/api/kb")
def kb_status():
    config.KB_DIR.mkdir(exist_ok=True)
    scan = rag.kb_scan(get_store(), config.KB_DIR)
    names = lambda items: [p.name if isinstance(p, Path) else p for p in items]  # noqa: E731
    return {"folder": str(config.KB_DIR), **{k: names(v) for k, v in scan.items()}}


@app.post("/api/kb/open")
def kb_open(request: Request):
    """Abre la carpeta de documentos en el explorador de archivos (solo desde este mismo equipo)."""
    if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(403, "Solo se puede abrir la carpeta desde el equipo donde corre la app.")
    config.KB_DIR.mkdir(exist_ok=True)
    if not hasattr(os, "startfile"):
        raise HTTPException(501, f"Abre la carpeta a mano: {config.KB_DIR}")
    os.startfile(config.KB_DIR)  # noqa: S606  (Windows)
    return {"opened": str(config.KB_DIR)}


class SyncReq(BaseModel):
    use_vision: bool = True
    lang: str = ""


@app.post("/api/kb/sync")
def kb_sync(req: SyncReq):
    vision = apply_options(req.use_vision, req.lang)

    def work(job: Job):
        state_ = {"i": 1, "n": 1, "name": ""}

        def on_file(p: Path, i: int, n: int):
            state_.update(i=i, n=n, name=p.name)
            job.total, job.done = n, i - 1

        def progress(frac: float, msg: str):
            if job.cancel.is_set():
                raise Cancelled()
            job.progress, job.message, job.current = (state_["i"] - 1 + frac) / state_["n"], msg, state_["name"]

        def log(_msg: str):
            if job.cancel.is_set():
                raise Cancelled()

        job.result = rag.kb_sync(get_store(), config.KB_DIR, vision, on_file=on_file, log=log, progress=progress)
        prepare_previews(job.result.get("indexed", []))

    return start_job("kb_sync", work).public()


# ---------- chat ----------

MAX_QUESTION = 4000  # caracteres


class Zone(BaseModel):
    page: int  # página (desde 1)
    rect: list[float]  # [x0, y0, x1, y1] como fracciones de la página (0-1), tal como se ve en pantalla


class ChatReq(BaseModel):
    question: str
    history: list[dict] = []
    docs: list[str] | None = None  # None = todos los documentos
    rerank: bool = False
    zone: Zone | None = None  # zona del PDF marcada a mano: la respuesta sale solo de ahí


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def public_hit(h: dict) -> dict:
    score = None if h["score"] is None else round(h["score"], 3)  # None = fuente de un resumen: no hay "similitud"
    return {"id": h["id"], "doc": h["doc"], "loc": h["loc"], "kind": h["kind"], "score": score, "text": h["text"][:500], "via": h.get("via")}


def zone_events(doc: str, zone: Zone, question: str, history: list[dict]):
    """Responde solo con lo que hay dentro de la zona: su texto y, para que entienda gráficos, tarjetas y tablas, su imagen."""
    path = indexed_file(doc)
    if path.suffix.lower() != ".pdf":
        raise ValueError("Marcar una zona solo funciona con PDFs.")
    try:
        ctx = viewer.read_zone(str(path), zone.page, zone.rect)
    except IndexError:
        raise ValueError("Página fuera de rango.") from None
    label = f"{doc}, pág. {zone.page}"
    png = viewer.render_zone(str(path), zone.page, zone.rect)
    out = []
    yield "status", "Mirando la zona…"
    try:  # con imagen: entiende tarjetas, tablas y gráficos. Si el modelo no admite imágenes, se responde solo con el texto.
        for token in llm.chat_stream(rag.build_zone_messages(question, label, ctx["text"], history, png)):
            out.append(token)
            yield "token", token
    except Exception:  # noqa: BLE001
        if out or not ctx["text"]:
            raise
        for token in llm.chat_stream(rag.build_zone_messages(question, label, ctx["text"], history)):
            out.append(token)
            yield "token", token
    if label not in "".join(out):
        yield "token", f" [{label}]"


@app.get("/api/zone/{doc}/{page}")
def zone_image(doc: str, page: int, x0: float, y0: float, x1: float, y1: float, dpi: int = 130):
    """Recorte de la zona marcada (para la vista previa y para que el modelo la vea)."""
    path = indexed_file(doc)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(404, "PDF no encontrado")
    try:
        png = viewer.render_zone(str(path), page, [x0, y0, x1, y1], min(max(dpi, 60), 220))
    except IndexError:
        raise HTTPException(404, "Página fuera de rango") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@app.post("/api/chat")
def chat(req: ChatReq):
    history = [{"role": m["role"], "content": m["content"]} for m in req.history if m.get("role") in ("user", "assistant")]

    def gen():
        try:
            if not req.question.strip():
                raise ValueError("Escribe una pregunta.")
            if len(req.question) > MAX_QUESTION:
                raise ValueError(f"La pregunta es demasiado larga ({len(req.question)} caracteres; el máximo es {MAX_QUESTION}).")
            if req.docs is not None and not req.docs:
                raise ValueError("Selecciona al menos un documento donde buscar.")
            unknown = [d for d in (req.docs or []) if d not in get_store().docs()]
            if unknown:
                raise ValueError(f"Documento no encontrado: {unknown[0]}" + (f" (y {len(unknown) - 1} más)" if len(unknown) > 1 else ""))
            if not get_store().docs():
                raise ValueError("Todavía no hay documentos indexados: sube archivos o sincroniza la carpeta.")
            if req.zone:
                if not req.docs or len(req.docs) != 1:
                    raise ValueError("Para preguntar sobre una zona escoge un solo archivo.")
                yield sse("sources", [])
                for kind, value in zone_events(req.docs[0], req.zone, req.question, history):
                    yield sse(kind, {"message": value} if kind == "status" else {"t": value})
                yield sse("done", {"model": llm.last_model.get("chat")})
                return
            targets = rag.overview_targets(get_store(), req.question, req.docs) if rag.is_overview(req.question) else []
            if targets:
                # Pregunta global ("¿de qué trata el video?"): se lee TODO el documento en orden, no solo los 6 fragmentos más parecidos
                yield sse("sources", [public_hit(h) for d in targets for h in rag.overview_hits(get_store(), d)])
                for doc in targets:
                    if len(targets) > 1:
                        yield sse("token", {"t": f"\n\n**{doc}**\n\n"})
                    for kind, value in rag.overview_stream(get_store(), doc):
                        yield sse("status", {"message": value}) if kind == "status" else sse("token", {"t": value})
            else:
                hits = rag.retrieve(get_store(), rag.standalone_question(req.question, history), req.docs, use_rerank=req.rerank)
                yield sse("sources", [public_hit(h) for h in hits])
                for token in llm.chat_stream(rag.build_messages(req.question, hits, history)):
                    yield sse("token", {"t": token})
            yield sse("done", {"model": llm.last_model.get("chat")})
        except Exception as e:  # noqa: BLE001
            # los ValueError son avisos para el usuario («Escribe una pregunta», «Zona demasiado pequeña»…): sin el nombre de la excepción
            yield sse("error", {"message": str(e) if isinstance(e, ValueError) else f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class QuizReq(BaseModel):
    doc: str | None = None  # practicar con un documento completo…
    chunks: list[int] = []  # …o con los fragmentos que usó una respuesta
    question: str = ""  # lo que el estudiante preguntó, para enfocar las preguntas
    n: int = 5


def study_items(req: QuizReq, limit: int = 8) -> list[tuple[int, dict]]:
    """Fragmentos con los que se genera un examen o un mapa: los de una respuesta, o una muestra repartida de un documento."""
    store = get_store()
    if req.chunks:
        found = store.get_chunks(list(dict.fromkeys(req.chunks)))
        items = [(i, found[i]) for i in dict.fromkeys(req.chunks) if i in found][:limit]
    elif req.doc:
        safe_name(req.doc)
        if req.doc not in store.docs():
            raise HTTPException(404, "Documento no encontrado")
        every = rag.ordered_chunks(store, req.doc)
        step = max(1, -(-len(every) // limit))
        items = every[::step][:limit]  # una muestra repartida a lo largo del documento
    else:
        raise HTTPException(400, "Indica un documento o los fragmentos de los que partir")
    if not items:
        raise HTTPException(400, "No hay contenido del que partir")
    return items


@app.post("/api/quiz")
def quiz(req: QuizReq):
    items = study_items(req)
    try:
        return {"questions": rag.make_quiz(items, req.question, req.n)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e


@app.post("/api/mindmap")
def mindmap(req: QuizReq):
    items = study_items(req, limit=8)
    try:
        return {"map": rag.make_mindmap(items, req.question)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e


@app.get("/api/docs/{name}/suggestions")
def suggestions(name: str):
    """Preguntas para empezar con este documento. Se generan la primera vez que se abre y se guardan en la base de datos."""
    safe_name(name)
    store = get_store()
    if name not in store.docs():
        raise HTTPException(404, "Documento no encontrado")
    saved = store.suggestions(name)
    if saved:
        return {"questions": saved, "generated": True}
    questions = rag.make_suggestions(store, name)
    generated = questions != rag.generic_questions(name)[: len(questions)]
    if generated:
        store.set_suggestions(name, questions)
    return {"questions": questions, "generated": generated}


class SummaryReq(BaseModel):
    doc: str


@app.post("/api/summarize")
def summarize(req: SummaryReq):
    safe_name(req.doc)
    if req.doc not in get_store().docs():
        raise HTTPException(404, "Documento no encontrado")
    try:
        return {"summary": rag.summarize(get_store(), req.doc)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e


# ---------- evidencias: archivo original y página resaltada ----------

@app.get("/api/files/{doc}")
def original_file(doc: str):
    path = media.playable_path(indexed_file(doc))  # si el video no se reproduce en el navegador y ya hay copia H.264, se sirve esa
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")  # admite Range (audio/video)


@lru_cache(maxsize=128)
def _page_png(path: str, mtime: float, page: int, text: str, dpi: int, mark_images: bool = False) -> bytes:
    return viewer.render_page(path, page, text, dpi, mark_images)[0]


@app.get("/api/docs/{name}/playback")
def playback(name: str, force: bool = False):
    """¿Se puede reproducir en el navegador? Si no (HEVC, .avi…), prepara una copia H.264 y avisa del avance.
    state: original (se reproduce tal cual) | converting (preparando la copia) | ready (copia lista) | error."""
    path = indexed_file(name)
    ext = path.suffix.lower()
    if ext not in AUDIO_EXT | VIDEO_EXT:
        raise HTTPException(404, "No es un audio ni un video")
    url = f"/api/files/{quote(name)}"
    need, reason = media.needs_preview(path)
    if force and ext in VIDEO_EXT and not need:  # el navegador no mostró la imagen aunque el formato parecía bueno
        need, reason = True, "formato que este navegador no muestra"
    if not need:
        return {"state": "original", "url": url}
    if media.preview_ready(path):
        return {"state": "ready", "reason": reason, "url": url}
    current = state.previews.get(name)
    if current is None or (force and current.startswith("error")):
        start_preview(name, path)
        current = "converting"
    failed = current.startswith("error")
    return {"state": "error" if failed else "converting", "reason": reason, "message": current[7:] if failed else "", "url": url}


@app.get("/api/docs/{name}/content")
def doc_content(name: str):
    """Todo lo que la app entendió de un documento (en orden de página o de minuto), para el visor."""
    path = indexed_file(name)
    pages = None
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as pdf:
            pages = len(pdf)
    chunks = [{"id": i, "loc": m["loc"], "kind": m["kind"], "text": m["text"]} for i, m in rag.ordered_chunks(get_store(), name)]
    return {"name": name, "ext": path.suffix.lower().lstrip("."), "pages": pages, "chunks": chunks}


@app.get("/api/page/{doc}/{page}")
def page_image(doc: str, page: int, chunk: list[int] | None = Query(default=None), dpi: int = 110):
    """Página del PDF con lo citado en amarillo. `chunk` puede repetirse (?chunk=3&chunk=7): se marcan todos los de esa página."""
    store = get_store()
    path = indexed_file(doc)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(404, "PDF no encontrado")
    texts, mark_images = [], False
    found = store.get_chunks(sorted(set(chunk or [])))
    for cid in sorted(found):
        if found[cid]["doc"] != doc:
            continue
        where = viewer.parse_loc(found[cid]["loc"])
        if where and where != ("page", page):
            continue  # un fragmento de otra página no se pinta en esta
        if found[cid]["kind"] == "visión":
            mark_images = True  # su texto salió de una imagen: se enmarca la imagen, no hay texto que resaltar
        else:
            texts.append(found[cid]["text"])
    try:
        png = _page_png(str(path), path.stat().st_mtime, page, "\n".join(texts), min(max(dpi, 60), 200), mark_images)
    except IndexError:
        raise HTTPException(404, "Página fuera de rango") from None
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


# ---------- historial de chats (PostgreSQL: tablas chats y chat_messages) ----------

_CHAT_ID = re.compile(r"^[a-f0-9]{12}$")
_MSG_KEYS = ("role", "content", "sources", "model", "error", "quiz", "map", "zone")


def get_chats() -> ChatStore:
    if state.chats is None:
        state.chats = ChatStore()
    return state.chats


def check_chat_id(chat_id: str) -> str:
    if not _CHAT_ID.match(chat_id):
        raise HTTPException(400, "Identificador de chat no válido")
    return chat_id


def clean_messages(messages: list[dict]) -> list[dict]:
    """Solo se guardan los campos conocidos y los roles válidos (el cliente no decide el formato del archivo)."""
    if len(messages) > 2000:
        raise HTTPException(400, "Demasiados mensajes en un solo chat")
    out = []
    for m in messages:
        if m.get("role") not in ("user", "assistant"):
            continue
        out.append({k: m[k] for k in _MSG_KEYS if k in m and m[k] not in (None, "")})
    return out


def derive_title(messages: list[dict]) -> str:
    first = next((m["content"] for m in messages if m["role"] == "user" and m.get("content")), "")
    first = " ".join(first.split())
    return (first[:60] + "…") if len(first) > 60 else (first or "Nuevo chat")


def read_chat(chat_id: str) -> dict:
    data = get_chats().get(check_chat_id(chat_id))
    if data is None:
        raise HTTPException(404, "Chat no encontrado")
    return data


class ChatBody(BaseModel):
    title: str | None = None
    messages: list[dict] = []
    doc: str | None = None  # documento sobre el que trata el chat (se fija al crearlo)


class RenameBody(BaseModel):
    title: str


@app.get("/api/chats")
def list_chats():
    return get_chats().summaries()


@app.post("/api/chats")
def create_chat(body: ChatBody):
    messages = clean_messages(body.messages)
    title = (body.title or "").strip()[:80] or derive_title(messages)
    return get_chats().save(uuid.uuid4().hex[:12], title, messages, doc=body.doc)


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    return read_chat(chat_id)


@app.put("/api/chats/{chat_id}")
def save_chat(chat_id: str, body: ChatBody):
    old = read_chat(chat_id)
    messages = clean_messages(body.messages)
    return get_chats().save(chat_id, (body.title or "").strip()[:80] or old["title"], messages, doc=body.doc)


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: RenameBody):
    old = read_chat(chat_id)
    title = body.title.strip()[:80]
    if not title:
        raise HTTPException(400, "El título no puede estar vacío")
    return get_chats().save(chat_id, title, old["messages"])


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    if not get_chats().delete(check_chat_id(chat_id)):
        raise HTTPException(404, "Chat no encontrado")
    return {"deleted": chat_id}


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- frontend React compilado ----------

class WebFiles(StaticFiles):
    """index.html nunca se cachea (así una versión nueva se ve al recargar); los archivos con hash de assets/ se cachean para siempre."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return response


_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if _dist.exists():
    app.mount("/", WebFiles(directory=_dist, html=True), name="web")
