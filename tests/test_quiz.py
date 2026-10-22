"""Preguntas de selección múltiple del modo estudio, sin Ollama. Ejecutar: python tests/test_quiz.py"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatpdf import llm, rag

ITEMS = [
    (10, {"doc": "plan.pdf", "loc": "pág. 3", "kind": "texto", "text": "Instalar 500 sensores en 12 fincas. Reducir el tiempo de instalación de 45 a 30 minutos."}),
    (11, {"doc": "plan.pdf", "loc": "pág. 5", "kind": "texto", "text": "El riesgo de rotación del personal técnico es de probabilidad alta."}),
]


def q(text, correct=0, frag=1, expl="Porque sí."):
    return {"pregunta": text, "opciones": ["A correcta", "B falsa", "C falsa", "D falsa"], "correcta": correct, "explicacion": expl, "fragmento": frag}


good = {"preguntas": [q("¿Cuántos sensores se planea instalar en 2027?"), q("¿Qué riesgo tiene probabilidad alta?", frag=2), q("¿A cuántos minutos se reduce la instalación?", correct=2, frag=1)]}

# 1) respuesta válida: se mezclan las opciones sin perder cuál es la correcta, y cada pregunta enlaza con su fuente
llm.complete = lambda prompt, temperature=0.2, json_mode=False: json.dumps(good)
positions = Counter()
for seed in range(60):
    quiz = rag.make_quiz(ITEMS, "objetivos", 3, random.Random(seed))
    assert len(quiz) == 3
    for item in quiz:
        assert len(item["options"]) == 4 and 0 <= item["answer"] <= 3
    assert quiz[0]["options"][quiz[0]["answer"]] == "A correcta" and quiz[2]["options"][quiz[2]["answer"]] == "C falsa"  # la respuesta correcta sigue siendo la misma
    positions[quiz[0]["answer"]] += 1
assert len(positions) == 4 and min(positions.values()) >= 5, positions  # la correcta no queda siempre en la misma posición
assert quiz[0]["source"] == {"id": 10, "doc": "plan.pdf", "loc": "pág. 3", "kind": "texto"} and quiz[1]["source"]["id"] == 11
print("mezcla de opciones y fuentes OK:", dict(sorted(positions.items())))

# 2) el prompt lleva el material, el tema y las reglas
seen = {}
llm.complete = lambda prompt, temperature=0.2, json_mode=False: (seen.update(prompt=prompt, json_mode=json_mode), json.dumps(good))[1]
rag.make_quiz(ITEMS, "¿qué riesgos hay?", 3)
assert seen["json_mode"] is True and "Fragmento 1 [plan.pdf, pág. 3]" in seen["prompt"] and "500 sensores" in seen["prompt"] and "¿qué riesgos hay?" in seen["prompt"]

# 3) JSON dentro de un bloque de código y con texto alrededor
llm.complete = lambda prompt, temperature=0.2, json_mode=False: "Aquí tienes:\n```json\n" + json.dumps(good) + "\n```\nSuerte."
assert len(rag.make_quiz(ITEMS, "", 3)) == 3

# 4) se descartan las preguntas malas y se conservan las buenas
bad = {"preguntas": [
    q("¿Pregunta válida número uno?"),
    {**q("¿Opciones repetidas aquí?"), "opciones": ["A", "A", "B", "C"]},
    {**q("¿Solo tres opciones aquí?"), "opciones": ["A", "B", "C"]},
    {**q("¿Correcta fuera de rango?"), "correcta": 7},
    {**q("¿Correcta es un texto?"), "correcta": "A"},
    {**q("¿Correcta booleana?"), "correcta": True},
    q("corta"),
    q("¿Pregunta válida número uno?"),  # repetida
    "no soy un objeto",
    {**q("¿Fragmento inexistente aquí?"), "fragmento": 99},
]}
llm.complete = lambda prompt, temperature=0.2, json_mode=False: json.dumps(bad)
out = rag.make_quiz(ITEMS, "", 10)
assert [o["question"] for o in out] == ["¿Pregunta válida número uno?", "¿Fragmento inexistente aquí?"], [o["question"] for o in out]
assert out[1]["source"] is None  # sin fuente reconocible no se inventa una
print("validación de preguntas OK:", len(out), "de", len(bad["preguntas"]))

# 5) primera respuesta inservible -> se reintenta una vez
calls = []
def flaky(prompt, temperature=0.2, json_mode=False):
    calls.append(temperature)
    return "lo siento, no puedo" if len(calls) == 1 else json.dumps(good)
llm.complete = flaky
assert len(rag.make_quiz(ITEMS, "", 3)) == 3 and len(calls) == 2 and calls[1] > calls[0]

# 6) si el modelo nunca devuelve nada útil: error claro
llm.complete = lambda prompt, temperature=0.2, json_mode=False: "{ esto no es json"
try:
    rag.make_quiz(ITEMS, "", 3)
    raise SystemExit("debió fallar")
except ValueError as e:
    assert "no devolvió preguntas" in str(e)

# 7) lista suelta en vez de objeto, y límites de n
llm.complete = lambda prompt, temperature=0.2, json_mode=False: json.dumps(good["preguntas"])
assert len(rag.make_quiz(ITEMS, "", 2)) == 2 and len(rag.make_quiz(ITEMS, "", 99)) == 3
print("TODO OK")
