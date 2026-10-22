"""Caché, reanudación y progreso del indexado, sin Ollama. Ejecutar: python tests/test_cache.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

calls = []
fail_on = {"n": None}


def fake_describe(img: bytes, prompt: str) -> str:
    calls.append(1)
    if fail_on["n"] is not None and len(calls) == fail_on["n"]:
        raise RuntimeError("Ollama se cayó")
    return f"Texto leido de la pagina {len(img) % 997}"


llm.describe_image = fake_describe
llm.embed_docs = lambda texts, titles=None: [[1.0, float(len(t) % 7)] for t in texts]
llm.mm_enabled = lambda: False  # las pruebas no usan el llama-server de embeddings


def scanned_pdf(path: Path, pages: int, seed: str):
    """PDF 'escaneado': cada página es solo una imagen (sin texto)."""
    src = pymupdf.open()
    out = pymupdf.open()
    for i in range(pages):
        src.new_page().insert_text((72, 100 + i), f"{seed} pagina {i}", fontsize=14 + i)
        out.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=src[i].get_pixmap(dpi=60).tobytes("png"))
    out.save(path)


with tempfile.TemporaryDirectory() as tmp:
    config.DATA_DIR = Path(tmp) / "data"
    store = VectorStore()
    a = Path(tmp) / "a.pdf"
    scanned_pdf(a, 3, "alfa")

    # 1) primera vez: analiza las 3 páginas; el progreso sube sin retroceder hasta 1.0
    seen = []
    n1 = rag.index_file(store, a, True, lambda m: None, lambda f, m: seen.append(f))
    assert len(calls) == 3, calls
    assert seen == sorted(seen) and seen[-1] == 1.0 and 0.0 <= seen[0] < 0.5, seen
    chunks1 = [c["text"] for c in store.chunks_of("a.pdf")]

    # 2) segunda vez: cero llamadas al modelo de visión y mismo resultado
    calls.clear()
    n2 = rag.index_file(store, a, True, lambda m: None)
    assert calls == [] and n2 == n1 and [c["text"] for c in store.chunks_of("a.pdf")] == chunks1
    print("reindexar: 0 llamadas a visión (caché)")

    # 3) la caché va por contenido, no por nombre: el mismo archivo con otro nombre también se salta la visión
    b = Path(tmp) / "copia_renombrada.pdf"
    b.write_bytes(a.read_bytes())
    rag.index_file(store, b, True, lambda m: None)
    assert calls == []

    # 4) reanudación: el 3er análisis falla; al reintentar solo se repite lo que faltaba
    c = Path(tmp) / "c.pdf"
    scanned_pdf(c, 3, "beta")
    calls.clear()
    fail_on["n"] = 3
    try:
        rag.index_file(store, c, True, lambda m: None)
        raise SystemExit("debió fallar")
    except RuntimeError:
        pass
    assert len(calls) == 3 and "c.pdf" not in store.docs()  # no deja un índice a medias
    calls.clear()
    fail_on["n"] = None
    rag.index_file(store, c, True, lambda m: None)
    assert len(calls) == 1, calls  # solo la página 3
    print("reanudar tras fallo: solo se repitió 1 de 3 páginas")

    # 5) sin visión no toca el modelo
    calls.clear()
    d = Path(tmp) / "d.pdf"
    scanned_pdf(d, 2, "gamma")
    try:
        rag.index_file(store, d, False, lambda m: None)
    except ValueError:
        pass  # PDF sin texto y sin visión: no hay nada que indexar
    assert calls == []

print("TODO OK")
