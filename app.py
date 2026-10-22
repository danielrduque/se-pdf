import os
import tempfile
import time
from pathlib import Path

import streamlit as st

from chatpdf import config, llm, rag, viewer
from chatpdf.ingest import AUDIO_EXT, IMG_EXT, VIDEO_EXT
from chatpdf.store import VectorStore, db_problem

st.set_page_config(page_title=config.APP_NAME, page_icon="📄", layout="wide")
config.load_settings()

# Modelo y URL sugeridos al cambiar de proveedor: (rol, proveedor) -> (modelo, url)
PRESETS = {
    ("chat", "ollama"): ("gemma3:4b", ""),
    ("chat", "llamacpp"): ("local", ""),
    ("chat", "openai"): ("gpt-4o-mini", ""),
    ("embed", "ollama"): ("embeddinggemma-2:740m", ""),
    ("embed", "llamacpp"): ("embeddinggemma-2", "http://127.0.0.1:8081/v1"),
    ("embed", "openai"): ("text-embedding-3-small", ""),
}


@st.cache_resource
def get_store() -> VectorStore:
    return VectorStore()


@st.cache_data(show_spinner=False, max_entries=64)
def cached_page(pdf_path: str, mtime: float, page: int, text: str):
    return viewer.render_page(pdf_path, page, text)


def show_sources(sources: list[dict]):
    """Cada fuente con su evidencia: página del PDF resaltada, o audio/video en el segundo citado."""
    for n, h in enumerate(sources):
        st.markdown(f"**{h['doc']} · {h['loc']}** ({h['kind']}, similitud {h['score']:.2f})")
        path = store.file_path(h["doc"])
        loc = viewer.parse_loc(h["loc"])
        if path and n < 3:  # solo las 3 primeras, para que la página no se haga pesada
            ext = path.suffix.lower()
            if loc and loc[0] == "page" and ext == ".pdf":
                png, found = cached_page(str(path), path.stat().st_mtime, loc[1], h["text"])
                st.image(png, caption=None if found else "Sin texto que resaltar (página leída por visión)")
            elif loc and loc[0] == "time" and ext in AUDIO_EXT:
                st.audio(str(path), start_time=loc[1])
            elif loc and loc[0] == "time" and ext in VIDEO_EXT:
                st.video(str(path), start_time=loc[1])
            elif ext in IMG_EXT:
                st.image(str(path))
        st.caption(h["text"][:400])


def model_picker(role: str, label: str, cfg: dict):
    names = list(config.BACKENDS)

    def on_change():  # al cambiar de proveedor, proponer un modelo coherente
        model, url = PRESETS[(role, st.session_state[f"{role}_backend"])]
        st.session_state[f"{role}_model"], st.session_state[f"{role}_url"] = model, url

    for suffix, value in (("backend", cfg["backend"]), ("model", cfg["model"]), ("url", cfg["base_url"])):
        st.session_state.setdefault(f"{role}_{suffix}", value)  # valor inicial vía estado, no vía argumento del widget
    cfg["backend"] = st.selectbox(
        f"{label}: proveedor", names, key=f"{role}_backend",
        format_func=lambda k: config.BACKENDS[k]["label"], on_change=on_change,
    )
    help_text = (
        "Puedes poner varios separados por coma (a, b, c): se prueban en orden y se salta al siguiente si uno falla."
        if role == "chat" else "Un solo modelo: mezclar modelos de embeddings rompería el índice."
    )
    cfg["model"] = st.text_input(f"{label}: modelo", key=f"{role}_model", help=help_text)
    cfg["base_url"] = st.text_input(
        f"{label}: URL (vacío = por defecto)", key=f"{role}_url",
        placeholder=config.BACKENDS[cfg["backend"]]["default_url"],
    )


def model_settings():
    with st.expander("⚙️ Modelos", expanded=st.session_state.get("had_problems", False)):
        model_picker("chat", "Chat y visión", config.CHAT)
        model_picker("embed", "Embeddings", config.EMBED)
        if "openai" in (config.CHAT["backend"], config.EMBED["backend"]):
            st.session_state.setdefault("api_key", config.CHAT["api_key"])
            key = st.text_input("API key", type="password", key="api_key", help="No se guarda en disco. También puedes definir CHATPDF_API_KEY.")
            config.CHAT["api_key"] = config.EMBED["api_key"] = key
            st.warning("Con una API en la nube, tus preguntas y el contenido de los archivos se envían a ese proveedor.")
    config.save_settings()


with st.sidebar:
    st.title(f"📄 {config.APP_NAME}")
    model_settings()

problems = ([db_problem()] if db_problem() else []) + llm.check_backends()
st.session_state["had_problems"] = bool(problems)
if problems:
    st.error("Falta preparar la base de datos o los modelos:")
    for p in problems:
        st.markdown(f"- {p}")
    st.info("Corrígelo (o cambia de proveedor en ⚙️ Modelos, a la izquierda) y la página se actualizará sola.")
    st.stop()

store = get_store()
if "history" not in st.session_state:
    st.session_state.history = []


def cancel_button():
    # Pulsar Cancelar relanza la app y corta el bucle en la siguiente actualización de pantalla
    st.button("⏹ Cancelar", on_click=lambda: st.session_state.update(cancelled=True))


def eta_text(t0: float, frac: float) -> str:
    return f" · ~{int((time.time() - t0) / frac * (1 - frac))} s restantes" if frac > 0.05 else ""


