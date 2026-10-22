"""Embeddings multimodales: la imagen o el audio ORIGINAL de cada fragmento se embebe aparte y la búsqueda los usa.
Sin servicio real: se simula llm.embed_media. Ejecutar: python tests/test_multimodal.py"""
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pymupdf

from chatpdf import config, llm, media_io, rag
from chatpdf.store import VectorStore

# --- tiempos y páginas
assert media_io.time_range("01:34–02:22") == (94.0, 142.0) and media_io.time_range("00:48") == (48.0, None) and media_io.time_range("pág. 2") is None
assert media_io.page_number("pág. 6") == 6 and media_io.page_number("imagen") is None

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    config.DATA_DIR = tmp / "data"

    # --- un PDF de 2 páginas (la 2 tiene un gráfico), un audio de 6 s y una imagen
    pdf = tmp / "informe.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Pagina uno solo con texto normal " * 4)
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Pagina dos con un grafico")
    p2.draw_rect(pymupdf.Rect(100, 150, 300, 300), fill=(1, 0, 0))
    doc.save(pdf)
    doc.close()
    wav = tmp / "voz.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.sin(np.linspace(0, 6 * 440 * 6.28, 16000 * 6)) * 12000).astype("<i2").tobytes())
    seg = media_io.audio_segment(wav, 1, 4)
    assert seg.dtype == np.float32 and abs(len(seg) - 3 * 16000) < 400, len(seg)  # 3 s a 16 kHz
    assert media_io.audio_segment(wav, 50, 60) is None  # más allá del final

    # --- media_vectors: solo los fragmentos con imagen/audio, y una página con varios fragmentos se embebe una vez
    calls = []
    def fake_media(items):
        calls.append([("image" if "image" in i else "audio") for i in items])
        return [[1.0, 0.0] if "image" in i else [0.0, 1.0] for i in items]
    real = (llm.mm_enabled, llm.embed_media)
    llm.mm_enabled, llm.embed_media = (lambda: True), fake_media
    pdf_chunks = [
        {"text": "texto de la pagina 1", "loc": "pág. 1", "kind": "texto"},
        {"text": "[Contenido visual] barras rojas", "loc": "pág. 2", "kind": "visión"},
        {"text": "[Contenido visual] mas detalle del grafico", "loc": "pág. 2", "kind": "visión"},
    ]
    mv = rag.media_vectors(pdf, pdf_chunks)
    assert mv[0] is None and mv[1] == [1.0, 0.0] and mv[2] == [1.0, 0.0], mv
    assert calls == [["image"]], calls  # la página 2 se embebió UNA vez aunque tenga dos fragmentos
    mv = rag.media_vectors(wav, [{"text": "hola", "loc": "00:01–00:04", "kind": "audio"}, {"text": "sin tiempo", "loc": "texto", "kind": "audio"}])
    assert mv == [[0.0, 1.0], None], mv
    assert rag.media_vectors(pdf, pdf_chunks[:1]) is None  # nada que embeber
    llm.mm_enabled = lambda: False
    assert rag.media_vectors(pdf, pdf_chunks) is None  # con otro proveedor de embeddings no hay vectores multimedia
    llm.mm_enabled, llm.embed_media = real

    # --- el vector de la imagen/audio entra por una ranura: aparece aunque su descripción no tenga nada que ver con la pregunta
    store = VectorStore()
    chunks = [{"text": f"Texto numero {i} sobre otro tema.", "loc": f"pág. {i}", "kind": "texto"} for i in range(4)]
    chunks.append({"text": "Descripcion generica de una imagen cualquiera.", "loc": "imagen", "kind": "visión"})
    text_vecs = [[0.6, 0.8, 0.0], [0.5, 0.8, 0.3], [0.4, 0.8, 0.4], [0.3, 0.9, 0.3], [0.0, 1.0, 0.0]]  # el de la imagen es el que menos se parece
    media = [None, None, None, None, [1.0, 0.0, 0.0]]  # pero la imagen original sí coincide con la pregunta [1, 0, 0]
    store.add("foto.png", chunks, text_vecs, media=media)
    hits = store.hybrid_search([1.0, 0.0, 0.0], "palabras que no aparecen en ningun lado", 3)
    assert [h["loc"] for h in hits[:2]] == ["pág. 0", "pág. 1"], [h["loc"] for h in hits]  # el texto manda en las primeras posiciones
    assert hits[2]["loc"] == "imagen" and hits[2]["via"] == "media" and hits[2]["mm_score"] > 0.99, hits[2]  # y la imagen entra por su ranura
    assert all(h["via"] == "texto" for h in hits[:2])
    store.add("foto.png", chunks, text_vecs)  # volver a leerlo sin vectores multimedia los quita
    assert all(h["via"] == "texto" for h in store.hybrid_search([1.0, 0.0, 0.0], "nada", 3))
    try:
        store.add("x.png", chunks, text_vecs, media=[None])
        raise AssertionError("debía rechazar una lista de vectores multimedia de otro largo")
    except ValueError:
        pass
    ids = [c["id"] for c in store.all_chunks()]
    store.reembed(ids, text_vecs, media)  # reembed con vectores multimedia
    assert store.hybrid_search([1.0, 0.0, 0.0], "nada", 3)[2]["via"] == "media"

    # --- REGRESIÓN (hallazgo de QA): los fragmentos multimedia que NO vienen al caso no desplazan al texto correcto.
    # La similitud pregunta<->imagen es alta aunque no tengan nada que ver; como ranking en la RRF, 30 imágenes irrelevantes sacaban el texto del top.
    for d in store.docs():  # índice limpio: ahora con vectores de 4 dimensiones
        store.delete(d)
    noise_chunks = [{"text": f"Descripcion visual numero {i} de otra cosa.", "loc": f"pág. {i}", "kind": "visión"} for i in range(30)]
    store.add("ruido.pdf", noise_chunks, [[0.0, 0.0, 1.0, 0.0]] * 30, media=[[0.5, 0.866, 0.0, 0.0]] * 30)  # coseno 0,5 con la pregunta: bajo el umbral
    store.add("manual.pdf", [{"text": "El codigo XJ-4471 identifica la falla del reactor.", "loc": "pág. 1", "kind": "texto"}], [[0.3, 0.9, 0.0, 0.0]])
    q = [1.0, 0.0, 0.0, 0.0]
    hits = store.hybrid_search(q, "codigo XJ-4471", 6)
    assert hits[0]["doc"] == "manual.pdf" and all(h["via"] == "texto" for h in hits), [(h["doc"], h["loc"], h["via"]) for h in hits]
    # aunque TODOS los fragmentos multimedia pasen el umbral (como los fotogramas de un video), el texto conserva k-1 lugares
    store.add("video.mp4", [{"text": f"[Frame de video] escena {i}", "loc": f"00:{i:02d}", "kind": "visión"} for i in range(10)], [[0.0, 0.0, 1.0, 0.0]] * 10, media=[[0.9, 0.436, 0.0, 0.0]] * 10)
    hits = store.hybrid_search(q, "codigo XJ-4471", 6)
    assert hits[0]["doc"] == "manual.pdf" and sum(h["via"] == "media" for h in hits) <= config.MM_SLOTS, [(h["doc"], h["loc"], h["via"]) for h in hits]
    assert sum(1 for h in hits if h["via"] == "media") == 1 and hits[-1]["via"] == "media" and hits[-1]["mm_score"] > 0.85
    print("vectores multimedia: extracción, guardado y búsqueda OK")
