"""Videos que el navegador no puede reproducir (HEVC de TikTok, etc.) y su copia H.264. Ejecutar: python tests/test_media.py"""
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import av
import numpy as np

from chatpdf import config, media

tmp = Path(tempfile.mkdtemp())
config.DATA_DIR = tmp / "data"


def make_video(path: Path, codec: str, fps=10, seconds=3, w=320, h=180, audio=True, pix_fmt="yuv420p", fmt=None):
    out = av.open(str(path), "w", format=fmt) if fmt else av.open(str(path), "w")
    v = out.add_stream(codec, rate=fps)
    v.width, v.height, v.pix_fmt = w, h, pix_fmt
    if audio:
        a = out.add_stream("aac", rate=44100)
        a.layout = "mono"
    for i in range(fps * seconds):
        img = np.full((h, w, 3), (i * 7) % 255, np.uint8)
        for p in v.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(p)
    for p in v.encode():
        out.mux(p)
    if audio:
        samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, 44100 * seconds)) * 8000).astype(np.int16).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = 44100
        res = av.AudioResampler(format="fltp", layout="mono", rate=44100)
        for rf in res.resample(frame) + res.resample(None):
            for p in a.encode(rf):
                out.mux(p)
        for p in a.encode():
            out.mux(p)
    out.close()


# 1) detección de formatos compatibles e incompatibles
good = tmp / "bueno.mp4"
make_video(good, "libx264")
assert media.needs_preview(good) == (False, "")

bad = tmp / "tiktok.mp4"  # MPEG-4 parte 2 dentro de un .mp4: un navegador tampoco lo reproduce (mismo efecto que HEVC)
make_video(bad, "mpeg4")
need, why = media.needs_preview(bad)
assert need and "MPEG-4" in why, (need, why)

avi = tmp / "viejo.avi"
make_video(avi, "mpeg4", audio=False, fmt="avi")
need, why = media.needs_preview(avi)
assert need and ".avi" in why, (need, why)

wav = tmp / "voz.wav"
wav.write_bytes(b"RIFF....WAVE")
assert media.needs_preview(wav) == (False, "")  # el audio nunca necesita copia (y ni siquiera se abre)
print("detección OK:", why)

# 2) la copia: H.264 + AAC, mismas dimensiones y duración, con el índice (moov) al inicio
assert not media.preview_ready(bad) and media.playable_path(bad) == bad
dst = media.make_preview(bad)
info = media.inspect(dst)
assert info == {"vcodec": "h264", "pix_fmt": "yuv420p", "acodec": "aac"}, info
assert media.needs_preview(dst) == (False, "")  # la copia sí la reproduce cualquier navegador
with av.open(str(dst)) as c:
    v = c.streams.video[0]
    assert (v.codec_context.width, v.codec_context.height) == (320, 180)
    assert abs(float(c.duration) / 1e6 - 3.0) < 0.5, c.duration
    frames = sum(1 for f in c.decode(video=0))
    assert frames >= 28, frames  # 10 fps × 3 s
assert b"moov" in dst.read_bytes()[:65536], "faststart: el índice debe estar al inicio"
assert media.preview_ready(bad) and media.playable_path(bad) == dst
assert not list(dst.parent.glob("*.tmp.mp4"))
print(f"copia H.264+AAC OK: {dst.stat().st_size // 1024} KB")

# 3) video sin audio y video grande (se reduce a 1280 de lado mayor, con medidas pares)
silent = tmp / "mudo.avi"
make_video(silent, "mpeg4", audio=False, fmt="avi", w=1920, h=1080, seconds=1)
d2 = media.make_preview(silent)
with av.open(str(d2)) as c:
    assert not c.streams.audio and (c.streams.video[0].codec_context.width, c.streams.video[0].codec_context.height) == (1280, 720)
print("sin audio y reducción de tamaño OK")

# 4) si el original cambia, la copia vieja deja de valer
import os, time
os.utime(bad, (time.time() + 5, time.time() + 5))
assert not media.preview_ready(bad) and media.playable_path(bad) == bad

# 5) quitar la copia
media.remove_preview(bad)
assert not media.preview_path(bad).exists()
media.remove_preview(None)
print("TODO OK")
