"""Resaltado amarillo de lo citado en la página del PDF. Ejecutar: python tests/test_viewer.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pymupdf

from chatpdf import viewer

tmp = Path(tempfile.mkdtemp())


def yellow_pixels(png: bytes) -> int:
    pix = pymupdf.Pixmap(png)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[..., :3].astype(int)
    return int(((a[..., 0] > 200) & (a[..., 1] > 150) & (a[..., 2] < 120)).sum())


def gray_image() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 240, 120), False)
    pix.set_rect(pix.irect, (140,))
    return pix.tobytes("png")


pdf = pymupdf.open()
p1 = pdf.new_page()
lines = ["El ocelote es un felino que vive en las selvas de America.", "Caza de noche y come roedores pequenos.", "Mide entre cincuenta y noventa centimetros de largo."]
for i, t in enumerate(lines):
    p1.insert_text((72, 100 + 22 * i), t, fontsize=12)
p2 = pdf.new_page()  # una imagen pequeña (como un gráfico dentro de la página) y un poco de texto
p2.insert_text((72, 90), "Figura 1. Ventas por trimestre.", fontsize=12)
p2.insert_image(pymupdf.Rect(72, 120, 312, 240), stream=gray_image())
p3 = pdf.new_page()  # una página escaneada: toda la página es una sola imagen
p3.insert_image(p3.rect, stream=gray_image())
path = tmp / "demo.pdf"
pdf.save(path)

render = lambda page, text="", **kw: viewer.render_page(str(path), page, text, **kw)

# 1) sin citas no hay amarillo
png, found = render(1)
assert found == 0 and yellow_pixels(png) == 0

# 2) el texto de un fragmento se resalta; con más líneas citadas hay más amarillo
png1, f1 = render(1, lines[0])
png3, f3 = render(1, "\n".join(lines))
y1, y3 = yellow_pixels(png1), yellow_pixels(png3)
assert f1 == 1 and f3 == 3 and 0 < y1 < y3, (f1, f3, y1, y3)
print(f"texto: 1 línea -> {y1} px amarillos | 3 líneas -> {y3} px")

# 3) una cita que viene de una imagen: se enmarca la imagen (no hay texto que resaltar)
png, f = render(2, "", mark_images=True)
assert f == 1 and yellow_pixels(png) > 0
png_no, f_no = render(2, "")
assert f_no == 0 and yellow_pixels(png_no) == 0  # sin mark_images, la imagen no se toca
print(f"imagen dentro de la página: {yellow_pixels(png)} px amarillos")

# 4) página escaneada completa: borde grueso y velo suave
png, f = render(3, "", mark_images=True)
assert f == 1 and yellow_pixels(png) > 0

# 5) texto y imagen a la vez, en la misma página
png, f = render(2, "Figura 1. Ventas por trimestre.", mark_images=True)
assert f == 2 and yellow_pixels(png) > yellow_pixels(render(2, "", mark_images=True)[0])

# 6) el original no se modifica (las marcas solo existen en la imagen que se devuelve)
assert pymupdf.open(path)[0].first_annot is None

# 7) página inexistente
try:
    render(9)
    raise SystemExit("debió fallar")
except IndexError:
    pass
print("TODO OK")
