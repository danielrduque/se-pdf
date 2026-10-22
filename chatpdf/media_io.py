"""Saca la imagen o el audio originales de un fragmento (una página, un fotograma, un tramo de audio) para embeberlos directamente."""
import re
from pathlib import Path

import numpy as np

SR = 16000  # EmbeddingGemma 2 espera audio mono a 16 kHz
_TIME = re.compile(r"^(\d+):(\d{2})(?:\s*[–-]\s*(\d+):(\d{2}))?$")


def time_range(loc: str) -> tuple[float, float | None] | None:
    """'01:34–02:22' -> (94, 142); '00:48' -> (48, None); otro -> None."""
    m = _TIME.match(loc.strip())
    if not m:
        return None
    start = int(m[1]) * 60 + int(m[2])
    return float(start), (float(int(m[3]) * 60 + int(m[4])) if m[3] else None)


def page_number(loc: str) -> int | None:
    m = re.match(r"^pág\.\s*(\d+)$", loc.strip())
    return int(m[1]) if m else None


def pdf_page_png(path: Path, page: int, dpi: int = 110) -> bytes:
    import pymupdf

    with pymupdf.open(path) as doc:
        return doc[page - 1].get_pixmap(dpi=dpi).tobytes("png")


def video_frame_jpg(path: Path, t: float, max_width: int = 1024) -> bytes | None:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            return None
        if frame.shape[1] > max_width:
            frame = cv2.resize(frame, (max_width, int(frame.shape[0] * max_width / frame.shape[1])))
        return cv2.imencode(".jpg", frame)[1].tobytes()
    finally:
        cap.release()


def audio_segment(path: Path, t0: float, t1: float, max_seconds: float = 300.0) -> np.ndarray | None:
    """Audio del tramo [t0, t1] (segundos) como onda mono float32 a 16 kHz, de un audio o de la pista de audio de un video."""
    import av

    t1 = min(t1, t0 + max_seconds)  # 25 tokens por segundo y 8.192 de contexto: pasar de ~5 min no cabe
    pieces, first = [], None
    with av.open(str(path)) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            return None
        container.seek(int(max(t0 - 1.0, 0.0) * 1_000_000))
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SR)
        for frame in container.decode(stream):
            ft = float(frame.time) if frame.time is not None else None
            if ft is not None and ft + frame.samples / frame.sample_rate < t0:
                continue
            if ft is not None and ft >= t1:
                break
            for out in resampler.resample(frame):
                if first is None:
                    first = ft if ft is not None else t0
                pieces.append(out.to_ndarray().reshape(-1))
    if not pieces:
        return None
    wave = np.concatenate(pieces).astype(np.float32)
    skip = max(int((t0 - first) * SR), 0)
    wave = wave[skip : skip + int((t1 - t0) * SR)]
    return wave if wave.size >= SR // 4 else None  # menos de un cuarto de segundo no dice nada
