"""Mapa mental (comando /mapa), sin Ollama. Ejecutar: python tests/test_mindmap.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatpdf import llm, rag

ITEMS = [
    (10, {"doc": "plan.pdf", "loc": "pág. 3", "kind": "texto", "text": "Instalar 500 sensores en 12 fincas."}),
    (11, {"doc": "plan.pdf", "loc": "pág. 5", "kind": "texto", "text": "El riesgo de rotación del personal es alto."}),
]
good = {"titulo": "Plan 2027", "ramas": [
    {"titulo": "Objetivos", "hijos": [{"titulo": "500 sensores", "fragmento": 1}, {"titulo": "12 fincas", "fragmento": 1}]},
    {"titulo": "Riesgos", "hijos": [{"titulo": "Rotación de personal", "fragmento": 2}, "Sin fuente", {"titulo": ""}]},
    {"titulo": "Sin hijos"},
]}

# 1) árbol válido: títulos, fuentes por fragmento y descarte de lo vacío
llm.complete = lambda prompt, temperature=0.2, json_mode=False: "```json\n" + json.dumps(good) + "\n```"
tree = rag.make_mindmap(ITEMS, "plan")
assert tree["title"] == "Plan 2027" and [b["title"] for b in tree["children"]] == ["Objetivos", "Riesgos", "Sin hijos"]
assert tree["children"][0]["children"][0]["source"] == {"id": 10, "doc": "plan.pdf", "loc": "pág. 3", "kind": "texto"}
assert tree["children"][1]["children"][0]["source"]["id"] == 11
assert [c["title"] for c in tree["children"][1]["children"]] == ["Rotación de personal", "Sin fuente"] and tree["children"][1]["children"][1]["source"] is None
print("árbol OK")

# 2) el prompt lleva el material y el tema; se pide JSON
seen = {}
llm.complete = lambda prompt, temperature=0.2, json_mode=False: (seen.update(prompt=prompt, json_mode=json_mode), json.dumps(good))[1]
rag.make_mindmap(ITEMS, "riesgos")
assert "500 sensores" in seen["prompt"] and "riesgos" in seen["prompt"] and seen["json_mode"] is True

# 3) respuesta inservible: reintenta una vez y luego da un error claro
calls = []
llm.complete = lambda prompt, temperature=0.2, json_mode=False: (calls.append(temperature), "no es json")[1]
try:
    rag.make_mindmap(ITEMS)
    raise SystemExit("debió fallar")
except ValueError as e:
    assert "mapa" in str(e) and len(calls) == 2 and calls[1] > calls[0]
assert rag._parse_map(json.dumps({"titulo": "X1", "ramas": [{"titulo": "una sola"}]}), ITEMS) is None  # con menos de 2 ramas no es un mapa
print("mapa mental OK")
