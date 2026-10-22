"""Convierte cualquier archivo (PDF, imagen, audio, video, texto) en chunks de texto con su ubicación."""
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Callable

from . import cache, config, llm

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
TEXT_EXT = {".txt", ".md"}
SUPPORTED_EXT = {".pdf"} | IMG_EXT | AUDIO_EXT | VIDEO_EXT | TEXT_EXT

Log = Callable[[str], None]
Progress = Callable[[float, str], None]  # (fracción 0..1, mensaje)

VISION_PROMPT = (
    "Transcribe todo el texto visible tal cual aparece y luego describe brevemente "
    "tablas, gráficos, diagramas o elementos visuales relevantes. Responde en el idioma del contenido."
)
VIDEO_PROMPT = (
    "Este es un fotograma de un video. Responde en español, en 2 o 3 frases sin títulos ni listas: qué está pasando, "
    "quién o qué aparece y qué hace, y dónde está. No adivines quién es una persona: menciona nombres solo si aparecen "
    "escritos en pantalla. Si hay texto importante en pantalla, cópialo tal cual."
)


def _prompt_id(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()[:8]  # si cambias el prompt, la caché se invalida

_whisper = None


def _noop_progress(_f: float, _m: str) -> None:
    pass


def _sub(progress: Progress, lo: float, hi: float) -> Progress:
    """Mapea el progreso 0..1 de un paso al tramo lo..hi del total."""
    return lambda f, m: progress(lo + (hi - lo) * min(max(f, 0.0), 1.0), m)


@lru_cache(maxsize=1024)
def _hash_cached(path: str, mtime_ns: int, size: int) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_hash(path: Path) -> str:
    """SHA-256 del contenido. Se recuerda mientras el archivo no cambie (la carpeta se escanea en cada recarga)."""
    st = Path(path).stat()
    return _hash_cached(str(path), st.st_mtime_ns, st.st_size)


def split_text(text: str, size: int = config.CHUNK_CHARS, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):  # cortar en un límite natural
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in out if c]


def _ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _describe(key: str, make_img: Callable[[], bytes], log: Log, prompt: str = VISION_PROMPT) -> str:
    """Descripción de visión con caché. `make_img` solo se llama si no está en caché."""
    full = f"vision|{config.CHAT['backend']}|{config.CHAT['model']}|{_prompt_id(prompt)}|{key}"
    if (hit := cache.get(full)) is not None:
        log("  (desde caché)")
        return hit
    desc = llm.describe_image(make_img(), prompt)
    cache.put(full, desc)
    return desc


def _transcribe(path: Path, fhash: str, log: Log, progress: Progress) -> list[dict]:
    global _whisper
    key = f"whisper|{config.WHISPER_MODEL}|{config.WHISPER_LANG}|{fhash}"
    if (hit := cache.get(key)) is not None:
        log("Transcripción desde caché")
        progress(1.0, "Transcripción desde caché")
        return hit
    from faster_whisper import WhisperModel

    if _whisper is None:
        log(f"Cargando Whisper ({config.WHISPER_MODEL})…")
        _whisper = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE)
    log("Transcribiendo audio…")
    segments, info = _whisper.transcribe(str(path), vad_filter=True, language=config.WHISPER_LANG)
    total = info.duration or 1.0
    chunks, buf, t0, t1 = [], [], None, 0.0
    for s in segments:  # `segments` es un generador: se transcribe mientras se recorre
        if t0 is None:
            t0 = s.start
        buf.append(s.text.strip())
        t1 = s.end
        progress(t1 / total, f"Transcribiendo audio ({_ts(t1)} de {_ts(total)})")
        if t1 - t0 >= 45:
            chunks.append({"text": " ".join(buf), "loc": f"{_ts(t0)}–{_ts(t1)}", "kind": "audio"})
            buf, t0 = [], None
    if buf:
        chunks.append({"text": " ".join(buf), "loc": f"{_ts(t0)}–{_ts(t1)}", "kind": "audio"})
    cache.put(key, chunks)
    return chunks


