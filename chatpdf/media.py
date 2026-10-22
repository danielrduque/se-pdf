"""Compatibilidad de audio y video con el navegador.

Muchos videos de TikTok, WhatsApp o celulares vienen en HEVC (H.265): el navegador abre el .mp4, reproduce el audio y muestra la imagen en negro.
Aquí se detecta ese caso y se crea una copia H.264 + AAC (con el índice al inicio para empezar a verla enseguida). El original no se toca.
"""
from fractions import Fraction
from pathlib import Path

import av

from . import config
from .ingest import AUDIO_EXT

PREVIEW_MAX_SIDE = 1280  # lado mayor de la copia: un video de 1080×1920 se baja a 720×1280, que es más que suficiente para verlo
_MP4_LIKE = {".mp4", ".mov", ".m4v"}


def inspect(path: Path) -> dict:
    with av.open(str(path)) as c:
        v = c.streams.video[0].codec_context if c.streams.video else None
        a = c.streams.audio[0].codec_context if c.streams.audio else None
        return {"vcodec": v.name if v else None, "pix_fmt": v.pix_fmt if v else None, "acodec": a.name if a else None}


def needs_preview(path: Path) -> tuple[bool, str]:
    """¿Un navegador normal no podría reproducir este archivo? Devuelve (sí/no, motivo en palabras)."""
    ext = path.suffix.lower()
    if ext in AUDIO_EXT:
        return False, ""  # mp3, wav, m4a, flac, ogg, aac: todos los navegadores los reproducen
    try:
        info = inspect(path)
    except Exception:  # noqa: BLE001  si ni siquiera se puede abrir, no hay copia posible
        return False, ""
    if info["vcodec"] is None:
        return False, ""
    names = {"hevc": "HEVC (H.265)", "h264": "H.264", "mpeg4": "MPEG-4", "vp9": "VP9", "vp8": "VP8", "av1": "AV1"}
    label = names.get(info["vcodec"], info["vcodec"])
    if ext in _MP4_LIKE:
        ok = info["vcodec"] == "h264" and info["pix_fmt"] in ("yuv420p", "yuvj420p") and info["acodec"] in (None, "aac", "mp3")
    elif ext == ".webm":
        ok = info["vcodec"] in ("vp8", "vp9", "av1") and info["acodec"] in (None, "opus", "vorbis")
    else:
        ok = False  # .mkv, .avi…: los navegadores no los reproducen de forma fiable
        label = f"{label} dentro de un archivo {ext}"
    return (not ok), ("" if ok else label)


def preview_path(path: Path) -> Path:
    return config.DATA_DIR / "previews" / f"{path.name}.mp4"


def preview_ready(path: Path) -> bool:
    p = preview_path(path)
    return p.exists() and p.stat().st_mtime >= path.stat().st_mtime  # si el original cambió, la copia ya no vale


def playable_path(path: Path) -> Path:
    """El archivo que conviene servir al navegador: la copia compatible si hace falta y ya existe; si no, el original."""
    if path.suffix.lower() not in AUDIO_EXT and preview_ready(path):
        return preview_path(path)
    return path


def remove_preview(path: Path | None) -> None:
    if path is not None:
        preview_path(path).unlink(missing_ok=True)


def make_preview(src: Path) -> Path:
    """Transcodifica a H.264 + AAC en un MP4 con 'faststart'. Escribe a un temporal y lo reemplaza al terminar."""
    dst = preview_path(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp.mp4")
    try:
        with av.open(str(src)) as inp, av.open(str(tmp), "w", format="mp4", options={"movflags": "+faststart"}) as out:
            vin = inp.streams.video[0]
            ain = inp.streams.audio[0] if inp.streams.audio else None
            fps = int(round(float(vin.average_rate or vin.guessed_rate or 30))) or 30
            w, h = vin.codec_context.width, vin.codec_context.height
            scale = min(1.0, PREVIEW_MAX_SIDE / max(w, h))
            width, height = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2  # H.264 exige medidas pares
            vout = out.add_stream("libx264", rate=fps)
            vout.width, vout.height, vout.pix_fmt = width, height, "yuv420p"
            vout.options = {"crf": "24", "preset": "veryfast"}
            if ain is not None:
                aout = out.add_stream("aac", rate=44100)
                aout.layout = "stereo"
                resampler = av.AudioResampler(format="fltp", layout="stereo", rate=44100)

            last = -1
            for packet in inp.demux(*([vin] + ([ain] if ain is not None else []))):
                for frame in packet.decode():
                    if isinstance(frame, av.VideoFrame):
                        t = frame.time if frame.time is not None else (last + 1) / fps
                        last = max(last + 1, int(round(t * fps)))  # tiempos estrictamente crecientes, aunque el original sea de fps variable
                        f = frame.reformat(width=width, height=height, format="yuv420p")
                        f.pts, f.time_base = last, Fraction(1, fps)
                        for pkt in vout.encode(f):
                            out.mux(pkt)
                    else:
                        for rf in resampler.resample(frame):
                            for pkt in aout.encode(rf):
                                out.mux(pkt)
            for pkt in vout.encode():
                out.mux(pkt)
            if ain is not None:
                for rf in resampler.resample(None):
                    for pkt in aout.encode(rf):
                        out.mux(pkt)
                for pkt in aout.encode():
                    out.mux(pkt)
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
    return dst
