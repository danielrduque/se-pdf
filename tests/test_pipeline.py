"""Prueba el pipeline completo sin Ollama (llm simulado). Ejecutar: python tests/test_pipeline.py"""
import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pymupdf

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

DIM = 64


def fake_vec(text: str) -> list[float]:
    # Embedding "bolsa de palabras" con hashing: textos con palabras comunes quedan cerca
    v = np.zeros(DIM)
    for w in text.lower().split():
        v[int(hashlib.md5(w.strip(".,:;?¿").encode()).hexdigest(), 16) % DIM] += 1
    return v.tolist()


llm.embed_docs = lambda texts, titles=None: [fake_vec(t) for t in texts]
llm.mm_enabled = lambda: False  # las pruebas no usan el llama-server de embeddings
llm.embed_query = fake_vec
llm.describe_image = lambda img, prompt: "Grafico de barras con ventas por trimestre"
llm.complete = lambda prompt, temperature=0.2: "RESUMEN(" + str(len(prompt)) + ")"
llm.chat_stream = lambda messages: iter(["RESUMEN(", str(len(messages[-1]["content"])), ")"])  # el resumen final se escribe en streaming

with tempfile.TemporaryDirectory() as tmp:
    config.DATA_DIR = Path(tmp) / "data"
    pdf_path = Path(tmp) / "demo.pdf"
    doc = pymupdf.open()
    pages = [
        "El ocelote es un felino que vive en las selvas de America. Caza de noche y come roedores.",
        "La fotosintesis convierte luz solar en energia quimica dentro de los cloroplastos de las plantas.",
        "",  # pagina "escaneada" sin texto -> debe ir a vision
    ]
    for t in pages:
        doc.new_page().insert_text((72, 72), t, fontsize=11)
    doc.save(pdf_path)

    store = VectorStore()
    logs = []
    n = rag.index_file(store, pdf_path, True, logs.append)
    print("fragmentos:", n, "| docs:", store.docs())
    assert n >= 3 and any(c["kind"] == "visión" for c in store.chunks_of("demo.pdf"))

    hits = rag.retrieve(store, "que come el ocelote?")
    print("top hit:", hits[0]["loc"], "-", hits[0]["text"][:60])
    assert hits[0]["loc"] == "pág. 1"
    hits = rag.retrieve(store, "como funciona la fotosintesis en las plantas")
    assert hits[0]["loc"] == "pág. 2"

    # persistencia
    store2 = VectorStore()
    assert store2.docs() == ["demo.pdf"] and store2.chunk_count() == n

    msgs = rag.build_messages("hola", hits, [])
    assert msgs[0]["role"] == "system" and "demo.pdf" in msgs[-1]["content"]
    assert rag.summarize(store, "demo.pdf").startswith("RESUMEN")

    store.delete("demo.pdf")
    assert store.docs() == [] and VectorStore().docs() == []

print("TODO OK")
