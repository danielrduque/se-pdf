"""Capa única de acceso a modelos. El resto de la app no sabe si habla con Ollama, llama.cpp o una API en la nube.

El campo `model` del chat admite varios modelos separados por coma ("a, b, c"): se prueban en orden y se salta
al siguiente cuando uno falla. Los embeddings usan siempre el primero (mezclar modelos rompería el índice).
"""
import base64
import time

import httpx
import numpy as np
import ollama
from openai import AuthenticationError, BadRequestError, NotFoundError, OpenAI, PermissionDeniedError

from . import config

_BATCH = 16
_FAST_TIMEOUT = 45  # con varios modelos, no esperar mucho a uno que no responde: se pasa al siguiente
_COOLDOWN = {"default": 60, "missing": 600}  # segundos que un modelo que falló queda en pausa
_paused: dict[tuple, float] = {}
last_model: dict[str, str] = {}  # último modelo que respondió, por rol (para mostrarlo en la interfaz)


# ---------- clientes ----------

def _url(cfg: dict) -> str:
    return cfg["base_url"] or config.BACKENDS[cfg["backend"]]["default_url"]


def _models(cfg: dict) -> list[str]:
    return [m.strip() for m in cfg["model"].split(",") if m.strip()]


def _ollama(cfg: dict) -> ollama.Client:
    return ollama.Client(host=_url(cfg))


def _openai(cfg: dict, patient: bool = True) -> OpenAI:
    # llama-server local no pide clave. Con "patient" se reintenta mucho (los planes gratuitos de la nube
    # limitan las peticiones por minuto: 429); sin él se falla rápido para saltar al siguiente modelo.
    return OpenAI(
        base_url=_url(cfg), api_key=cfg["api_key"] or "sin-clave",
        timeout=300 if patient else _FAST_TIMEOUT, max_retries=6 if patient else 1,
    )


