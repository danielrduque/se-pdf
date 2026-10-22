"""Preguntas globales («¿de qué trata el video?») sin Ollama. Ejecutar: python tests/test_overview.py"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

# --- qué preguntas son globales ---
SI = [
    "¿De qué trata el video?", "hazme un resumen de lo que trata el video", "resume el documento", "Explícame todo el video",
    "pero todo el video analiza el audio y las escenas y dime de que trata", "¿De qué va el audio?", "¿Qué pasa en el video?",
    "Describe el video", "dame una idea general del contrato", "¿Sobre qué es el PDF?",
]
NO = [
    "¿Quién lidera el proyecto Colibri?", "¿Qué dice el contrato sobre cancelar el servicio?", "¿Cuánto se vendió en el primer trimestre?",
    "¿Cuántos sensores lleva la Zona B?", "¿Dónde está el punto de encuentro en una emergencia?", "¿Cada cuánto se calibra el sensor?",
    # hallazgo de QA: «que se ve en el video» dentro de otra pregunta es una oración de relativo, no un pedido de resumen (tardaba 112 s)
    "¿Cuál es el marcador final del partido que se ve en el video?", "¿Qué camiseta lleva el hombre que aparece en el video?",
    "¿Cuántas personas hay en la escena que se muestra en el audiovisual?", "¿Qué dice el rótulo que muestra en la pantalla el video?",
]
assert all(rag.is_overview(q) for q in SI), [q for q in SI if not rag.is_overview(q)]
assert not any(rag.is_overview(q) for q in NO), [q for q in NO if rag.is_overview(q)]
print("detección de preguntas globales OK:", len(SI), "sí /", len(NO), "no")

with tempfile.TemporaryDirectory() as tmp:
    config.DATA_DIR = Path(tmp) / "data"
    store = VectorStore()
    V = lambda t, loc, kind: {"text": t, "loc": loc, "kind": kind}
    vec = lambda n: [[1.0, float(i)] for i in range(n)]

    # video nuevo: escenas primero y audio después, y fuera de orden, para comprobar que se ordena por minuto
    new_video = [V("[Frame de video] Un hombre con camiseta del Barcelona transmite.", "00:16", "visión"), V("Ataca el PSG. Cancelo en defensa.", "00:00–00:26", "audio"),
                 V("[Frame de video] Logo de KICK en pantalla.", "00:00", "visión"), V("[Frame de video] El hombre grita y levanta los brazos.", "00:24", "visión")]
    store.add("WhatsApp Video.mp4", new_video, vec(4))
    time.sleep(0.01)
    store.add("capacitacion_seguridad.mp4", [V("Hola a todos.", "00:00–00:09", "audio")], vec(1))
    store.add("contrato.pdf", [V("Cláusula 1.", "pág. 1", "texto"), V("Cláusula 2.", "pág. 2", "texto")], vec(2))
    store.add("mensaje.wav", [V("Mensaje del gerente.", "00:00–00:18", "audio")], vec(1))
    store.set_added("capacitacion_seguridad.mp4", 1)  # más viejo
    store.set_added("WhatsApp Video.mp4", 2)  # el más reciente

    # --- a qué documento se refiere ---
    T = lambda q, docs=None: rag.overview_targets(store, q, docs)
    assert T("¿de qué trata el video?") == ["WhatsApp Video.mp4"]  # hay 2 videos: el más reciente
    assert T("resume capacitacion_seguridad") == ["capacitacion_seguridad.mp4"]  # nombrado
    assert T("resume el pdf") == ["contrato.pdf"]
    assert T("de qué va el audio") == ["mensaje.wav"]
    assert T("resume esto", ["contrato.pdf"]) == ["contrato.pdf"]  # único documento seleccionado
    assert T("resume esto") == []  # ambiguo: se usa la búsqueda normal
    assert T("resume el video", ["contrato.pdf"]) == []  # el video no está entre los seleccionados
    print("elección del documento OK")

    # --- orden por minuto, voz y escenas mezcladas ---
    ordered = [rag._label(m) for _, m in rag._ordered(store, "WhatsApp Video.mp4")]
    assert [l.split("]")[0] for l in ordered] == ["[00:00–00:26", "[00:00", "[00:16", "[00:24"], ordered  # a igual minuto, primero la voz
    assert ordered[0] == "[00:00–00:26] Se dice: Ataca el PSG. Cancelo en defensa." and ordered[1].startswith("[00:00] Se ve: Logo de KICK")
    assert "[Frame de video]" not in " ".join(ordered)
    hits = rag.overview_hits(store, "WhatsApp Video.mp4")
    assert len(hits) == 4 and all(h["score"] is None and "id" in h for h in hits)

    # --- el resumen recibe todo el contenido en orden, con instrucciones de video ---
    prompts = []
    llm.chat_stream = lambda messages: (prompts.append(messages[-1]["content"]), iter(["Trata ", "de un streamer."]))[1]
    out = list(rag.overview_stream(store, "WhatsApp Video.mp4"))
    assert [v for k, v in out if k == "token"] == ["Trata ", "de un streamer."] and out[0][0] == "status"
    p = prompts[0]
    assert "DE QUÉ TRATA el video" in p and p.index("Se dice: Ataca el PSG") < p.index("Se ve: Un hombre") < p.index("Se ve: El hombre grita")
    assert rag.summarize(store, "WhatsApp Video.mp4") == "Trata de un streamer."
    print("resumen ordenado OK")

    # --- documentos largos: se resumen por partes y luego se resumen los resúmenes ---
    store.add("largo.pdf", [V(("Párrafo %d. " % i) * 120, f"pág. {i}", "texto") for i in range(1, 9)], vec(8))
    calls = []
    llm.complete = lambda prompt, temperature=0.2: (calls.append(prompt), "resumen parcial")[1]
    out = list(rag.overview_stream(store, "largo.pdf"))
    status = [v for k, v in out if k == "status"]
    assert len(calls) >= 2 and any("parte 1 de" in s for s in status) and status[-1].startswith("Escribiendo el resumen"), (len(calls), status)
    assert "DE QUÉ TRATA" not in prompts[-1] and "documento" in prompts[-1]
    print(f"documento largo OK: {len(calls)} resúmenes parciales")

print("TODO OK")