with st.sidebar:
    cloud = "openai" in (config.CHAT["backend"], config.EMBED["backend"])
    st.caption(f"Chat: `{config.CHAT['model']}` · Embeddings: `{config.EMBED['model']}` · " + ("☁️ usa la nube" if cloud else "todo en tu PC"))
    use_vision = st.checkbox("Analizar imágenes/gráficos (más lento)", value=True)
    use_rerank = st.checkbox("Reranking (para documentos muy grandes, +5 s por pregunta)", value=False)
    lang = st.selectbox("Idioma del audio/video", ["Autodetectar", "Español", "English"])
    config.WHISPER_LANG = {"Autodetectar": None, "Español": "es", "English": "en"}[lang]
    if st.session_state.pop("cancelled", False):
        st.warning("Proceso cancelado. Lo ya analizado queda en caché: al volver a procesar continúa donde quedó.")

    # ---- subir archivos sueltos ----
    st.subheader("Subir archivos")
    files = st.file_uploader(
        "PDF, imágenes, audio, video o texto",
        accept_multiple_files=True,
        type=[e.lstrip(".") for e in sorted(rag.SUPPORTED_EXT)],
        label_visibility="collapsed",
    )
    if st.button("Procesar archivos", type="primary", disabled=not files):
        cancel_button()
        for f in files:
            with st.status(f"Procesando {f.name}…", expanded=True) as status:
                bar = st.progress(0.0, text="Empezando…")
                t0 = time.time()

                def on_progress(frac: float, msg: str):
                    bar.progress(min(frac, 1.0), text=f"{msg}{eta_text(t0, frac)}")

                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / f.name
                    path.write_bytes(f.getbuffer())
                    try:
                        n = rag.index_file(store, path, use_vision, lambda _m: None, on_progress)
                        status.update(label=f"{f.name}: {n} fragmentos ({time.time() - t0:.0f} s)", state="complete")
                    except Exception as e:
                        status.update(label=f"{f.name}: error — {e}", state="error")

    # ---- base de conocimiento (carpeta) ----
    st.subheader("📁 Base de conocimiento")
    config.KB_DIR.mkdir(exist_ok=True)
    st.caption(f"Pon tus PDFs, audios y videos en `{config.KB_DIR}` y sincroniza.")
    scan = rag.kb_scan(store, config.KB_DIR)
    pending = len(scan["new"]) + len(scan["changed"])
    st.write(f"{len(scan['ok'])} al día · {pending} por indexar · {len(scan['removed'])} borrados de la carpeta")
    if scan["duplicates"]:
        st.warning("Hay archivos con el mismo nombre en subcarpetas; solo se indexa el primero: " + ", ".join(p.name for p in scan["duplicates"]))
    c1, c2 = st.columns(2)
    if hasattr(os, "startfile") and c2.button("Abrir carpeta"):
        os.startfile(config.KB_DIR)
    if c1.button("Sincronizar", type="primary", disabled=not (pending or scan["removed"])):
        cancel_button()
        with st.status("Sincronizando carpeta…", expanded=True) as status:
            bar = st.progress(0.0, text="Empezando…")
            t0, cur = time.time(), {"i": 1, "n": 1, "name": ""}

            def on_file(p: Path, i: int, n: int):
                cur.update(i=i, n=n, name=p.name)

            def on_progress(frac: float, msg: str):
                total = (cur["i"] - 1 + frac) / cur["n"]
                bar.progress(min(total, 1.0), text=f"[{cur['i']}/{cur['n']}] {cur['name']}: {msg}{eta_text(t0, total)}")

            result = rag.kb_sync(store, config.KB_DIR, use_vision, on_file=on_file, progress=on_progress)
            ok = not result["errors"]
            status.update(
                label=f"{len(result['indexed'])} indexados · {len(result['removed'])} quitados · {len(result['errors'])} con error ({time.time() - t0:.0f} s)",
                state="complete" if ok else "error",
            )
        for name, err in result["errors"].items():
            st.error(f"{name}: {err}")
        if ok:
            st.rerun()

    # ---- documentos indexados ----
    st.divider()
    docs, info = store.docs(), store.info["docs"]
    selected = st.multiselect("Buscar en", docs, default=docs)
    for d in docs:
        c1, c2 = st.columns([4, 1])
        c1.write(("📁 " if info.get(d, {}).get("origin") == "folder" else "") + d)
        if c2.button("🗑", key=f"del_{d}"):
            store.delete(d)
            st.rerun()
    if docs:
        st.divider()
        to_sum = st.selectbox("Resumir documento completo", docs)
        if st.button("Resumir"):
            with st.spinner("Resumiendo todo el documento…"):
                summary = rag.summarize(store, to_sum)
            st.session_state.history += [
                {"role": "user", "content": f"Resumen de {to_sum}"},
                {"role": "assistant", "content": summary},
            ]
    if st.button("Limpiar chat"):
        st.session_state.history = []
        st.rerun()

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("sources"):
            with st.expander("Fuentes"):
                show_sources(m["sources"])


if q := st.chat_input("Pregunta algo sobre tus archivos…", disabled=not selected):
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Buscando en tus archivos…"):
                hits = rag.retrieve(store, rag.standalone_question(q, st.session_state.history), selected, use_rerank=use_rerank)
        except ValueError as e:  # p. ej. cambiaste de modelo de embeddings
            st.error(str(e))
            st.stop()
        answer = st.write_stream(llm.chat_stream(rag.build_messages(q, hits, st.session_state.history)))
    st.session_state.history += [
        {"role": "user", "content": q},
        {"role": "assistant", "content": answer, "sources": hits},
    ]
    st.rerun()
