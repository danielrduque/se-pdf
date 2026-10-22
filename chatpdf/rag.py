import json
import random
import re
import unicodedata
from pathlib import Path

from . import config, llm, media_io, viewer
from .ingest import AUDIO_EXT, IMG_EXT, SUPPORTED_EXT, VIDEO_EXT, file_hash, ingest_file
from .store import VectorStore

SYSTEM = (
    "Eres un asistente que responde preguntas sobre documentos del usuario (PDF, imágenes, audio, video). "
    "Usa SOLO el contexto proporcionado. Si la respuesta no está en el contexto, dilo claramente. "
    "Responde en el mismo idioma de la pregunta. Cada fragmento del contexto empieza con una etiqueta entre corchetes "
    "(nombre de archivo y ubicación): al citar, copia EXACTAMENTE esa etiqueta de los fragmentos que usaste. "
    "Nunca inventes archivos, páginas ni minutos. "
    "Responde de forma directa y concisa con tus propias palabras (no copies el contexto), "
    "y pon la cita al final de la frase."
)


def media_vectors(path: Path, chunks: list[dict], log=lambda _m: None) -> list | None:
    """El vector de la imagen o el audio ORIGINAL de cada fragmento que lo tiene (página con gráficos, imagen, fotograma, tramo de audio).

    Es la búsqueda multimodal de verdad: EmbeddingGemma 2 convierte la propia imagen o el propio audio en un vector del mismo espacio que el
    texto, así que una pregunta escrita los encuentra aunque la descripción o la transcripción no mencionen lo que se busca.
    Devuelve una lista alineada con `chunks` (None donde no aplica), o None si no hay nada que embeber o no hay servicio multimodal."""
    if not llm.mm_enabled():
        return None
    ext = path.suffix.lower()
    wanted: dict[tuple, dict] = {}  # clave del medio -> entrada para embed_media (una página con varios fragmentos se embebe una vez)
    keys: list[tuple | None] = []
    for c in chunks:
        key, item = None, None
        loc, kind = c.get("loc", ""), c.get("kind")
        try:
            if kind == "visión" and ext == ".pdf" and (n := media_io.page_number(loc)):
                key = ("page", n)
                item = lambda n=n: {"image": media_io.pdf_page_png(path, n, 110)}
            elif kind == "visión" and ext in IMG_EXT:
                key = ("image",)
                item = lambda: {"image": path.read_bytes()}
            elif kind == "visión" and ext in VIDEO_EXT and (tr := media_io.time_range(loc)):
                key = ("frame", tr[0])
                item = lambda t=tr[0]: (lambda jpg: {"image": jpg} if jpg else None)(media_io.video_frame_jpg(path, t))
            elif kind == "audio" and ext in AUDIO_EXT | VIDEO_EXT and (tr := media_io.time_range(loc)) and tr[1]:
                key = ("audio", tr[0], tr[1])
                item = lambda a=tr[0], b=tr[1]: (lambda w: {"audio": w} if w is not None else None)(media_io.audio_segment(path, a, b))
        except Exception:  # noqa: BLE001
            key = None
        keys.append(key)
        if key is not None and key not in wanted:
            wanted[key] = item
    if not wanted:
        return None
    log(f"Embebiendo directamente {len(wanted)} imagen(es) o tramo(s) de audio con EmbeddingGemma 2…")
    ready = {k: f() for k, f in wanted.items()}
    todo = [k for k, v in ready.items() if v is not None]
    vecs = dict(zip(todo, llm.embed_media([ready[k] for k in todo])))
    failed = sum(1 for k in wanted if vecs.get(k) is None)
    if failed:
        log(f"  {failed} no se pudieron embeber; esos fragmentos se buscan solo por su texto.")
    out = [vecs.get(k) if k is not None else None for k in keys]
    return out if any(v is not None for v in out) else None