def _openai_messages(messages: list[dict]) -> list[dict]:
    """Convierte {"role", "content", "images": [bytes]} al formato de contenido por partes de las APIs compatibles con OpenAI."""
    out = []
    for m in messages:
        if not m.get("images"):
            out.append(m)
            continue
        parts = [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": _image_url(i)}} for i in m["images"]]
        out.append({"role": m["role"], "content": parts})
    return out


_props: dict[str, tuple[float, dict]] = {}


def _modalities() -> dict:
    """Lo que el llama-server de embeddings sabe leer ({"vision": True, "audio": True}): depende de que se haya arrancado con --mmproj."""
    cfg = config.EMBED
    if cfg["backend"] != "llamacpp":
        return {}
    root = _url(cfg).rstrip("/").removesuffix("/v1")
    hit = _props.get(root)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    try:
        mods = httpx.get(f"{root}/props", timeout=5).json().get("modalities", {}) or {}
    except Exception:  # noqa: BLE001
        mods = {}
    _props[root] = (time.time(), mods)
    return mods


def mm_enabled() -> bool:
    """¿Se pueden embeber imágenes y audio directamente? Solo con EmbeddingGemma 2 en llama.cpp arrancado con su proyector multimodal."""
    mods = _modalities()
    return bool(mods.get("vision") or mods.get("audio"))


def _wav(wave_f32: np.ndarray, sr: int = 16000) -> bytes:
    import io
    import wave

    pcm = (np.clip(np.asarray(wave_f32, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return bio.getvalue()


def media_part(item: dict) -> dict:
    """Parte de contenido de llama-server para una imagen ({"image": bytes}) o un trozo de audio ({"audio": onda float32 a 16 kHz})."""
    if "image" in item:
        return {"type": "image_url", "image_url": {"url": _image_url(item["image"])}}
    return {"type": "input_audio", "input_audio": {"data": base64.b64encode(_wav(item["audio"])).decode(), "format": "wav"}}


def _is_ollama(cfg: dict) -> bool:
    return cfg["backend"] == "ollama"


def _image_url(img: bytes) -> str:
    mime = "image/jpeg" if img[:3] == b"\xff\xd8\xff" else "image/webp" if img[8:12] == b"WEBP" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(img).decode()}"


# ---------- salto entre modelos ----------

def _key(cfg: dict, model: str) -> tuple:
    return (cfg["backend"], _url(cfg), model)


def _order(cfg: dict) -> list[str]:
    """Modelos en el orden configurado, dejando para el final los que fallaron hace poco."""
    models, now = _models(cfg), time.time()
    ready = [m for m in models if _paused.get(_key(cfg, m), 0) <= now]
    return ready + [m for m in models if m not in ready]


def _failed(cfg: dict, model: str, e: Exception, errors: list[str]):
    if isinstance(e, (AuthenticationError, PermissionDeniedError)):
        raise e  # una clave inválida fallaría igual con todos los modelos
    errors.append(f"{model}: {type(e).__name__}")
    pause = _COOLDOWN["missing" if isinstance(e, NotFoundError) else "default"]
    _paused[_key(cfg, model)] = time.time() + pause


def _run(cfg: dict, role: str, call):
    """Ejecuta call(modelo, paciente) con el primer modelo que responda."""
    order = _order(cfg)
    if len(order) == 1:
        r = call(order[0], True)
        last_model[role] = order[0]
        return r
    errors: list[str] = []
    for i, m in enumerate(order):
        try:
            r = call(m, i == len(order) - 1)  # solo el último modelo es "paciente"
            last_model[role] = m
            return r
        except Exception as e:
            _failed(cfg, m, e, errors)
    raise RuntimeError("Ningún modelo respondió → " + "; ".join(errors))


def _chat_openai(cfg: dict, model: str, messages: list[dict], temperature: float, stream: bool, patient: bool = True, json_mode: bool = False):
    client = _openai(cfg, patient)
    kw = dict(model=model, messages=messages, stream=stream, temperature=temperature)
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    for _ in range(2):  # algunos modelos no aceptan 'temperature' o 'response_format': se reintenta sin ese parámetro
        try:
            return client.chat.completions.create(**kw)
        except BadRequestError as e:
            msg = str(e).lower()
            dropped = next((k for k in ("temperature", "response_format") if k in msg and k in kw), None)
            if dropped is None:
                raise
            kw.pop(dropped)
    return client.chat.completions.create(**kw)


# ---------- comprobación ----------

def check_backends() -> list[str]:
    """Problemas que impiden usar la configuración actual (lista vacía si todo está listo)."""
    problems, seen = [], set()
    for role, cfg in (("chat", config.CHAT), ("embeddings", config.EMBED)):
        names, url = (_models(cfg) if role == "chat" else _models(cfg)[:1]), _url(cfg)
        if not names:
            problems.append(f"Escribe un modelo para {role}.")
            continue
        if cfg["backend"] == "ollama":
            try:
                installed = {m.model for m in _ollama(cfg).list().models}
            except Exception:
                if ("ollama", url) not in seen:
                    problems.append(f"Ollama no responde en {url}. Instálalo desde https://ollama.com/download/windows y ábrelo.")
                seen.add(("ollama", url))
                continue
            for name in names:
                if name not in installed and f"{name}:latest" not in installed:
                    problems.append(f"Falta el modelo `{name}` ({role}). Ejecuta: `ollama pull {name}`")
        elif cfg["backend"] == "llamacpp":
            try:
                _openai(cfg).models.list()
            except Exception:
                if ("llamacpp", url) not in seen:
                    problems.append(f"No hay un `llama-server` respondiendo en {url} ({role}). Mira la sección llama.cpp del README.")
                seen.add(("llamacpp", url))
        else:  # nube
            if not cfg["api_key"]:
                problems.append(f"Falta la API key para {role} ({url}). Escríbela en 'Modelos' o defínela en el archivo .env (CHATPDF_API_KEY).")
    return problems


# ---------- embeddings ----------

def _embed(inputs: list[str]) -> list[list[float]]:
    cfg, model = config.EMBED, _models(config.EMBED)[0]
    if _is_ollama(cfg):
        return _ollama(cfg).embed(model=model, input=inputs).embeddings
    r = _openai(cfg).embeddings.create(model=model, input=inputs)
    return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]


def embed_media(items: list[dict]) -> list[list[float] | None]:
    """Vector de cada imagen o trozo de audio, directamente (sin describirlos antes), con EmbeddingGemma 2 en llama.cpp: el servidor acepta
    en /v1/embeddings entradas {"content": [parte]} cuando se arrancó con --mmproj. None si ese elemento no se pudo embeber.
    Cada item: {"image": bytes PNG/JPG/WEBP} o {"audio": np.ndarray float32 mono a 16 kHz}."""
    cfg = config.EMBED
    url = _url(cfg).rstrip("/") + "/embeddings"
    out: list[list[float] | None] = []
    for it in items:
        try:
            r = httpx.post(url, json={"model": _models(cfg)[0], "input": [{"content": [media_part(it)]}]}, timeout=900)
            r.raise_for_status()
            out.append(r.json()["data"][0]["embedding"])
        except Exception:  # noqa: BLE001  (un archivo que no se deja embeber no debe tumbar la lectura de todo el documento)
            out.append(None)
    return out


def _gemma_embed() -> bool:
    return "gemma" in config.EMBED["model"].lower()


def embed_docs(texts: list[str], titles: list[str] | None = None) -> list[list[float]]:
    titles = titles or ["none"] * len(texts)
    if _gemma_embed():  # formato recomendado por EmbeddingGemma para documentos
        inputs = [f"title: {t or 'none'} | text: {x}" for t, x in zip(titles, texts)]
    else:
        inputs = list(texts)
    out: list[list[float]] = []
    for i in range(0, len(inputs), _BATCH):
        out.extend(_embed(inputs[i : i + _BATCH]))
    return out


def embed_query(query: str) -> list[float]:
    return _embed([f"task: search result | query: {query}" if _gemma_embed() else query])[0]


# ---------- chat ----------

def describe_image(img: bytes, prompt: str) -> str:
    cfg = config.CHAT

    def call(model: str, patient: bool) -> str:
        if _is_ollama(cfg):
            r = _ollama(cfg).chat(
                model=model,
                messages=[{"role": "user", "content": prompt, "images": [img]}],
                options={"num_ctx": config.NUM_CTX, "temperature": 0.1},
            )
            return r.message.content.strip()
        content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": _image_url(img)}}]
        r = _chat_openai(cfg, model, [{"role": "user", "content": content}], 0.1, False, patient)
        return (r.choices[0].message.content or "").strip()

    return _run(cfg, "chat", call)


def complete(prompt: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    """Respuesta completa (sin streaming). Con json_mode el modelo debe devolver un objeto JSON válido."""
    cfg = config.CHAT

    def call(model: str, patient: bool) -> str:
        if _is_ollama(cfg):
            r = _ollama(cfg).chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": config.NUM_CTX, "temperature": temperature, **({"num_predict": 1500} if json_mode else {})},  # tope: un modelo pequeño a veces no cierra el JSON y sigue escribiendo
                format="json" if json_mode else None,
            )
            return r.message.content.strip()
        r = _chat_openai(cfg, model, [{"role": "user", "content": prompt}], temperature, False, patient, json_mode)
        return (r.choices[0].message.content or "").strip()

    return _run(cfg, "chat", call)


def _stream_one(cfg: dict, model: str, messages: list[dict], patient: bool):
    if _is_ollama(cfg):
        for chunk in _ollama(cfg).chat(model=model, messages=messages, stream=True, options={"num_ctx": config.NUM_CTX, "temperature": 0.2}):
            yield chunk.message.content
        return
    for chunk in _chat_openai(cfg, model, _openai_messages(messages), 0.2, True, patient):
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_stream(messages: list[dict]):
    """Respuesta en streaming. Se salta al siguiente modelo solo si el fallo ocurre antes del primer fragmento."""
    cfg = config.CHAT
    order = _order(cfg)
    errors: list[str] = []
    for i, m in enumerate(order):
        started = False
        try:
            for token in _stream_one(cfg, m, messages, patient=(len(order) == 1 or i == len(order) - 1)):
                started = True
                last_model["chat"] = m
                yield token
            return
        except Exception as e:
            if started or len(order) == 1:
                raise  # ya se mostró texto: no se puede reiniciar con otro modelo sin duplicarlo
            _failed(cfg, m, e, errors)
    raise RuntimeError("Ningún modelo respondió → " + "; ".join(errors))
