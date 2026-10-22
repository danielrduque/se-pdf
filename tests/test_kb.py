"""Base de conocimiento por carpeta y protección de embeddings, sin Ollama. Ejecutar: python tests/test_kb.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

DIM = {"n": 2}
llm.embed_docs = lambda texts, titles=None: [[1.0] * DIM["n"] for _ in texts]
llm.mm_enabled = lambda: False  # las pruebas no usan el llama-server de embeddings
llm.embed_query = lambda q: [1.0] * DIM["n"]

with tempfile.TemporaryDirectory() as tmp:
    config.DATA_DIR = Path(tmp) / "data"
    kb = Path(tmp) / "kb"
    (kb / "sub").mkdir(parents=True)
    (kb / "a.txt").write_text("Texto de la nota A sobre el proyecto.", encoding="utf-8")
    (kb / "b.md").write_text("Texto de la nota B sobre presupuestos.", encoding="utf-8")
    (kb / "sub" / "c.txt").write_text("Nota C dentro de una subcarpeta.", encoding="utf-8")
    (kb / "ignorar.xyz").write_text("formato no soportado", encoding="utf-8")

    store = VectorStore()
    s = rag.kb_scan(store, kb)
    assert sorted(p.name for p in s["new"]) == ["a.txt", "b.md", "c.txt"] and not s["ok"], s  # .xyz ignorado
    print("escaneo inicial: 3 nuevos (el .xyz se ignora)")

    # 1) primera sincronización
    r = rag.kb_sync(store, kb, False)
    assert sorted(r["indexed"]) == ["a.txt", "b.md", "c.txt"] and not r["errors"], r
    assert store.docs() == ["a.txt", "b.md", "c.txt"]
    assert all(store.info["docs"][d]["origin"] == "folder" for d in store.docs())

    # 2) sin cambios -> no reindexa nada
    r = rag.kb_sync(store, kb, False)
    assert r["indexed"] == [] and r["up_to_date"] == 3

    # 3) archivo modificado -> se reindexa solo ese; borrado -> sale del índice; nuevo -> entra
    (kb / "a.txt").write_text("Texto NUEVO de la nota A con otra informacion.", encoding="utf-8")
    (kb / "b.md").unlink()
    (kb / "d.txt").write_text("Nota D recien agregada.", encoding="utf-8")
    s = rag.kb_scan(store, kb)
    assert [p.name for p in s["changed"]] == ["a.txt"] and s["removed"] == ["b.md"] and [p.name for p in s["new"]] == ["d.txt"]
    r = rag.kb_sync(store, kb, False)
    assert sorted(r["indexed"]) == ["a.txt", "d.txt"] and r["removed"] == ["b.md"]
    assert store.docs() == ["a.txt", "c.txt", "d.txt"] and store.file_path("b.md") is None
    assert "NUEVO" in store.chunks_of("a.txt")[0]["text"]
    print("modificado / borrado / nuevo detectados y aplicados")

    # 4) un documento subido a mano NO se borra aunque no esté en la carpeta
    manual = Path(tmp) / "manual.txt"
    manual.write_text("Subido a mano por el usuario.", encoding="utf-8")
    rag.index_file(store, manual, False, lambda m: None)  # origin="upload"
    rag.kb_sync(store, kb, False)
    assert "manual.txt" in store.docs()

    # 5) nombres duplicados en subcarpetas: se avisa y no se pisan
    (kb / "sub" / "a.txt").write_text("Otro a.txt distinto", encoding="utf-8")
    s = rag.kb_scan(store, kb)
    assert [p.name for p in s["duplicates"]] == ["a.txt"]

    # 6) un archivo malo no impide indexar los demás
    (kb / "roto.pdf").write_bytes(b"esto no es un pdf")
    (kb / "e.txt").write_text("Nota E valida.", encoding="utf-8")
    r = rag.kb_sync(store, kb, False)
    assert "roto.pdf" in r["errors"] and "e.txt" in r["indexed"], r
    print("archivo roto aislado:", list(r["errors"]))

    # 7) cambiar de modelo de embeddings (otra dimensión) se detecta con un mensaje claro
    DIM["n"] = 5
    try:
        store.hybrid_search(llm.embed_query("x"), "x", 3)
        raise SystemExit("debió fallar")
    except ValueError as e:
        assert "dimensiones" in str(e)
    r = rag.kb_sync(store, kb, False)  # reindexar archivos con el modelo nuevo: la dimensión ya no cuadra
    (kb / "f.txt").write_text("Nota F.", encoding="utf-8")
    r = rag.kb_sync(store, kb, False)
    assert "f.txt" in r["errors"] and "dimensiones" in r["errors"]["f.txt"]
    for d in store.docs():
        store.delete(d)
    DIM["n"] = 5
    assert rag.index_file(store, kb / "f.txt", False, lambda m: None) == 1  # con el índice vacío ya acepta el modelo nuevo
    print("cambio de modelo de embeddings: error claro y recuperable")

    # 8) el índice y la info sobreviven a un reinicio
    assert VectorStore().info["docs"]["f.txt"]["origin"] == "upload"

    # 9) releer un documento desde su propia copia guardada NO debe borrar esa copia (defecto real encontrado con un video)
    own = store.file_path("f.txt")
    assert own is not None and rag.index_file(store, own, False, lambda m: None) == 1
    assert store.file_path("f.txt") is not None and store.docs().count("f.txt") == 1
    print("releer desde la propia copia: la copia se conserva")

print("TODO OK")
