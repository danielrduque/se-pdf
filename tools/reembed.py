"""Recalcula los embeddings del índice (PostgreSQL) con el modelo configurado, sin volver a leer ni transcribir los archivos.

Útil al cambiar de modelo de embeddings: los vectores viejos tienen el mismo tamaño pero otro espacio, así que no sirven.
Con EmbeddingGemma 2 multimodal (proveedor «mm») también calcula el vector de la imagen o el audio ORIGINAL de cada fragmento
que lo tiene (páginas con gráficos, imágenes, fotogramas, tramos de audio), a partir de las copias de data/files.
Es atómico: primero se calculan todos los vectores nuevos y luego se sustituyen en una sola transacción.

Uso:  python tools/reembed.py [--sin-media]     (necesita el servicio si el proveedor es «mm»: run_mm.bat)
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

config.load_settings()
if problems := llm.check_backends():
    sys.exit("No se puede recalcular:\n  " + "\n  ".join(problems))
store = VectorStore()
chunks = store.all_chunks()
if not chunks:
    sys.exit("El índice está vacío: no hay nada que recalcular.")

t = time.time()
print(f"{len(chunks)} fragmentos -> {config.EMBED['model']} ({config.EMBED['backend']})")
vecs = llm.embed_docs([c["text"] for c in chunks], [c["doc"] for c in chunks])
print(f"  texto: listo en {time.time() - t:.0f} s")

media = None
if llm.mm_enabled() and "--sin-media" not in sys.argv:
    by_id: dict[int, list[float] | None] = {}
    for doc in dict.fromkeys(c["doc"] for c in chunks):
        original = store.file_path(doc)
        mine = [c for c in chunks if c["doc"] == doc]
        if original is None:
            print(f"  {doc}: no se conserva el original, solo se recalcula el texto")
            continue
        t = time.time()
        got = rag.media_vectors(original, mine, lambda m: print("   ", m))
        if got:
            by_id.update({c["id"]: v for c, v in zip(mine, got)})
            print(f"  {doc}: {sum(v is not None for v in got)} vectores de imagen/audio ({time.time() - t:.0f} s)")
    media = [by_id.get(c["id"]) for c in chunks]

store.reembed([c["id"] for c in chunks], vecs, media)
print("Listo." + (f" {sum(v is not None for v in media)} fragmentos con vector de imagen o audio propio." if media else ""))
