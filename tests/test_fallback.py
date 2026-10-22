"""Salto entre modelos con un servidor falso compatible con OpenAI. Ejecutar: python tests/test_fallback.py"""
import json
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import AuthenticationError

from chatpdf import config, llm

calls = Counter()


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionError, BrokenPipeError):
            pass  # el cliente se fue (timeout del modelo "lento"): es lo esperado

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m = req["model"]
        calls[m] += 1
        if m.startswith("muerto"):
            return self._json(404, {"error": {"message": "model not found", "type": "invalid_request_error", "code": "model_not_found"}})
        if m == "limitado":
            return self._json(429, {"error": {"message": "quota exceeded", "type": "rate_limit_error"}})
        if m == "auth":
            return self._json(401, {"error": {"message": "invalid key", "type": "authentication_error"}})
        if m == "lento":
            time.sleep(3)
        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for part in ("hola ", "desde ", m):
                chunk = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": m,
                         "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return
        self._json(200, {"id": "x", "object": "chat.completion", "created": 0, "model": m,
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": f"respuesta de {m}"}, "finish_reason": "stop"}]})


server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
config.CHAT.update(backend="openai", base_url=f"http://127.0.0.1:{server.server_port}/v1", api_key="k")
llm._FAST_TIMEOUT = 1  # el modelo "lento" tarda 3 s


def use(models: str):
    config.CHAT["model"] = models
    llm._paused.clear()
    calls.clear()


# 1) un solo modelo: comportamiento normal
use("bueno")
assert llm.complete("hola") == "respuesta de bueno"

# 2) salta de un modelo inexistente y de uno con el cupo agotado hasta uno que contesta
use("muerto, limitado, bueno")
assert llm.complete("hola") == "respuesta de bueno" and llm.last_model["chat"] == "bueno"
assert calls["muerto"] == 1 and calls["limitado"] >= 1 and calls["bueno"] == 1
print("salta muerto (404) y limitado (429) -> contesta 'bueno'")

# 3) los que fallaron quedan en pausa: la siguiente pregunta va directa al que funciona
before = dict(calls)
assert llm._order(config.CHAT)[0] == "bueno"
assert llm.complete("otra") == "respuesta de bueno"
assert calls["muerto"] == before["muerto"] and calls["limitado"] == before["limitado"]
print("modelos caídos en pausa: la 2ª pregunta no los vuelve a intentar")

# 4) pasada la pausa, se vuelven a probar
llm._paused.clear()
llm.complete("hola")
assert calls["muerto"] == before["muerto"] + 1

# 5) streaming: el modelo lento (timeout) se salta antes del primer token
use("lento, bueno")
t = time.time()
text = "".join(llm.chat_stream([{"role": "user", "content": "hola"}]))
assert text == "hola desde bueno", text
print(f"streaming salta el modelo lento en {time.time() - t:.1f} s -> '{text}'")

# 6) también en visión
use("muerto, bueno")
assert llm.describe_image(b"\x89PNG\r\n\x1a\n" + b"0" * 20, "describe") == "respuesta de bueno"

# 7) si todos fallan: error claro con los nombres
use("muerto1, muerto2")
try:
    llm.complete("hola")
    raise SystemExit("debió fallar")
except RuntimeError as e:
    assert "muerto1" in str(e) and "muerto2" in str(e), e
    print("todos fallan ->", e)

# 8) clave inválida: no se prueban los demás modelos (fallarían igual)
use("auth, bueno")
try:
    llm.complete("hola")
    raise SystemExit("debió fallar")
except AuthenticationError:
    assert calls["bueno"] == 0
    print("clave inválida: se corta de inmediato, sin probar los demás")

# 9) los embeddings usan solo el primer modelo de la lista
config.EMBED.update(model="uno, dos")
assert llm._models(config.EMBED)[0] == "uno"

server.shutdown()
print("TODO OK")