def index_file(store: VectorStore, path: Path, use_vision: bool, log, progress=None, origin: str = "upload") -> int:
    progress = progress or (lambda _f, _m: None)
    fhash = file_hash(path)
    chunks = ingest_file(path, use_vision, log, lambda f, m: progress(f * 0.9, m), fhash)  # el 10 % final son los embeddings
    if not chunks:
        raise ValueError("No se pudo extraer contenido del archivo.")
    progress(0.9, f"Preparando la búsqueda ({len(chunks)} fragmento{'' if len(chunks) == 1 else 's'})")
    log(f"Generando embeddings de {len(chunks)} fragmentos…")
    vecs = llm.embed_docs([c["text"] for c in chunks], [path.name] * len(chunks))
    media = media_vectors(path, chunks, log)
    store.add(path.name, chunks, vecs, fhash, origin, media=media)
    store.save_file(path)
    progress(1.0, "Listo")
    return len(chunks)


def kb_scan(store: VectorStore, folder: Path) -> dict:
    """Compara la carpeta con el índice: qué archivos son nuevos, cambiaron, están al día o se borraron."""
    status: dict[str, list] = {"new": [], "changed": [], "ok": [], "removed": [], "duplicates": []}
    indexed = store.info["docs"]
    seen: set[str] = set()
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXT) if folder.exists() else []
    for p in files:
        if p.name in seen:  # el índice identifica los documentos por nombre de archivo
            status["duplicates"].append(p)
            continue
        seen.add(p.name)
        known = indexed.get(p.name)
        if known is None:
            status["new"].append(p)
        elif known["hash"] != file_hash(p):
            status["changed"].append(p)
        else:
            status["ok"].append(p)
    status["removed"] = [d for d, i in indexed.items() if i.get("origin") == "folder" and d not in seen]
    return status


def kb_sync(store: VectorStore, folder: Path, use_vision: bool, on_file=None, log=lambda _m: None, progress=None) -> dict:
    """Indexa lo nuevo, reindexa lo modificado y quita del índice lo que ya no está en la carpeta."""
    status = kb_scan(store, folder)
    todo = status["new"] + status["changed"]
    done, errors = [], {}
    for i, p in enumerate(todo, 1):
        if on_file:
            on_file(p, i, len(todo))
        try:
            index_file(store, p, use_vision, log, progress, origin="folder")
            done.append(p.name)
        except Exception as e:  # un archivo malo no debe impedir indexar los demás
            errors[p.name] = f"{type(e).__name__}: {e}"
    for d in status["removed"]:
        store.delete(d)
    return {"indexed": done, "removed": status["removed"], "errors": errors, "skipped_duplicates": [p.name for p in status["duplicates"]], "up_to_date": len(status["ok"])}


def standalone_question(question: str, history: list[dict]) -> str:
    """Reescribe preguntas de seguimiento ('¿y eso cuánto cuesta?') para que la búsqueda tenga contexto."""
    if not history:
        return question
    recent = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history[-4:])
    rewritten = llm.complete(
        "Dada esta conversación y una pregunta de seguimiento, reescribe la pregunta para que se entienda sola. "
        "Responde SOLO con la pregunta reescrita, en el mismo idioma.\n\n"
        f"Conversación:\n{recent}\n\nPregunta de seguimiento: {question}"
    )
    return rewritten or question


def rerank(question: str, hits: list[dict], k: int = config.TOP_K, min_keep: int = 3) -> list[dict]:
    """Reordena los candidatos con el LLM en UNA sola llamada (listwise). Si la respuesta no se entiende, deja el orden original."""
    if len(hits) <= min_keep:
        return hits
    listing = "\n".join(f"[{i}] {h['text'][:config.RERANK_SNIPPET]!r}" for i, h in enumerate(hits, 1))
    answer = llm.complete(
        f"Pregunta: {question}\n\nFragmentos:\n{listing}\n\n"
        f"¿Qué fragmentos contienen la información para responder la pregunta? Ordénalos del más al menos útil. "
        f"Responde SOLO con sus números separados por comas (máximo {k}).",
        temperature=0,
    )
    order = []
    for n in re.findall(r"\d+", answer):
        i = int(n) - 1
        if 0 <= i < len(hits) and i not in order:
            order.append(i)
    if not order:
        return hits[:k]
    for i in range(len(hits)):  # completa hasta min_keep con el orden híbrido original
        if len(order) >= min_keep:
            break
        if i not in order:
            order.append(i)
    return [hits[i] for i in order[:k]]


