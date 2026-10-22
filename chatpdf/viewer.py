"""Convierte la ubicación de una cita ('pág. 7', '02:14–02:40') en algo que se pueda mostrar."""
import math
import re

import pymupdf

_PAGE = re.compile(r"pág\.\s*(\d+)")
_TIME = re.compile(r"(\d+):(\d{2})")


def parse_loc(loc: str) -> tuple[str, int] | None:
    """('page', n) para PDFs, ('time', segundos) para audio/video; None si no aplica."""
    if m := _PAGE.search(loc):
        return "page", int(m.group(1))
    if m := _TIME.match(loc):
        return "time", int(m.group(1)) * 60 + int(m.group(2))
    return None


YELLOW = (1.0, 0.83, 0.0)


def _page(doc: pymupdf.Document, page_no: int) -> pymupdf.Page:
    """Página `page_no` (desde 1). Fuera de rango lanza IndexError: con 0 o negativos Python devolvería la última página."""
    if not 1 <= page_no <= len(doc):
        raise IndexError(page_no)
    return doc[page_no - 1]


def render_page(pdf_path: str, page_no: int, text: str, dpi: int = 110, mark_images: bool = False) -> tuple[bytes, int]:
    """Renderiza la página con lo citado en amarillo. Devuelve (png, nº de marcas).

    - `text`: el texto de los fragmentos citados (varios se unen con saltos de línea): cada línea que aparece en la página se resalta.
    - `mark_images`: la cita viene de una imagen (gráfico, PDF escaneado) que no tiene texto que resaltar; se enmarca la propia imagen.
    """
    found = 0
    with pymupdf.open(pdf_path) as doc:
        page = _page(doc, page_no)
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 6 or line.startswith("[Contenido visual]"):
                continue
            for rect in page.search_for(line[:200]):
                page.add_highlight_annot(rect)
                found += 1
        if mark_images:
            area = page.rect.width * page.rect.height
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    big = rect.width * rect.height > 0.6 * area  # una página escaneada es una sola imagen: velo suave y borde grueso
                    page.draw_rect(rect, color=YELLOW, fill=YELLOW, fill_opacity=0.10 if big else 0.28, width=4 if big else 2.5)
                    found += 1
        return page.get_pixmap(dpi=dpi).tobytes("png"), found


# ---------- zona marcada a mano en una página ----------

def _zone(page: pymupdf.Page, rect: list[float]) -> pymupdf.Rect:
    """Fracciones de la página (0-1, como se ve en pantalla) -> rectángulo del PDF. Lanza ValueError si es demasiado pequeña."""
    if len(rect) != 4:
        raise ValueError("La zona debe ser [x0, y0, x1, y1].")
    if not all(math.isfinite(float(v)) for v in rect):
        raise ValueError("La zona tiene valores no válidos.")
    x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in rect)
    x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        raise ValueError("La zona es demasiado pequeña: arrastra un rectángulo más grande.")
    r = page.rect
    return pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)


def read_zone(pdf_path: str, page_no: int, rect: list[float]) -> dict:
    """Lo que hay dentro de la zona: su texto y si conviene mirarla como imagen (gráficos, fotos, páginas escaneadas)."""
    with pymupdf.open(pdf_path) as doc:
        page = _page(doc, page_no)
        clip = _zone(page, rect)
        text = re.sub(r"\n{3,}", "\n\n", page.get_text("text", clip=clip * page.derotation_matrix).strip())
        area = clip.width * clip.height
        covered = sum((pymupdf.Rect(i["bbox"]) & clip).get_area() for i in page.get_image_info())
        drawings = sum(1 for d in page.get_drawings() if d["rect"].intersects(clip) and d["rect"].get_area() < 0.5 * page.rect.get_area())
        return {"text": text, "visual": covered > 0.25 * area or drawings >= 12 or len(text) < 40}


def render_zone(pdf_path: str, page_no: int, rect: list[float], dpi: int = 150) -> bytes:
    with pymupdf.open(pdf_path) as doc:
        page = _page(doc, page_no)
        return page.get_pixmap(dpi=dpi, clip=_zone(page, rect)).tobytes("png")
