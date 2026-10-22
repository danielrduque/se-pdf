import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Lee KEY=valor de .env sin pisar variables que ya estén definidas en el sistema."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_dotenv(ROOT / ".env")
APP_NAME = "CHATDD"
DATA_DIR = ROOT / "data"
KB_DIR = ROOT / "base_conocimiento"  # carpeta que se indexa con "Sincronizar carpeta"
# PostgreSQL + pgvector (docker compose up -d db). Ojo: 127.0.0.1 y no "localhost", por lo mismo que más abajo.
DB_URL = os.getenv("CHATPDF_DB_URL") or "postgresql://{u}:{p}@127.0.0.1:{port}/{db}".format(
    u=os.getenv("POSTGRES_USER", "chatdd"), p=os.getenv("POSTGRES_PASSWORD", ""),
    port=os.getenv("POSTGRES_PORT", "5434"), db=os.getenv("POSTGRES_DB", "chatdd"),
)

# Proveedores de modelos. "llamacpp" y "openai" hablan el mismo protocolo (API compatible con OpenAI):
#  - llamacpp: tu propio `llama-server` local (ver README)
#  - openai:   cualquier nube compatible (OpenAI, Groq, OpenRouter, Gemini, DeepSeek, Together…)
# Ojo: 127.0.0.1 y no "localhost". En Windows "localhost" intenta primero IPv6 (::1), el servidor no escucha ahí y
# cada llamada pierde ~2 s esperando el timeout antes de caer a IPv4 (medido: 2,4 s vs 0,22 s por embedding).
BACKENDS = {
    "ollama": {"label": "Ollama (local)", "default_url": "http://127.0.0.1:11434"},
    "llamacpp": {"label": "llama.cpp (local)", "default_url": "http://127.0.0.1:8080/v1"},
    "openai": {"label": "API en la nube (compatible OpenAI)", "default_url": "https://api.openai.com/v1"},
}

# Configuración activa. La interfaz la modifica y se guarda (sin la API key) en data/settings.json
_KEY = os.getenv("CHATPDF_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
CHAT = {"backend": "ollama", "model": "gemma3:4b", "base_url": "", "api_key": _KEY}  # multimodal: chat + visión
# EmbeddingGemma 2 con llama.cpp: un segundo llama-server (puerto 8081) con el GGUF y su proyector multimodal (--mmproj), que embebe
# texto, imágenes y audio en el mismo espacio de 768 dimensiones (tools/llamacpp_start.ps1)
EMBED = {"backend": "llamacpp", "model": "embeddinggemma-2", "base_url": "http://127.0.0.1:8081/v1", "api_key": _KEY}

# Búsqueda multimodal: hasta MM_SLOTS de los 6 resultados pueden venir de coincidir directamente con la imagen o el audio original (embeddings
# multimedia) si la similitud pasa MM_TAU. El resto siempre es del texto. Medido en tu índice con 3 conjuntos de consultas (visuales, de texto y
# dentro de un video/audio), la fuente correcta queda entre los 6 en todos; un ranking multimedia en la RRF la hundía a 16/25 en preguntas de texto.
# Depende del modelo: si cambias EmbeddingGemma, vuelve a medirlo (python tools/qa_check.py --retrieval-only).
MM_SLOTS = 1
MM_TAU = 0.68

# Audio / video (siempre local con faster-whisper)
WHISPER_MODEL = "small"  # tiny | base | small | medium
WHISPER_DEVICE = "cpu"  # "cuda" si tienes cuDNN instalado
WHISPER_COMPUTE = "int8"
WHISPER_LANG = None  # None = autodetectar; "es", "en"... para forzar (la UI lo cambia)

# Chunking y recuperación
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
TOP_K = 6  # fragmentos que se pasan al LLM
RERANK_CANDIDATES = 14  # candidatos de la búsqueda híbrida que el reranker reordena
RERANK_SNIPPET = 350  # caracteres de cada candidato que ve el reranker
NUM_CTX = 4096  # contexto del LLM en Ollama; súbelo si te sobra VRAM

# Video
FRAME_EVERY_SEC = 8  # un frame cada N segundos (más espaciado si el video es largo, ver MAX_FRAMES)
MAX_FRAMES = 30
FRAME_MIN_DIFF = 3.0  # diferencia media (0-255) bajo la cual un frame se considera igual al anterior y se omite


def load_settings() -> None:
    p = DATA_DIR / "settings.json"
    if not p.exists():
        return
    saved = json.loads(p.read_text(encoding="utf-8"))
    for name, cfg in (("chat", CHAT), ("embed", EMBED)):
        cfg.update({k: v for k, v in saved.get(name, {}).items() if k in ("backend", "model", "base_url")})


def save_settings() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {name: {k: v for k, v in cfg.items() if k != "api_key"} for name, cfg in (("chat", CHAT), ("embed", EMBED))}
    (DATA_DIR / "settings.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