def retrieve(
    store: VectorStore,
    question: str,
    docs: list[str] | None = None,
    k: int = config.TOP_K,
    use_rerank: bool = False,  # opcional: añade una llamada al LLM por pregunta y en las pruebas no mejoró nada
) -> list[dict]:
    """Búsqueda híbrida (embeddings + BM25) y, opcionalmente, reranking con el LLM."""
    n = max(k, config.RERANK_CANDIDATES) if use_rerank else k
    hits = store.hybrid_search(llm.embed_query(question), question, n, docs)
    return rerank(question, hits, k) if use_rerank else hits


def build_messages(question: str, hits: list[dict], history: list[dict]) -> list[dict]:
    context = "\n\n".join(f"[{h['doc']}, {h['loc']}]\n{h['text']}" for h in hits)
    past = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    msgs = [{"role": "system", "content": SYSTEM}] + past
    msgs.append({"role": "user", "content": f"Contexto:\n{context}\n\nPregunta: {question}"})
    return msgs


# ---------- preguntas globales: "¿de qué trata el video?", "resume el documento" ----------
# La búsqueda por similitud solo trae los 6 fragmentos más parecidos: sirve para preguntas puntuales, no para
# "de qué trata". Estas preguntas se contestan leyendo TODO el documento, en orden de tiempo o de página.

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# Pregunta global («resume el video», «¿de qué trata?»): se lee el documento entero. Las fórmulas «¿qué pasa en el video?» y «explica el video» solo cuentan
# al principio de la frase: dentro de otra pregunta («¿cuál es el marcador del partido que se ve en el video?») son una oración de relativo y no piden un resumen.
_OVERVIEW = re.compile(r"\b(resum\w*|de que (se )?(trata|va|habla|es)|sobre que (es|trata|habla)|idea general|vision general)\b")
_OVERVIEW_START = re.compile(
    r"^\W*(?:(?:y|pero|oye|ahora|entonces|puedes|podrias|por favor)\s+)*"
    r"(?:que (?:pasa|ocurre|se ve|se dice|dice|explica|muestra|contiene|hay) en (?:el|la|todo|este|esta|ese|esa)"
    r"|(?:explica|explicame|cuenta|cuentame|describe|describeme|analiza|analizame)\w* (?:el|la|todo|este|esta|ese|esa))\b"
)
_KIND_WORDS = {"video": VIDEO_EXT, "audio": AUDIO_EXT, "grabacion": AUDIO_EXT | VIDEO_EXT, "pdf": {".pdf"}, "imagen": IMG_EXT, "foto": IMG_EXT}


def is_overview(question: str) -> bool:
    q = _norm(question)
    return bool(_OVERVIEW.search(q) or _OVERVIEW_START.search(q))


def overview_targets(store: VectorStore, question: str, docs: list[str] | None = None, limit: int = 3) -> list[str]:
    """Qué documento(s) quiere resumir el usuario: el que nombra, el del tipo que menciona (el más reciente) o el único que hay."""
    pool = docs if docs is not None else store.docs()
    if not pool:
        return []
    q = _norm(question)
    named = [d for d in pool if _norm(d) in q or _norm(Path(d).stem) in q]
    if named:
        return named[:limit]
    for word, exts in _KIND_WORDS.items():
        if re.search(rf"\b{word}s?\b", q):
            cands = [d for d in pool if Path(d).suffix.lower() in exts]
            # si nombró un tipo ("el video") que no está entre los seleccionados, no se adivina otro documento
            added = store.info["docs"]
            return [max(cands, key=lambda d: added.get(d, {}).get("added", 0))] if cands else []
    return list(pool) if len(pool) == 1 else []


