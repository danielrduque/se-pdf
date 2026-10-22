"""Comprueba, con archivos reales, que EmbeddingGemma 2 multimodal funciona de verdad: la pregunta (texto) se compara DIRECTAMENTE
con la imagen o el audio, sin pasar por una descripción ni una transcripción.

Uso:  python tools/mm_check.py            (necesita el llama-server de embeddings: powershell -File tools\llamacpp_start.ps1)

Para cada archivo multimedia de data/files se calcula su vector y se ordenan unas frases de ejemplo: la correcta debe quedar primero.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from chatpdf import config, llm, media_io

config.load_settings()
FILES = ROOT / "data" / "files"

# (archivo, tramo/página opcional, frases candidatas; la primera es la que debe ganar)
CASES = [
    ("organigrama.png", None, ["organigrama de la empresa con gerente, jefes y cargos", "receta de cocina con arroz y pollo", "foto de un paisaje de montaña", "gráfico de barras de ventas por trimestre"]),
    ("plan_estrategico_2027.pdf", 6, ["cronograma o diagrama de Gantt con hitos del proyecto por meses", "organigrama de la empresa", "foto de un paisaje de montaña", "receta de cocina"]),
    ("informe_ventas_2026.pdf", 3, ["gráfico de barras con las ventas por trimestre", "organigrama de la empresa", "cronograma con hitos por meses", "foto de un gato"]),
    ("mensaje_del_gerente.wav", (0, 18), ["una persona hablando en español sobre el plan de instalar sensores en fincas", "música de piano instrumental", "ruido blanco y estática", "un perro ladrando"]),
]


def vec(item: dict | str) -> np.ndarray:
    if isinstance(item, str):
        return np.array(llm._embed([f"task: search result | query: {item}"])[0])
    return np.array(llm.embed_media([item])[0])


def main() -> int:
    if problems := llm.check_backends():
        print("No se puede probar:", *problems, sep="\n  ")
        return 2
    if not llm.mm_enabled():
        print("El llama-server de embeddings no tiene el proyector multimodal (--mmproj): solo embebería texto.")
        return 2
    print(f"EmbeddingGemma 2 en llama.cpp: {config.EMBED['base_url']}  módulos: {llm._modalities()}")
    wins = 0
    for name, where, queries in CASES:
        path = FILES / name
        if not path.exists():
            print(f"(falta {name}: se omite)")
            continue
        t = time.time()
        if path.suffix == ".pdf":
            item = {"image": media_io.pdf_page_png(path, where, 110), "tokens": 560}
        elif path.suffix in {".wav", ".mp3", ".m4a"}:
            item = {"audio": media_io.audio_segment(path, *where)}
        else:
            item = {"image": path.read_bytes(), "tokens": 560}
        v = vec(item)
        took = time.time() - t
        qs = np.array([vec(q) for q in queries])
        sims = qs @ v / (np.linalg.norm(qs, axis=1) * np.linalg.norm(v))
        order = np.argsort(-sims)
        ok = order[0] == 0
        wins += ok
        print(f"\n{'OK ' if ok else 'MAL'} {name}{f' (pág. {where})' if path.suffix == '.pdf' else ''}  [{took:.1f} s para embeber el {'audio' if 'audio' in item else 'la imagen'}]")
        for rank, i in enumerate(order, 1):
            print(f"   {rank}. {sims[i]:.3f}  {queries[i]}")
    print(f"\nLa frase correcta quedó primera en {wins} de {len(CASES)} casos.")
    return 0 if wins == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