def _pdf(path: Path, fhash: str, use_vision: bool, log: Log, progress: Progress) -> list[dict]:
    import pymupdf

    chunks = []
    with pymupdf.open(path) as pdf:
        total = len(pdf)
        for i, page in enumerate(pdf, 1):
            progress((i - 1) / total, f"Página {i} de {total}")
            log(f"Página {i}/{total}")
            text = page.get_text().strip()
            for part in split_text(text):
                chunks.append({"text": part, "loc": f"pág. {i}", "kind": "texto"})
            # Páginas escaneadas o con imágenes/gráficos: las lee el modelo de visión
            if use_vision and (len(text) < 80 or page.get_images()):
                desc = _describe(f"{fhash}|p{i}", lambda: page.get_pixmap(dpi=110).tobytes("png"), log)
                for part in split_text(desc):
                    chunks.append({"text": f"[Contenido visual] {part}", "loc": f"pág. {i}", "kind": "visión"})
        progress(1.0, f"Página {total} de {total}")
    return chunks


def _image(path: Path, fhash: str, log: Log, progress: Progress) -> list[dict]:
    progress(0.0, "Analizando imagen")
    log("Analizando imagen…")
    desc = _describe(fhash, path.read_bytes, log)
    return [{"text": p, "loc": "imagen", "kind": "visión"} for p in split_text(desc)]


def _video(path: Path, fhash: str, use_vision: bool, log: Log, progress: Progress) -> list[dict]:
    audio_end = 0.5 if use_vision else 1.0  # con visión, la mitad del progreso es el audio y la otra los frames
    try:
        chunks = _transcribe(path, fhash, log, _sub(progress, 0.0, audio_end))
    except Exception as e:  # video sin pista de audio, etc.
        log(f"Sin audio utilizable ({type(e).__name__}); solo se analizan los frames.")
        chunks = []
    if not use_vision:
        return chunks
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    duration = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps
    step = max(config.FRAME_EVERY_SEC, duration / config.MAX_FRAMES)
    times = [i * step for i in range(int(duration // step) + 1) if i * step < duration]
    prev = None  # miniatura del último frame descrito, para saltar los casi idénticos (diapositivas quietas)
    try:
        for n, t in enumerate(times):
            progress(audio_end + (1 - audio_end) * n / len(times), f"Mirando el video: escena {n + 1} de {len(times)} (minuto {_ts(t)})")
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            small = cv2.cvtColor(cv2.resize(frame, (32, 18)), cv2.COLOR_BGR2GRAY).astype("float32")
            if prev is not None and abs(small - prev).mean() < config.FRAME_MIN_DIFF:
                log(f"Frame {_ts(t)} casi idéntico al anterior: se omite")
                continue
            prev = small
            log(f"Describiendo frame {_ts(t)}…")
            if frame.shape[1] > 1024:
                frame = cv2.resize(frame, (1024, int(frame.shape[0] * 1024 / frame.shape[1])))
            desc = _describe(f"{fhash}|t{int(t)}", lambda f=frame: cv2.imencode(".jpg", f)[1].tobytes(), log, VIDEO_PROMPT)
            chunks.append({"text": f"[Frame de video] {desc}", "loc": _ts(t), "kind": "visión"})
    finally:
        cap.release()
    return chunks


def ingest_file(path: Path, use_vision: bool = True, log: Log = lambda _m: None, progress: Progress = _noop_progress, fhash: str | None = None) -> list[dict]:
    ext = path.suffix.lower()
    fhash = fhash or (file_hash(path) if ext not in TEXT_EXT else "")
    if ext == ".pdf":
        chunks = _pdf(path, fhash, use_vision, log, progress)
    elif ext in IMG_EXT:
        chunks = _image(path, fhash, log, progress)
    elif ext in AUDIO_EXT:
        chunks = _transcribe(path, fhash, log, progress)
    elif ext in VIDEO_EXT:
        chunks = _video(path, fhash, use_vision, log, progress)
    elif ext in TEXT_EXT:
        chunks = [{"text": p, "loc": "texto", "kind": "texto"} for p in split_text(path.read_text(encoding="utf-8", errors="ignore"))]
    else:
        raise ValueError(f"Formato no soportado: {ext}")
    return chunks