def _ordered(store: VectorStore, doc: str) -> list[tuple[int, dict]]:
    """Fragmentos del documento en su orden natural: por minuto en audio y video (voz y escenas mezcladas), por página en los demás."""
    items = [(m["id"], m) for m in store.chunks_of(doc)]
    if Path(doc).suffix.lower() in AUDIO_EXT | VIDEO_EXT:
        def start(m: dict) -> int:
            loc = viewer.parse_loc(m["loc"])
            return loc[1] if loc and loc[0] == "time" else 0
        items.sort(key=lambda im: (start(im[1]), 0 if im[1]["kind"] == "audio" else 1))
    return items


ordered_chunks = _ordered  # público: lo usa el visor para listar lo que se entendió de un documento


def _label(m: dict) -> str:
    text = re.sub(r"^\[(Frame de video|Contenido visual)\]\s*", "", m["text"]).strip()
    if m["kind"] == "audio":
        return f"[{m['loc']}] Se dice: {text}"
    if viewer.parse_loc(m["loc"]) and viewer.parse_loc(m["loc"])[0] == "time":
        return f"[{m['loc']}] Se ve: {text}"
    return f"[{m['loc']}] {text}"


def overview_hits(store: VectorStore, doc: str, limit: int = 6) -> list[dict]:
    """Fragmentos representativos (repartidos a lo largo del documento) para mostrar como fuentes; sin puntaje de similitud."""
    items = _ordered(store, doc)
    step = max(1, -(-len(items) // limit))
    return [{**m, "id": i, "score": None} for i, m in items[::step][:limit]]


def _summary_prompt(doc: str, body: str) -> str:
    ext = Path(doc).suffix.lower()
    if ext in VIDEO_EXT:
        intro = ("A continuación está el contenido de un video, en orden de tiempo: «Se dice» es la transcripción del audio y «Se ve» describe algunas escenas. "
                 "Explica DE QUÉ TRATA el video: el tema, qué ocurre, qué se dice y qué se ve, en el orden en que sucede. "
                 "El audio («Se dice») es lo más confiable para saber de qué trata; las escenas («Se ve») dan contexto. "
                 "Si varias escenas muestran a la misma persona o el mismo lugar, cuéntalo como uno solo, sin repetirlo. "
                 "Si el audio es corto o poco claro, apóyate en lo que se ve, y al revés. "
                 "No inventes nombres ni datos: usa solo lo que aparezca escrito en pantalla o se diga en el audio.")
    elif ext in AUDIO_EXT:
        intro = "A continuación está la transcripción de un audio, con su minuto. Explica DE QUÉ TRATA: el tema, las ideas principales y las cifras o datos importantes. No inventes nada."
    else:
        intro = "A continuación está el contenido de un documento, con su página. Resúmelo de forma clara y completa: tema, ideas principales y datos importantes. No inventes nada."
    return f"{intro}\n\nContenido de «{doc}»:\n{body}\n\nResumen en español, con viñetas cortas si ayudan:"


def _group(texts: list[str], size: int = 4500) -> list[str]:
    groups, cur = [], ""
    for t in texts:
        if len(cur) + len(t) > size and cur:
            groups.append(cur)
            cur = ""
        cur += t + "\n"
    return groups + [cur] if cur.strip() else groups


def overview_stream(store: VectorStore, doc: str):
    """Resumen de TODO el documento. Emite ("status", texto) mientras lee por partes y ("token", texto) al escribir la respuesta final."""
    texts = [_label(m) for _, m in _ordered(store, doc)]
    while len(groups := _group(texts)) > 1:  # documentos largos: resumir por partes y luego resumir los resúmenes
        yield ("status", f"Leyendo «{doc}» por partes…")
        texts = []
        for n, g in enumerate(groups, 1):
            yield ("status", f"Leyendo «{doc}»: parte {n} de {len(groups)}…")
            texts.append(llm.complete("Resume los puntos clave de este fragmento, conservando los minutos o páginas si los hay:\n\n" + g))
    yield ("status", f"Escribiendo el resumen de «{doc}»…")
    for token in llm.chat_stream([{"role": "user", "content": _summary_prompt(doc, groups[0] if groups else "")}]):
        yield ("token", token)


def summarize(store: VectorStore, doc: str, log=lambda _m: None) -> str:
    """Resumen completo de un documento (botón «Resumir»)."""
    out = []
    for kind, value in overview_stream(store, doc):
        if kind == "status":
            log(value)
        else:
            out.append(value)
    return "".join(out).strip()


ZONE_SYSTEM = (
    "Ayudas a entender una zona que el usuario marcó en un documento. Recibes el texto que se pudo leer de la zona y, si la hay, su imagen. "
    "Usa SOLO lo que hay en la zona; si la respuesta no está, dilo claramente. Responde en el idioma de la pregunta. "
    "NUNCA copies ni repitas el texto de la zona: explícalo con tus propias palabras, como se lo explicarías a alguien que no lo ha leído. "
    "Si piden «explica» o «resume» la zona: primero una frase con el tema; luego, si hay cifras, indicadores o tablas, una lista corta donde CADA cifra destacada aparece con su significado "
    "en tus palabras (por ejemplo «+18 %: las ventas crecieron 18 % frente a 2025»); al final, la idea o conclusión principal. No dejes cifras sin explicar. "
    "Si la pregunta es concreta, responde directamente a ella. Al final cita la zona con la etiqueta exacta que se te da, entre corchetes."
)


def build_zone_messages(question: str, label: str, text: str, history: list[dict], png: bytes | None = None) -> list[dict]:
    past = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    shown = text[:3000] or "(no se pudo leer texto)"
    body = f"Etiqueta para citar: [{label}]\n\nTexto leído de la zona:\n{shown}\n\nPregunta: {question}"
    user = {"role": "user", "content": body, **({"images": [png]} if png else {})}
    return [{"role": "system", "content": ZONE_SYSTEM}] + past + [user]


# ---------- preguntas sugeridas para empezar a explorar un documento ----------

def generic_questions(doc: str) -> list[str]:
    """Preguntas que sirven para cualquier documento: se usan si el modelo no logra generar otras."""
    ext = Path(doc).suffix.lower()
    if ext in VIDEO_EXT:
        return ["¿De qué trata el video?", "¿Qué se ve en las escenas principales?", "¿Qué se dice de más importante?", "¿Qué personas, lugares o cifras se mencionan?"]
    if ext in AUDIO_EXT:
        return ["¿De qué trata el audio?", "¿Cuáles son las ideas principales?", "¿Qué personas, lugares o cifras se mencionan?", "¿Qué conclusión da quien habla?"]
    return ["¿De qué trata este documento?", "¿Cuáles son los puntos principales?", "¿Qué cifras, fechas o nombres importantes aparecen?", "¿Qué conclusiones o siguientes pasos se mencionan?"]


def _suggest_prompt(items: list[tuple[int, dict]], n: int) -> str:
    material = "\n\n".join(f"[{m['loc']}]\n{re.sub(r'^\[(Frame de video|Contenido visual)\]\s*', '', m['text'])[:500]}" for _, m in items)
    return (
        f"Estas son partes de un documento. Escribe {n} preguntas cortas, en español, que alguien querría hacerle a este documento. "
        "Reglas: cada pregunta se responde con el contenido de abajo; que sean variadas (una idea principal, un dato concreto, una cifra o fecha, una persona o lugar); "
        "máximo 14 palabras; sin numerar; no digas «según el fragmento» ni «el texto»; que se entiendan solas, sin ver el documento.\n"
        'Responde SOLO con un objeto JSON con esta forma exacta: {"preguntas":["...","..."]}\n\n' + material
    )


def _parse_suggestions(raw: str, n: int) -> list[str]:
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1), max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return []
    rows = data.get("preguntas", []) if isinstance(data, dict) else data
    out, seen = [], set()
    for r in rows if isinstance(rows, list) else []:
        q = re.sub(r"^\s*\d+[.)]\s*", "", str(r)).strip()
        if not 10 <= len(q) <= 140 or q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append(q + "?" if q.startswith("¿") and not q.endswith("?") else q)
    return out[:n]


def make_suggestions(store: VectorStore, doc: str, n: int = 4) -> list[str]:
    """Preguntas para empezar, hechas por el modelo a partir de una muestra repartida del documento. Si falla, las genéricas."""
    every = _ordered(store, doc)
    step = max(1, -(-len(every) // 6))
    items = every[::step][:6]
    if not items:
        return generic_questions(doc)[:n]
    for attempt in range(2):
        try:
            qs = _parse_suggestions(llm.complete(_suggest_prompt(items, n), temperature=0.5 + 0.2 * attempt, json_mode=True), n)
        except Exception:  # noqa: BLE001  (el modelo no respondió: se usan las genéricas)
            break
        if len(qs) >= min(n, 3):
            return qs
    return generic_questions(doc)[:n]


# ---------- modo estudio: preguntas de selección múltiple ----------

def _quiz_prompt(items: list[tuple[int, dict]], question: str, n: int) -> str:
    material = "\n\n".join(f"Fragmento {k} [{m['doc']}, {m['loc']}]:\n{re.sub(r'^\[(Frame de video|Contenido visual)\]\s*', '', m['text'])[:900]}" for k, (_, m) in enumerate(items, 1))
    focus = f" El estudiante acaba de preguntar: «{question}». Prioriza ese tema." if question.strip() else ""
    return (
        f"Eres un profesor. Usando SOLO el contenido de los fragmentos, crea {n} preguntas de selección múltiple en español para que un estudiante practique.{focus}\n"
        "Reglas: cada pregunta tiene exactamente 4 opciones y solo UNA es correcta; las incorrectas deben ser plausibles pero claramente falsas según el contenido; "
        "no repitas preguntas; no uses «todas las anteriores» ni «ninguna»; la pregunta debe entenderse sola (no digas «según el fragmento»); "
        "incluye una explicación breve de por qué es correcta y el número del fragmento donde está la respuesta.\n"
        'Responde SOLO con un objeto JSON con esta forma exacta: {"preguntas":[{"pregunta":"...","opciones":["...","...","...","..."],"correcta":0,"explicacion":"...","fragmento":1}]} '
        '("correcta" es la posición, de 0 a 3, de la opción correcta).\n\n' + material
    )


def _parse_quiz(raw: str, items: list[tuple[int, dict]], rng: random.Random) -> list[dict]:
    """Interpreta la respuesta del modelo, descarta lo que no cumple las reglas y mezcla las opciones (los modelos tienden a poner la correcta primero)."""
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1), max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return []
    rows = data.get("preguntas", []) if isinstance(data, dict) else data
    out, seen = [], set()
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        q = str(r.get("pregunta", "")).strip()
        opts = [str(o).strip() for o in r.get("opciones", [])] if isinstance(r.get("opciones"), list) else []
        ok = r.get("correcta")
        if len(q) < 10 or len(opts) != 4 or len(set(o.lower() for o in opts)) != 4 or not all(opts) or not isinstance(ok, int) or isinstance(ok, bool) or not 0 <= ok <= 3:
            continue
        if q.lower() in seen:
            continue
        seen.add(q.lower())
        order = list(range(4))
        rng.shuffle(order)
        frag = r.get("fragmento")
        src = items[frag - 1] if isinstance(frag, int) and not isinstance(frag, bool) and 1 <= frag <= len(items) else None
        out.append({
            "question": q,
            "options": [opts[i] for i in order],
            "answer": order.index(ok),
            "explanation": str(r.get("explicacion", "")).strip(),
            "source": {"id": src[0], "doc": src[1]["doc"], "loc": src[1]["loc"], "kind": src[1]["kind"]} if src else None,
        })
    return out


def make_quiz(items: list[tuple[int, dict]], question: str = "", n: int = 5, rng: random.Random | None = None) -> list[dict]:
    """items: [(id_del_fragmento, fragmento)]. Devuelve preguntas de selección múltiple; reintenta una vez si el modelo respondió algo inservible."""
    rng = rng or random.Random()
    n = max(1, min(n, 10))
    quiz: list[dict] = []
    for attempt in range(2):
        raw = llm.complete(_quiz_prompt(items, question, n), temperature=0.4 + 0.2 * attempt, json_mode=True)
        quiz = _parse_quiz(raw, items, rng)
        if len(quiz) >= min(n, 2):
            break
    if not quiz:
        raise ValueError("El modelo no devolvió preguntas utilizables. Prueba de nuevo, con menos preguntas o con otro modelo.")
    return quiz[:n]


# ---------- mapa mental ----------

def _map_prompt(items: list[tuple[int, dict]], topic: str) -> str:
    material = "\n\n".join(f"Fragmento {k} [{m['doc']}, {m['loc']}]:\n{re.sub(r'^\[(Frame de video|Contenido visual)\]\s*', '', m['text'])[:600]}" for k, (_, m) in enumerate(items, 1))
    focus = f" Centra el mapa en: «{topic}»." if topic.strip() else ""
    return (
        f"Eres un experto en organizar ideas. Usando SOLO el contenido de los fragmentos, crea un MAPA MENTAL en español.{focus}\n"
        "Reglas: un título central de máximo 6 palabras; entre 3 y 6 ramas con las ideas principales; cada rama con 2 a 4 sub-ideas que incluyan datos concretos "
        "(cifras, nombres, fechas, plazos); todos los títulos cortos (máximo 8 palabras, nada de frases largas); no inventes nada; "
        "en cada sub-idea indica el número del fragmento de donde sale.\n"
        'Responde SOLO con un objeto JSON con esta forma exacta: {"titulo":"...","ramas":[{"titulo":"...","hijos":[{"titulo":"...","fragmento":1}]}]}\n\n' + material
    )


def _node(title, items, frag=None) -> dict | None:
    title = " ".join(str(title or "").split())[:90]
    if len(title) < 2:
        return None
    src = items[frag - 1] if isinstance(frag, int) and not isinstance(frag, bool) and 1 <= frag <= len(items) else None
    return {"title": title, "source": {"id": src[0], "doc": src[1]["doc"], "loc": src[1]["loc"], "kind": src[1]["kind"]} if src else None, "children": []}


def _parse_map(raw: str, items: list[tuple[int, dict]]) -> dict | None:
    """Interpreta el JSON del modelo y lo convierte en un árbol {title, source, children}; None si no sirve."""
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    root = _node(data.get("titulo") if isinstance(data, dict) else None, items)
    branches = data.get("ramas") if isinstance(data, dict) else None
    if not root or not isinstance(branches, list):
        return None
    for b in branches[:6]:
        if not isinstance(b, dict):
            continue
        node = _node(b.get("titulo"), items, b.get("fragmento"))
        if not node:
            continue
        for h in (b.get("hijos") if isinstance(b.get("hijos"), list) else [])[:5]:
            child = _node(h.get("titulo"), items, h.get("fragmento")) if isinstance(h, dict) else _node(h, items)
            if child:
                node["children"].append(child)
        root["children"].append(node)
    return root if len(root["children"]) >= 2 else None


def make_mindmap(items: list[tuple[int, dict]], topic: str = "") -> dict:
    """Mapa mental de los fragmentos como árbol; reintenta una vez si el modelo respondió algo inservible."""
    for attempt in range(2):
        tree = _parse_map(llm.complete(_map_prompt(items, topic), temperature=0.3 + 0.2 * attempt, json_mode=True), items)
        if tree:
            return tree
    raise ValueError("El modelo no devolvió un mapa utilizable. Prueba de nuevo o con otro modelo.")
