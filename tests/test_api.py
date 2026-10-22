"""API web (FastAPI) con modelos simulados. Ejecutar: python tests/test_api.py"""
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pymupdf
from fastapi.testclient import TestClient

from chatpdf import config, llm

tmp = Path(tempfile.mkdtemp())
config.DATA_DIR, config.KB_DIR = tmp / "data", tmp / "kb"
config.KB_DIR.mkdir()

DELAY = {"s": 0.0}


def fake_vec(text: str) -> list[float]:
    v = np.zeros(64)
    for w in text.lower().split():
        v[int(hashlib.md5(w.strip(".,:;?¿").encode()).hexdigest(), 16) % 64] += 1
    return v.tolist()


llm.check_backends = lambda: []
llm.embed_docs = lambda texts, titles=None: (time.sleep(DELAY["s"]), [fake_vec(t) for t in texts])[1]
llm.mm_enabled = lambda: False  # las pruebas no usan el llama-server de embeddings
llm.embed_query = fake_vec
llm.describe_image = lambda img, prompt: "texto de imagen"
llm.complete = lambda prompt, temperature=0.2: "pregunta reescrita sobre el ocelote"
llm.last_model["chat"] = "modelo-falso"


def fake_stream(messages):
    ctx = messages[-1]["content"]
    for tok in ("Respuesta ", "basada ", "en ", "el ", "contexto: ", "ocelote" if "ocelote" in ctx.lower() else "nada"):
        yield tok


llm.chat_stream = fake_stream

from server import main as srv  # noqa: E402  (después de fijar DATA_DIR/KB_DIR)

client = TestClient(srv.app)


def wait(job_id, timeout=20):
    t = time.time()
    while time.time() - t < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["state"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.05)
    raise SystemExit("el trabajo no terminó")


def events(resp):
    out, cur = [], {}
    for line in resp.text.splitlines():
        if line.startswith("event: "):
            cur = {"event": line[7:]}
        elif line.startswith("data: "):
            cur["data"] = json.loads(line[6:])
            out.append(cur)
    return out


# 1) estado inicial
st = client.get("/api/status").json()
assert st["problems"] == [] and st["docs"] == [] and "openai" in st["backends"] and "api_key" not in json.dumps(st)
print("status OK")

# 2) subida de un PDF y de un texto; el PDF se usa luego para las evidencias
pdf = pymupdf.open()
pg = pdf.new_page()
pg.insert_text((72, 100), "El ocelote es un felino que vive en las selvas de America.", fontsize=12)
pg.insert_text((72, 120), "Caza de noche y come roedores pequenos.", fontsize=12)
pdf.new_page().insert_text((72, 100), "La fotosintesis ocurre en los cloroplastos de las plantas.", fontsize=12)
pdf_path = tmp / "animales.pdf"
pdf.save(pdf_path)
r = client.post("/api/upload", files=[("files", ("animales.pdf", pdf_path.read_bytes(), "application/pdf")),
                                      ("files", ("nota.txt", "Nota sobre el presupuesto del proyecto Colibri.".encode(), "text/plain"))], data={"use_vision": "false"})
assert r.status_code == 200, r.text
job = wait(r.json()["id"])
assert job["state"] == "done" and job["progress"] == 1.0 and job["done"] == 2, job
assert set(job["result"]) == {"animales.pdf", "nota.txt"} and "chunks" in job["result"]["animales.pdf"]
docs = client.get("/api/docs").json()
assert {d["name"] for d in docs} == {"animales.pdf", "nota.txt"}, docs
print("subida OK:", {d["name"]: d["chunks"] for d in docs})

# 3) formato no soportado
r = client.post("/api/upload", files=[("files", ("virus.exe", b"x", "application/octet-stream"))])
assert r.status_code == 400 and "no soportado" in r.text.lower()

