"""Descarga los modelos de EmbeddingGemma 2 en formato GGUF para llama.cpp (~870 MB), en tools/models/.

  - embeddinggemma-2-Q8_0.gguf        el modelo (núcleo de texto), 310 MB
  - mmproj-embeddinggemma-2-Q8_0.gguf el proyector multimodal: codificadores de visión y de audio, 555 MB

Uso:  python tools/download_models.py
Origen: https://huggingface.co/ggml-org/embeddinggemma-2-GGUF (Apache 2.0). Hace falta llama.cpp >= b11658.
"""
import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

DEST = Path(__file__).resolve().parent / "models"
FILES = ("embeddinggemma-2-Q8_0.gguf", "mmproj-embeddinggemma-2-Q8_0.gguf")

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
DEST.mkdir(exist_ok=True)
for name in FILES:
    path = hf_hub_download("ggml-org/embeddinggemma-2-GGUF", name, local_dir=DEST)
    print(f"{name}: {os.path.getsize(path) / 1e6:.0f} MB -> {path}")
sys.exit(0)
