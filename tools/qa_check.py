"""Prueba la app con preguntas sobre cada archivo de la base de conocimiento de ejemplo.

Uso:
  python tools/qa_check.py --mode gemini --sync     # chat/visión con la cadena de Gemini (nube), embeddings locales
  python tools/qa_check.py --mode local  --sync     # todo local con Ollama (gemma3:4b + embeddinggemma)
  python tools/qa_check.py --mode current           # lo configurado en la app, sobre el índice real de data/
  python tools/qa_check.py --retrieval-only         # solo la búsqueda (sin LLM, ~15 s): ¿la fuente correcta está entre los 6 fragmentos?

Cada modo usa su propio índice (data/qa_<modo>/), así la comparación es justa: la visión del indexado también
la hace el modelo del modo. Para cada pregunta se comprueba (1) que la respuesta contenga lo esperado y
(2) que la fuente correcta (archivo y página/minuto) esté entre los fragmentos recuperados.
Las preguntas con su respuesta están en docs/preguntas_de_prueba.md. Requiere haber generado la base: tools/make_sample_kb.py
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chatpdf import config, llm, rag
from chatpdf.store import VectorStore

M, C, P = "manual_sensor_AG200.pdf", "contrato_servicios.pdf", "informe_ventas_2026.pdf"
A, O, W = "acta_reunion_escaneada.pdf", "organigrama.png", "mensaje_del_gerente.wav"
V = "capacitacion_seguridad.mp4"
G, L = "guia_instalacion_riego.pdf", "plan_estrategico_2027.pdf"

# (archivo, pregunta, fragmentos que la respuesta debe contener ["a|b" = cualquiera], fuentes que deben estar recuperadas)
# fuentes: [(archivo, prefijo_de_ubicación | None)]; needles=None -> la respuesta debe decir que no lo encuentra
CASES = [
    (M, "¿Cuál es el rango de temperatura de operación del sensor AG-200?", ["-10", "60"], [(M, "pág. 1")]),
    (M, "¿Qué significa el error E-4471?", ["humedad", "desconectado"], [(M, "pág. 3")]),
    (M, "¿Cada cuánto se debe calibrar el sensor?", ["6 meses"], [(M, "pág. 2")]),
    (C, "¿Cuántos días de aviso previo se necesitan para cancelar el contrato y qué penalización hay?", ["30|treinta", "10"], [(C, None)]),
    (C, "¿Cuál es el valor mensual del contrato de servicios?", ["4200"], [(C, None)]),
    (P, "¿En qué trimestre fueron más altas las ventas de 2026 y cuánto se vendió?", ["t3|tercer", "210"], [(P, None)]),
    (P, "¿Cuánto se vendió en el primer trimestre de 2026?", ["120"], [(P, None)]),
    (P, "¿Qué línea de producto tiene la mayor participación en las ventas?", ["sensores de riego", "48"], [(P, None)]),
    (A, "¿Cuál es el presupuesto aprobado para el proyecto Colibri?", ["85000"], [(A, None)]),
    (A, "¿Quiénes asistieron a la reunión del 14 de marzo?", ["carlos ruiz", "pardo", "torres"], [(A, None)]),
    (A, "¿Cuál es la fecha de entrega del proyecto Colibri?", ["30 de junio"], [(A, None)]),
    (O, "¿Quién es el jefe de ingeniería?", ["luis pardo"], [(O, None)]),
    (O, "¿Quién es el gerente general?", ["carlos ruiz"], [(O, None)]),
    (O, "¿Qué cargo tiene Ana Torres?", ["coordinadora de compras"], [(O, None)]),
    (W, "¿Cuántos sensores se planea instalar en 2027 y en cuántas fincas?", ["500", "12"], [(W, None)]),
    (W, "¿Cuál es la fecha de lanzamiento oficial?", ["12 de noviembre"], [(W, None)]),
    (V, "¿Cada cuántos metros hay un extintor y de qué tipo?", ["15", "abc"], [(V, None)]),
    (V, "¿Dónde está el punto de encuentro en una emergencia?", ["parqueadero norte"], [(V, None)]),
    (V, "¿Qué equipo de protección es obligatorio en la zona de instalación?", ["casco", "gafas", "guantes"], [(V, None)]),
    (G, "¿Cada cuántos metros se marcan los puntos de instalación?", ["15"], [(G, "pág. 2")]),
    (G, "¿Cuántos sensores lleva la Zona B?", ["18"], [(G, "pág. 3")]),
    (G, "¿Cuánto hay que esperar para la primera lectura de un sensor?", ["10 minutos"], [(G, "pág. 4")]),
    (G, "¿Cuál es la presión de trabajo del sistema de riego?", ["2,5 bar"], [(G, "pág. 2")]),
    (L, "¿Cuántos clientes activos tenía la empresa al cierre de 2026?", ["38"], [(L, "pág. 2")]),
    (L, "¿A cuántos minutos se quiere reducir el tiempo de instalación por sensor?", ["30"], [(L, "pág. 3")]),
    (L, "¿Cuánto se invertirá en tecnología en 2027?", ["120"], [(L, "pág. 4")]),
    (L, "¿Qué riesgos tienen probabilidad alta?", ["rotacion", "tipo de cambio", "!retraso"], [(L, "pág. 5")]),  # "!x": NO debe aparecer
    (L, "¿Cuándo se hará el piloto y en cuántas fincas?", ["junio", "3"], [(L, "pág. 6")]),
    (L, "¿Cuándo es la próxima revisión del plan estratégico?", ["15 de enero"], [(L, "pág. 7")]),
    ("varios", "¿Cuánto tarda hoy instalar un sensor y a cuánto se quiere reducir?", ["45", "30"], [(G, "pág. 1"), (L, "pág. 3")]),
    ("varios", "¿Quién es la responsable del proyecto Colibri y cuál es su cargo?", ["maría gonzález", "directora de proyectos"], []),
    ("varios", "¿De qué ciudad es el proveedor de sensores?", ["bogot"], []),
    ("sin respuesta", "¿Cuál es el salario del gerente general?", None, []),
    ("sin respuesta", "¿Cuánto cuesta cada sensor AG-200?", None, []),
]
NO_ANSWER = ("no se ", "no encuentr", "no aparece", "no contiene", "no incluye", "no menciona", "no hay", "no esta ", "no proporciona",
             "no especifica", "no dispone", "no figura", "no indica", "no se menciona", "no tengo")


def answer_ok(answer: str, needles: list[str] | None) -> bool:
    """needles: cada elemento debe aparecer ("a|b" = cualquiera de las dos); con "!" delante, NO debe aparecer."""
    a = norm(answer)
    if needles is None:
        return any(p in a for p in NO_ANSWER)
    return all((norm(n[1:]) not in a) if n.startswith("!") else any(norm(alt) in a for alt in n.split("|")) for n in needles)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"(?<=\d)[.,](?=\d)", "", s).replace("**", "")


def setup(mode: str, do_sync: bool):
    config.load_settings()
    if mode == "local":
        config.CHAT.update(backend="ollama", model="gemma3:4b", base_url="")
        config.EMBED.update(backend="ollama", model="embeddinggemma", base_url="")
    if mode != "current":
        config.DATA_DIR = ROOT / "data" / f"qa_{mode}"
    problems = llm.check_backends()
    if problems:
        sys.exit("No se puede probar: " + "; ".join(problems))
    store = VectorStore()
    print(f"modo: {mode} | chat: {config.CHAT['backend']} {config.CHAT['model'].split(',')[0].strip()}"
          f"{' (+respaldo)' if ',' in config.CHAT['model'] else ''} | embeddings: {config.EMBED['model']} | índice: {config.DATA_DIR}")
    if do_sync:
        t = time.time()
        r = rag.kb_sync(store, config.KB_DIR, True, on_file=lambda p, i, n: print(f"  indexando [{i}/{n}] {p.name}", flush=True))
        print(f"indexado en {time.time() - t:.0f} s | errores: {r['errors'] or 'ninguno'}")
        if r["errors"]:
            sys.exit(1)
    return store


def retrieval_only(store: VectorStore) -> int:
    """Solo la búsqueda, sin LLM: rápido, y detecta regresiones del índice o de la fusión de rankings (las preguntas con archivo no cargado se omiten)."""
    docs = set(store.docs())
    ok = tot = 0
    skipped = 0
    for _doc, q, _needles, sources in CASES:
        if not sources:
            continue
        if any(d not in docs for d, _ in sources):
            skipped += 1
            continue
        tot += 1
        hits = rag.retrieve(store, q)
        good = all(any(h["doc"] == d and (loc is None or h["loc"].startswith(loc)) for h in hits) for d, loc in sources)
        ok += good
        if not good:
            print(f"FUENTE ✗  {q}\n      esperaba: {sources}\n      recuperó: {[(h['doc'][:24], h['loc'], h.get('via')) for h in hits]}")
    print(f"\nBÚSQUEDA: fuente correcta en {ok}/{tot} (omitidas porque su archivo no está cargado: {skipped})")
    return 0 if ok == tot else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gemini", "local", "current"], default="current")
    ap.add_argument("--sync", action="store_true", help="indexar la carpeta base_conocimiento/ antes de preguntar")
    ap.add_argument("--retrieval-only", action="store_true", help="solo comprobar la búsqueda (sin LLM)")
    args = ap.parse_args()
    store = setup(args.mode, args.sync)
    if args.retrieval_only:
        return retrieval_only(store)
    if not store.docs():
        print("El índice está vacío: usa --sync o sincroniza la carpeta desde la app.")
        return 2

    rows, per_doc = [], defaultdict(lambda: [0, 0, 0])  # archivo -> [respuestas ok, fuentes ok, total]
    for doc, q, needles, sources in CASES:
        t = time.time()
        hits = rag.retrieve(store, q)
        try:
            answer = "".join(llm.chat_stream(rag.build_messages(q, hits, [])))
        except Exception as e:  # p. ej. cuota agotada en todos los modelos de la nube: cuenta como fallo y se sigue
            answer = f"[ERROR] {type(e).__name__}: {e}"
        secs = time.time() - t
        ans_ok = answer_ok(answer, needles)
        src_ok = all(any(h["doc"] == d and (loc is None or h["loc"].startswith(loc)) for h in hits) for d, loc in sources)
        per_doc[doc][0] += ans_ok
        per_doc[doc][1] += src_ok
        per_doc[doc][2] += 1
        rows.append({"doc": doc, "q": q, "answer": answer, "ans_ok": ans_ok, "src_ok": src_ok, "secs": round(secs, 1),
                     "model": llm.last_model.get("chat"), "sources": [(h["doc"], h["loc"]) for h in hits]})
        print(f"{'OK  ' if ans_ok else 'FALLA'} {'fuente OK ' if src_ok else 'FUENTE ✗  '} [{doc}] {q}  ({secs:.0f} s, {llm.last_model.get('chat')})")
        if not (ans_ok and src_ok):
            print(f"      esperaba: {needles} en {sources}\n      respuesta: {answer[:260]!r}\n      recuperó: {rows[-1]['sources']}")

    n = len(CASES)
    print(f"\n{'archivo':32} respuestas  fuentes")
    for d, (a, s, t) in per_doc.items():
        print(f"{d:32} {a}/{t}         {s}/{t}")
    tot_a, tot_s = sum(r["ans_ok"] for r in rows), sum(r["src_ok"] for r in rows)
    avg = sum(r["secs"] for r in rows) / n
    print(f"\nTOTAL [{args.mode}]: respuestas {tot_a}/{n} | fuentes {tot_s}/{n} | {avg:.1f} s por pregunta")
    out = config.DATA_DIR / "qa_results.json"
    out.write_text(json.dumps({"mode": args.mode, "answers_ok": tot_a, "sources_ok": tot_s, "total": n, "avg_secs": avg, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if tot_a == n and tot_s == n else 1


if __name__ == "__main__":
    sys.exit(main())