# --- llm.embed_media habla con llama-server: partes de contenido {"content": [...]} en /v1/embeddings (sin servicio real: httpx simulado)
import json  # noqa: E402

posted = []
class FakeResp:
    def __init__(self, code=200): self.status_code = code
    def raise_for_status(self):
        if self.status_code != 200: raise RuntimeError("HTTP " + str(self.status_code))
    def json(self): return {"data": [{"embedding": [0.1] * 768}]}
real_post = llm.httpx.post
def fake_post(url, json=None, timeout=None):
    posted.append((url, json))
    return FakeResp(500 if len(posted) == 3 else 200)  # el tercero falla: solo ese queda en None
llm.httpx.post = fake_post
config.EMBED.update(backend="llamacpp", model="embeddinggemma-2", base_url="http://127.0.0.1:8081/v1")
png = pymupdf.open().new_page().get_pixmap(dpi=20).tobytes("png")
res = llm.embed_media([{"image": png}, {"audio": np.zeros(16000, dtype=np.float32)}, {"image": png}])
llm.httpx.post = real_post
assert [r is not None for r in res] == [True, True, False], res
url, body = posted[0]
assert url == "http://127.0.0.1:8081/v1/embeddings" and body["model"] == "embeddinggemma-2"
part = body["input"][0]["content"][0]
assert part["type"] == "image_url" and part["image_url"]["url"].startswith("data:image/png;base64,"), part
apart = posted[1][1]["input"][0]["content"][0]
assert apart["type"] == "input_audio" and apart["input_audio"]["format"] == "wav", apart
import base64, io  # noqa: E402
with wave.open(io.BytesIO(base64.b64decode(apart["input_audio"]["data"]))) as w:  # un WAV válido de 1 s a 16 kHz mono
    assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16000, 1, 16000)
# mm_enabled depende de los módulos que anuncie el servidor (--mmproj) y solo existe con llama.cpp
llm._props.clear()
llm.httpx.get = lambda url, timeout=None: type("R", (), {"json": lambda self: {"modalities": {"vision": True, "audio": True}}})()
assert llm.mm_enabled()
llm._props.clear()
llm.httpx.get = lambda url, timeout=None: type("R", (), {"json": lambda self: {"modalities": {}}})()
assert not llm.mm_enabled()  # servidor arrancado sin --mmproj: solo texto
config.EMBED.update(backend="ollama")
llm._props.clear()
assert not llm.mm_enabled()
print("llama.cpp: partes de contenido de imagen y audio, WAV y detección de módulos OK")
print("TODO OK")