# 4) chat por SSE: fuentes -> tokens -> done
r = client.post("/api/chat", json={"question": "¿qué come el ocelote?", "history": []})
ev = events(r)
kinds = [e["event"] for e in ev]
assert kinds[0] == "sources" and kinds[-1] == "done" and kinds.count("token") >= 3, kinds
sources = ev[0]["data"]
assert sources[0]["doc"] == "animales.pdf" and sources[0]["loc"] == "pág. 1" and "id" in sources[0], sources[0]
answer = "".join(e["data"]["t"] for e in ev if e["event"] == "token")
assert "ocelote" in answer and ev[-1]["data"]["model"] == "modelo-falso"
print("chat SSE OK:", answer)

# 4b) pregunta global: lee TODO el documento (con estado de avance) y sus fuentes no llevan "similitud"
ev = events(client.post("/api/chat", json={"question": "hazme un resumen del documento animales.pdf"}))
kinds = [e["event"] for e in ev]
assert kinds[0] == "sources" and "status" in kinds and kinds[-1] == "done", kinds
assert all(s["score"] is None and s["doc"] == "animales.pdf" for s in ev[0]["data"])
assert "ocelote" in "".join(e["data"]["t"] for e in ev if e["event"] == "token")
print("pregunta global OK")

# 5) chat con historial (usa la reescritura) y con filtros de documentos
r = client.post("/api/chat", json={"question": "¿y de qué se alimenta?", "history": [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola", "sources": []}], "docs": ["animales.pdf"]})
assert {s["doc"] for s in events(r)[0]["data"]} == {"animales.pdf"}
assert events(client.post("/api/chat", json={"question": "x", "docs": []}))[0]["event"] == "error"

# 6) evidencias: página resaltada y archivo original con Range
r = client.get(f"/api/page/animales.pdf/1?chunk={sources[0]['id']}")
assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n" and r.headers["content-type"] == "image/png"
assert client.get("/api/page/animales.pdf/99").status_code == 404
assert client.get("/api/page/nota.txt/1").status_code == 404
r = client.get("/api/files/animales.pdf", headers={"Range": "bytes=0-9"})
assert r.status_code == 206 and len(r.content) == 10, (r.status_code, len(r.content))
assert client.get("/api/files/..").status_code in (400, 404) and client.get("/api/files/inexistente.pdf").status_code == 404
print("página resaltada y Range OK")

# 6b) contenido leído de un documento (lo usa el visor) y resolución de las páginas
c1 = client.get("/api/docs/animales.pdf/content").json()
assert c1["pages"] == 2 and c1["ext"] == "pdf" and [c["loc"] for c in c1["chunks"]][0] == "pág. 1" and all("id" in c and c["text"] for c in c1["chunks"])
assert client.get("/api/docs/nota.txt/content").json()["pages"] is None
assert client.get("/api/docs/inexistente.pdf/content").status_code == 404
small = client.get("/api/page/animales.pdf/1?dpi=60").content
big = client.get("/api/page/animales.pdf/1?dpi=150").content
assert len(big) > len(small) and client.get("/api/page/animales.pdf/1?dpi=99999").status_code == 200  # el dpi se limita
print("contenido leído y dpi OK")

# 6c) video que el navegador no reproduce (HEVC de TikTok, MPEG-4…): el servidor prepara una copia H.264 y la sirve en su lugar
import av  # noqa: E402
from chatpdf import media  # noqa: E402


def make_clip(path, codec):
    out = av.open(str(path), "w")
    v = out.add_stream(codec, rate=10)
    v.width, v.height, v.pix_fmt = 160, 90, "yuv420p"
    for i in range(20):
        for pkt in v.encode(av.VideoFrame.from_ndarray(np.full((90, 160, 3), i * 10, np.uint8), format="rgb24")):
            out.mux(pkt)
    for pkt in v.encode():
        out.mux(pkt)
    out.close()


def poll_playback(name, force=False):
    for _ in range(150):
        r = client.get(f"/api/docs/{name}/playback" + ("?force=true" if force else "")).json()
        if r["state"] in ("ready", "original", "error"):
            return r
        time.sleep(0.1)
    raise SystemExit("la copia no terminó")


bad, good = tmp / "tiktok.mp4", tmp / "normal.mp4"
make_clip(bad, "mpeg4")
make_clip(good, "libx264")
for name, f in (("tiktok.mp4", bad), ("normal.mp4", good)):
    srv.get_store().add(name, [{"text": "escena", "loc": "00:00", "kind": "visión"}], [fake_vec("escena")])
    srv.get_store().save_file(f)

first = client.get("/api/docs/tiktok.mp4/playback").json()
assert first["state"] in ("converting", "ready") and "MPEG-4" in first["reason"], first
assert first["url"] == "/api/files/tiktok.mp4"
done = poll_playback("tiktok.mp4")
assert done["state"] == "ready", done
served = tmp / "servido.mp4"
served.write_bytes(client.get("/api/files/tiktok.mp4").content)
assert media.inspect(served)["vcodec"] == "h264", media.inspect(served)  # al navegador le llega la copia H.264
assert media.inspect(srv.get_store().file_path("tiktok.mp4"))["vcodec"] == "mpeg4"  # y el original queda intacto
assert client.get("/api/files/tiktok.mp4", headers={"Range": "bytes=0-9"}).status_code == 206
assert poll_playback("normal.mp4")["state"] == "original"  # un H.264 normal no se toca
assert client.get("/api/docs/normal.mp4/playback?force=true").json()["state"] in ("converting", "ready")  # si el navegador no muestra la imagen, se fuerza la copia
assert poll_playback("normal.mp4", force=True)["state"] == "ready"
assert client.get("/api/docs/animales.pdf/playback").status_code == 404 and client.get("/api/docs/nada.mp4/playback").status_code == 404
preview = media.preview_path(srv.get_store().file_path("tiktok.mp4"))
assert preview.exists()
assert client.delete("/api/docs/tiktok.mp4").status_code == 200 and not preview.exists()  # al quitar el documento se borra su copia
client.delete("/api/docs/normal.mp4")
print("video no reproducible: copia H.264 OK")

# 6d) varias citas a la vez (?chunk=a&chunk=b) y filtrado por página
meta = srv.get_store().chunks_of("animales.pdf")
ids1 = [m["id"] for m in meta if m["loc"] == "pág. 1"]
ids2 = [m["id"] for m in meta if m["loc"] == "pág. 2"]
plain = client.get("/api/page/animales.pdf/1").content
one = client.get(f"/api/page/animales.pdf/1?chunk={ids1[0]}").content
both = client.get(f"/api/page/animales.pdf/1?chunk={ids1[0]}&chunk={ids2[0]}").content
assert one != plain  # con una cita, la página sale con resaltado
assert one == both  # el fragmento de la página 2 NO se pinta en la página 1
assert client.get(f"/api/page/animales.pdf/1?chunk=999999&chunk=-3").content == plain  # índices inválidos se ignoran
assert client.get(f"/api/page/nota.txt/1?chunk={ids1[0]}").status_code == 404
print("varias citas y filtrado por página OK")

# 6e) modo estudio: preguntas de selección múltiple (con el modelo simulado y restaurándolo al terminar)
real_complete = llm.complete
llm.complete = lambda prompt, temperature=0.2, json_mode=False: json.dumps({"preguntas": [{"pregunta": "¿De qué se alimenta el ocelote?", "opciones": ["Roedores", "Plantas", "Peces", "Insectos"], "correcta": 0, "explicacion": "Caza de noche y come roedores.", "fragmento": 1}]})
ids = [m["id"] for m in srv.get_store().chunks_of("animales.pdf")]
qz = client.post("/api/quiz", json={"chunks": ids, "question": "ocelote", "n": 3}).json()["questions"]
assert len(qz) == 1 and qz[0]["options"][qz[0]["answer"]] == "Roedores" and qz[0]["source"]["doc"] == "animales.pdf" and qz[0]["source"]["loc"].startswith("pág.")
assert client.post("/api/quiz", json={"doc": "animales.pdf"}).json()["questions"]
assert client.post("/api/quiz", json={}).status_code == 400 and client.post("/api/quiz", json={"doc": "nada.pdf"}).status_code == 404
llm.complete = lambda *a, **k: "esto no es json"
assert client.post("/api/quiz", json={"doc": "animales.pdf"}).status_code == 502
llm.complete = real_complete
print("modo estudio (API) OK")
llm.complete = lambda prompt, temperature=0.2, json_mode=False: json.dumps({"titulo": "Animales", "ramas": [{"titulo": "Dieta", "hijos": [{"titulo": "Roedores", "fragmento": 1}]}, {"titulo": "Hábitat", "hijos": [{"titulo": "Selva"}]}]})
mp = client.post("/api/mindmap", json={"doc": "animales.pdf"}).json()["map"]
assert mp["title"] == "Animales" and len(mp["children"]) == 2 and mp["children"][0]["children"][0]["source"]["doc"] == "animales.pdf"
assert client.post("/api/mindmap", json={}).status_code == 400
llm.complete = lambda *a, **k: "nada"
assert client.post("/api/mindmap", json={"doc": "animales.pdf"}).status_code == 502
llm.complete = real_complete
print("mapa mental (API) OK")

# 7) resumen
assert "summary" in client.post("/api/summarize", json={"doc": "animales.pdf"}).json()
assert client.post("/api/summarize", json={"doc": "nada.pdf"}).status_code == 404

# 8) cancelar un trabajo largo
DELAY["s"] = 0.6
files = [("files", (f"n{i}.txt", f"Texto numero {i} de prueba para cancelar.".encode(), "text/plain")) for i in range(4)]
jid = client.post("/api/upload", files=files, data={"use_vision": "false"}).json()["id"]
time.sleep(0.5)
client.post(f"/api/jobs/{jid}/cancel")
j = wait(jid)
DELAY["s"] = 0.0
assert j["state"] == "cancelled", j
assert len([d for d in client.get("/api/docs").json() if d["name"].startswith("n")]) < 4
print("cancelación OK:", j["message"])

# 9) base de conocimiento: carpeta -> escaneo -> sincronización
(config.KB_DIR / "a.txt").write_text("Texto de la nota A.", encoding="utf-8")
(config.KB_DIR / "b.md").write_text("Texto de la nota B.", encoding="utf-8")
kb = client.get("/api/kb").json()
assert sorted(kb["new"]) == ["a.txt", "b.md"], kb
job = wait(client.post("/api/kb/sync", json={"use_vision": False}).json()["id"])
assert job["state"] == "done" and sorted(job["result"]["indexed"]) == ["a.txt", "b.md"], job
kb = client.get("/api/kb").json()
assert kb["new"] == [] and "a.txt" in kb["ok"]
(config.KB_DIR / "a.txt").unlink()
assert client.get("/api/kb").json()["removed"] == ["a.txt"]
wait(client.post("/api/kb/sync", json={"use_vision": False}).json()["id"])
assert "a.txt" not in {d["name"] for d in client.get("/api/docs").json()}
print("base de conocimiento OK")

# 9b) abrir la carpeta en el explorador (se simula; en otros sistemas responde 501)
import os  # noqa: E402
opened = []
os.startfile = lambda path: opened.append(str(path))
r = client.post("/api/kb/open")
assert r.status_code == 200 and opened == [str(config.KB_DIR)], (r.status_code, opened)

# 10) configuración de modelos: se guarda sin la clave
body = {"chat": {"backend": "openai", "model": "gemini-x, gemini-y", "base_url": "https://example.test/v1"}, "embed": {"backend": "ollama", "model": "embeddinggemma", "base_url": ""}, "api_key": "SECRETO-123"}
st = client.post("/api/settings", json=body).json()
assert st["chat"]["model"] == "gemini-x, gemini-y" and st["has_key"] and st["cloud"] and "SECRETO-123" not in json.dumps(st)
assert "SECRETO-123" not in (config.DATA_DIR / "settings.json").read_text(encoding="utf-8")
assert client.post("/api/settings", json={**body, "chat": {"backend": "nube-inventada", "model": "x"}}).status_code == 400
assert client.post("/api/settings", json={**body, "chat": {"backend": "ollama", "model": "  "}}).status_code == 400
config.CHAT.update(backend="ollama", model="gemma3:4b", base_url="", api_key="")

# 10b) historial de chats
assert client.get("/api/chats").json() == []
msgs = [{"role": "user", "content": "¿Qué come el ocelote?"}, {"role": "assistant", "content": "Roedores [animales.pdf, pág. 1]", "model": "m", "sources": [{"id": 1, "doc": "animales.pdf", "loc": "pág. 1", "kind": "texto", "score": 0.5, "text": "x"}],
         "streaming": True, "basura": "no se guarda"}, {"role": "system", "content": "ignorado"}]
c = client.post("/api/chats", json={"messages": msgs}).json()
assert c["title"] == "¿Qué come el ocelote?" and len(c["messages"]) == 2 and "basura" not in c["messages"][1] and "streaming" not in c["messages"][1]
cid = c["id"]
assert [x["id"] for x in client.get("/api/chats").json()] == [cid] and client.get("/api/chats").json()[0]["count"] == 2
got = client.get(f"/api/chats/{cid}").json()
assert got["messages"][1]["sources"][0]["doc"] == "animales.pdf" and got["messages"][1]["model"] == "m"
time.sleep(0.02)
msgs.append({"role": "user", "content": "¿Y dónde vive?"})
upd = client.put(f"/api/chats/{cid}", json={"messages": msgs}).json()
assert len(upd["messages"]) == 3 and upd["title"] == c["title"] and upd["created"] == c["created"] and upd["updated"] > c["updated"]
assert client.patch(f"/api/chats/{cid}", json={"title": "  Animales  "}).json()["title"] == "Animales"
assert client.patch(f"/api/chats/{cid}", json={"title": "   "}).status_code == 400
second = client.post("/api/chats", json={"title": "Otro", "messages": []}).json()
assert [x["title"] for x in client.get("/api/chats").json()] == ["Otro", "Animales"]  # el más reciente primero
assert client.get("/api/chats/zzzzzzzzzzzz").status_code == 400 and client.get("/api/chats/aaaaaaaaaaaa").status_code == 404
assert client.get("/api/chats/..").status_code in (400, 404, 405) and client.put("/api/chats/aaaaaaaaaaaa", json={"messages": []}).status_code == 404
assert client.delete(f"/api/chats/{cid}").status_code == 200 and client.delete(f"/api/chats/{cid}").status_code == 404
# 10d) zona marcada a mano en una página: recorte, preguntas solo sobre ella y la zona queda en el historial
box = {"x0": 0, "y0": 0, "x1": 1, "y1": 0.5}
zr = client.get("/api/zone/animales.pdf/1", params=box)
assert zr.status_code == 200 and zr.content[1:4] == b"PNG"
assert client.get("/api/zone/animales.pdf/1", params={"x0": 0.1, "y0": 0.1, "x1": 0.102, "y1": 0.102}).status_code == 400  # demasiado pequeña
assert client.get("/api/zone/animales.pdf/99", params=box).status_code == 404 and client.get("/api/zone/nota.txt/1", params=box).status_code == 404
seen_zone = []
def zone_stream(messages):  # registra lo que recibe el modelo: la imagen de la zona y el texto leído
    seen_zone.append(messages)
    yield from fake_stream(messages)
real_stream = llm.chat_stream
llm.chat_stream = zone_stream
zev = events(client.post("/api/chat", json={"question": "¿qué dice aquí?", "docs": ["animales.pdf"], "zone": {"page": 1, "rect": [0, 0, 1, 1]}}))
assert zev[0]["event"] == "sources" and zev[0]["data"] == [] and zev[-1]["event"] == "done", zev
zans = "".join(e["data"]["t"] for e in zev if e["event"] == "token")
assert "[animales.pdf, pág. 1]" in zans, zans  # la respuesta siempre cita la página de la zona
assert any(e["event"] == "status" for e in zev)  # «Mirando la zona…»
last = seen_zone[-1][-1]
assert last["images"][0][1:4] == b"PNG" and "Etiqueta para citar: [animales.pdf, pág. 1]" in last["content"] and "¿qué dice aquí?" in last["content"]  # imagen + texto + pregunta
assert "NUNCA copies" in seen_zone[-1][0]["content"]  # las instrucciones piden explicar con palabras propias, no copiar
def no_vision(messages):  # un modelo que no admite imágenes falla antes del primer token: se responde solo con el texto
    if messages[-1].get("images"):
        raise RuntimeError("este modelo no admite imágenes")
    yield from fake_stream(messages)
llm.chat_stream = no_vision
zev2 = events(client.post("/api/chat", json={"question": "¿qué dice aquí?", "docs": ["animales.pdf"], "zone": {"page": 1, "rect": [0, 0, 1, 1]}}))
assert zev2[-1]["event"] == "done" and "error" not in [e["event"] for e in zev2]
assert "error" in [e["event"] for e in events(client.post("/api/chat", json={"question": "x", "zone": {"page": 1, "rect": [0, 0, 1, 1]}}))]  # sin un archivo escogido
assert "error" in [e["event"] for e in events(client.post("/api/chat", json={"question": "x", "docs": ["nota.txt"], "zone": {"page": 1, "rect": [0, 0, 1, 1]}}))]  # no es un PDF
assert "error" in [e["event"] for e in events(client.post("/api/chat", json={"question": "x", "docs": ["animales.pdf"], "zone": {"page": 1, "rect": [0.5, 0.5, 0.5, 0.5]}}))]  # zona vacía
llm.chat_stream = real_stream
zc = client.post("/api/chats", json={"doc": "animales.pdf", "messages": [{"role": "user", "content": "q", "zone": {"doc": "animales.pdf", "page": 1, "rect": [0, 0, 1, 1]}}]}).json()
assert client.get(f"/api/chats/{zc['id']}").json()["messages"][0]["zone"]["rect"] == [0, 0, 1, 1]
client.delete(f"/api/chats/{zc['id']}")
print("zona marcada OK")

# 10c) cada chat trata de un documento (se fija al crearlo) y cada documento tiene sus preguntas sugeridas
c2 = client.post("/api/chats", json={"title": "ligado", "doc": "animales.pdf", "messages": []}).json()
assert c2["doc"] == "animales.pdf" and client.get(f"/api/chats/{c2['id']}").json()["doc"] == "animales.pdf"
assert client.put(f"/api/chats/{c2['id']}", json={"doc": "otro.pdf", "messages": []}).json()["doc"] == "animales.pdf"  # no cambia de documento
assert [x["doc"] for x in client.get("/api/chats").json() if x["id"] == c2["id"]] == ["animales.pdf"]
client.delete(f"/api/chats/{c2['id']}")
from chatpdf import rag  # noqa: E402
sug_llm, sug_calls = llm.complete, {"n": 0}
def fake_suggest(prompt, temperature=0.2, json_mode=False):
    sug_calls["n"] += 1
    return json.dumps({"preguntas": ["1. ¿De qué se alimenta el ocelote?", "¿Dónde vive el ocelote?", "¿Cuánto pesa un ocelote adulto?", "¿Qué tan grande es un ocelote?", "¿Dónde vive el ocelote?"]})
llm.complete = fake_suggest
sug = client.get("/api/docs/animales.pdf/suggestions").json()
assert sug["generated"] and sug["questions"] == ["¿De qué se alimenta el ocelote?", "¿Dónde vive el ocelote?", "¿Cuánto pesa un ocelote adulto?", "¿Qué tan grande es un ocelote?"]  # sin numerar ni repetidas
assert client.get("/api/docs/animales.pdf/suggestions").json()["questions"] == sug["questions"] and sug_calls["n"] == 1  # la segunda vez sale de la base
llm.complete = lambda *a, **k: "esto no es json"
fallback = client.get("/api/docs/nota.txt/suggestions").json()
assert not fallback["generated"] and fallback["questions"] == rag.generic_questions("nota.txt")  # si el modelo falla, preguntas genéricas (y no se guardan)
llm.complete = fake_suggest
assert client.get("/api/docs/nota.txt/suggestions").json()["generated"]  # al reintentar sí las genera
assert client.get("/api/docs/nada.pdf/suggestions").status_code == 404
llm.complete = sug_llm
print("preguntas sugeridas y chats por documento OK")

# 10e) hallazgos de QA: páginas fuera de rango, zonas con valores no válidos y preguntas vacías, enormes o de archivos que no existen
assert client.get("/api/page/animales.pdf/0").status_code == 404 and client.get("/api/page/animales.pdf/-1").status_code == 404  # antes devolvían la última página
assert client.get("/api/zone/animales.pdf/0", params=box).status_code == 404 and client.get("/api/zone/animales.pdf/-3", params=box).status_code == 404
for empty in ("", "   ", " \n\t "):
    ev = events(client.post("/api/chat", json={"question": empty, "docs": ["animales.pdf"]}))
    assert ev[0]["event"] == "error" and "pregunta" in ev[0]["data"]["message"].lower(), ev
ev = events(client.post("/api/chat", json={"question": "x" * 4001, "docs": ["animales.pdf"]}))
assert ev[0]["event"] == "error" and "demasiado larga" in ev[0]["data"]["message"], ev
ev = events(client.post("/api/chat", json={"question": "hola", "docs": ["nada.pdf"]}))
assert ev[0]["event"] == "error" and "no encontrado" in ev[0]["data"]["message"].lower(), ev
nan = events(client.post("/api/chat", content='{"question":"hola","docs":["animales.pdf"],"zone":{"page":1,"rect":[NaN,0,1,1]}}', headers={"Content-Type": "application/json"}))
assert "error" in [e["event"] for e in nan] and "no válidos" in json.dumps(nan, ensure_ascii=False), nan
print("validaciones de QA OK")

# los chats viven en PostgreSQL: sobreviven a una instancia nueva y borrar un chat borra sus mensajes (cascada)
from chatpdf.chats import ChatStore  # noqa: E402
from chatpdf.store import _pool  # noqa: E402
full = {"role": "assistant", "content": "El ocelote come roedores.", "model": "m", "sources": [{"id": 1, "doc": "animales.pdf", "loc": "pág. 1"}], "quiz": [{"q": "x"}]}
sid = client.post("/api/chats", json={"title": "Persistente", "messages": [{"role": "user", "content": "hola"}, full]}).json()["id"]
assert ChatStore().get(sid)["messages"] == [{"role": "user", "content": "hola"}, full]  # ida y vuelta exacta, con fuentes y examen
assert ChatStore().get(sid)["created"] <= ChatStore().get(sid)["updated"]
client.put(f"/api/chats/{sid}", json={"messages": [{"role": "user", "content": "solo uno"}]})
assert client.get(f"/api/chats/{sid}").json()["messages"] == [{"role": "user", "content": "solo uno"}]  # reemplaza, no acumula
with _pool().connection() as conn:
    assert conn.execute(f"SELECT count(*) FROM {ChatStore().schema}.chat_messages WHERE chat_id = %s", (sid,)).fetchone()[0] == 1
    client.delete(f"/api/chats/{sid}")
    assert conn.execute(f"SELECT count(*) FROM {ChatStore().schema}.chat_messages WHERE chat_id = %s", (sid,)).fetchone()[0] == 0
print("historial de chats OK")

# 11) borrar documentos
assert client.delete("/api/docs/nota.txt").status_code == 200 and client.delete("/api/docs/nota.txt").status_code == 404
assert client.delete("/api/docs/..").status_code in (400, 404, 405)  # el cliente lo normaliza a /api/; con el frontend compilado responde 405
print("TODO OK")
