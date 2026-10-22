"""Búsqueda híbrida (BM25 + vectores) y reranking, sin Ollama. Ejecutar: python tests/test_retrieval.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore, tokenize

assert tokenize("Bogotá, ÁRBOL 2027 x") == ["bogota", "arbol", "2027"]

rng = np.random.default_rng(0)
with tempfile.TemporaryDirectory() as tmp:
    config.DATA_DIR = Path(tmp) / "data"
    store = VectorStore()
    # 40 fragmentos con vectores ALEATORIOS: la búsqueda vectorial no sirve, solo BM25 puede acertar
    chunks = [{"text": f"Informe generico numero {i} sobre temas varios de la empresa.", "loc": f"pág. {i}", "kind": "texto"} for i in range(40)]
    chunks[27]["text"] = "El equipo de soporte uso el codigo XJ-4471 para identificar la falla del reactor."
    store.add("manual.pdf", chunks, rng.normal(size=(40, 32)).tolist())
    store.add("otro.pdf", [{"text": "Codigo XJ-4471 aparece tambien aqui.", "loc": "pág. 1", "kind": "texto"}], rng.normal(size=(1, 32)).tolist())

    qvec = rng.normal(size=32).tolist()
    hits = store.hybrid_search(qvec, "codigo XJ-4471", 5)
    assert {h["doc"] for h in hits[:2]} == {"manual.pdf", "otro.pdf"} and "XJ-4471" in hits[0]["text"], hits[:2]
    print("hibrida encuentra el codigo exacto:", hits[0]["doc"], hits[0]["loc"])

    # filtro por documento
    only = store.hybrid_search(qvec, "codigo XJ-4471", 5, docs=["otro.pdf"])
    assert {h["doc"] for h in only} == {"otro.pdf"}

    # sin coincidencias léxicas -> solo vectores, no revienta
    assert len(store.hybrid_search(qvec, "zzzz qqqq", 5)) == 5

    # tras borrar, el índice BM25 se reconstruye
    store.delete("otro.pdf")
    assert all(h["doc"] == "manual.pdf" for h in store.hybrid_search(qvec, "codigo XJ-4471", 5))

# --- reranking ---
cands = [{"text": f"fragmento {i}", "loc": f"p{i}", "doc": "d"} for i in range(1, 11)]
q = "pregunta"

llm.complete = lambda prompt, temperature=0.2: "Los mejores son 4, 2 y 9."
assert [h["loc"] for h in rag.rerank(q, cands, k=6)] == ["p4", "p2", "p9"]

llm.complete = lambda prompt, temperature=0.2: "4, 4, 99, 0, 7"  # duplicados y fuera de rango
assert [h["loc"] for h in rag.rerank(q, cands, k=6)] == ["p4", "p7", "p1"]  # rellena hasta min_keep=3

llm.complete = lambda prompt, temperature=0.2: "no sé"  # ilegible -> orden original
assert [h["loc"] for h in rag.rerank(q, cands, k=4)] == ["p1", "p2", "p3", "p4"]

assert rag.rerank(q, cands[:3], k=6) == cands[:3]  # pocos candidatos: sin llamar al LLM
print("TODO OK")
