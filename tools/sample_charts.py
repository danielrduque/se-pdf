"""Gráficos e ilustraciones (matplotlib) para la base de conocimiento de ejemplo. Cada función devuelve un PNG en bytes."""
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, patches

NAVY, GREEN, BLUE, ORANGE = "#12284C", "#1F8A5B", "#2F6DB5", "#E08A1E"
LIGHT, GREY, RED, SOIL = "#EEF3F8", "#5A6677", "#C0392B", "#8B6B4A"

_fonts = Path("C:/Windows/Fonts")
if (_fonts / "calibri.ttf").exists():
    for f in ("calibri.ttf", "calibrib.ttf", "calibrii.ttf"):
        if (_fonts / f).exists():
            font_manager.fontManager.addfont(str(_fonts / f))
    plt.rcParams["font.family"] = "Calibri"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#B8C2CC", "axes.labelcolor": GREY, "xtick.color": GREY, "ytick.color": GREY})


def _png(fig, dpi=200) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _clean(ax, left=False):
    for s in ("top", "right") + (("left",) if left else ()):
        ax.spines[s].set_visible(False)


def sales_bar() -> bytes:
    q, v = ["T1", "T2", "T3", "T4"], [120, 150, 210, 180]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bars = ax.bar(q, v, width=0.58, color=[BLUE if x != max(v) else GREEN for x in v], zorder=3)
    for b, x in zip(bars, v):
        ax.text(b.get_x() + b.get_width() / 2, x + 5, str(x), ha="center", fontsize=13, fontweight="bold", color=NAVY)
    ax.set_ylim(0, 250)
    ax.set_ylabel("Millones de pesos")
    ax.yaxis.grid(True, color="#E3E8EE", zorder=0)
    ax.set_title("Ventas 2026 por trimestre", loc="left", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    _clean(ax)
    return _png(fig)


def product_donut() -> bytes:
    labels, share = ["Sensores de riego", "Controladores", "Servicios de instalación"], [48, 31, 21]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.pie(share, colors=[BLUE, GREEN, ORANGE], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
    ax.text(0, 0.04, "Ventas", ha="center", fontsize=12, color=GREY)
    ax.text(0, -0.2, "2026", ha="center", fontsize=16, fontweight="bold", color=NAVY)
    ax.legend([f"{l}  ·  {s} %" for l, s in zip(labels, share)], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=12)
    ax.set_title("Participación por línea de producto", loc="left", fontsize=14, fontweight="bold", color=NAVY)
    return _png(fig)


def budget_bars() -> bytes:
    areas, v = ["Capacitación", "Marketing", "Operaciones", "Tecnología"], [30, 45, 85, 120]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    bars = ax.barh(areas, v, height=0.55, color=[BLUE, BLUE, BLUE, GREEN], zorder=3)
    for b, x in zip(bars, v):
        ax.text(x + 2.5, b.get_y() + b.get_height() / 2, f"{x} mil USD", va="center", fontsize=12, fontweight="bold", color=NAVY)
    ax.set_xlim(0, 160)
    ax.xaxis.grid(True, color="#E3E8EE", zorder=0)
    ax.set_xlabel("Miles de dólares")
    ax.set_title("Inversión 2027 por área", loc="left", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    _clean(ax, left=True)
    ax.tick_params(axis="y", length=0, labelsize=12)
    return _png(fig)


def gantt() -> bytes:
    months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    tasks = [("Contratar 2 técnicos", 2, 2, BLUE), ("Piloto en 3 fincas", 5, 3, GREEN), ("Expansión a 12 fincas", 8, 2, ORANGE)]
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    for i, (name, start, length, col) in enumerate(tasks):
        ax.barh(i, length, left=start, height=0.5, color=col, zorder=3)
        ax.text(start + length / 2, i, f"{months[start]}–{months[start + length - 1]}", ha="center", va="center", color="white", fontsize=10, fontweight="bold", zorder=4)
    ax.plot(10.5, 3, marker="D", markersize=14, color=RED, zorder=4)
    ax.text(10.5, 3.45, "Nov", ha="center", fontsize=10, fontweight="bold", color=RED)
    ax.set_yticks(range(4), [t[0] for t in tasks] + ["Lanzamiento oficial"], fontsize=12)
    ax.set_xticks(np.arange(12) + 0.5, months)
    ax.set_xlim(0, 12)
    ax.set_ylim(3.9, -0.6)
    ax.xaxis.grid(True, color="#E3E8EE", zorder=0)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    ax.set_title("Hitos del proyecto 2027", loc="left", fontsize=14, fontweight="bold", color=NAVY, pad=28)
    _clean(ax, left=True)
    ax.spines["bottom"].set_visible(False)
    return _png(fig)


def zones_map() -> bytes:
    zones = [("Zona A", 12, 4, 3, BLUE, 0, 3.4), ("Zona B", 18, 6, 3, GREEN, 3.6, 7.4), ("Zona C", 9, 3, 3, ORANGE, 7.6, 10.4)]
    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    for name, n, cols, rows, col, x0, x1 in zones:
        ax.add_patch(patches.FancyBboxPatch((x0, 0.3), x1 - x0, 3.1, boxstyle="round,pad=0.02,rounding_size=0.12", fc=col, alpha=0.13, ec=col, lw=1.6))
        xs = np.linspace(x0 + 0.45, x1 - 0.45, cols)
        ys = np.linspace(1.2, 2.5, rows)
        pts = [(x, y) for y in ys for x in xs]
        assert len(pts) == n
        ax.scatter(*zip(*pts), s=80, color=col, zorder=3, edgecolor="white", linewidth=1.2)
        ax.text((x0 + x1) / 2, 3.05, name, ha="center", fontsize=13, fontweight="bold", color=col)
        ax.text((x0 + x1) / 2, 0.52, f"{n} sensores", ha="center", fontsize=11.5, color=NAVY)
    ax.plot([5.2], [-0.35], marker="^", markersize=12, color=RED, clip_on=False)
    ax.text(5.55, -0.45, "Pasarela LoRa", fontsize=10.5, color=GREY, va="center")
    ax.set_xlim(-0.2, 10.6)
    ax.set_ylim(-0.7, 3.7)
    ax.axis("off")
    ax.set_title("Distribución de sensores por zona de la finca", loc="left", fontsize=14, fontweight="bold", color=NAVY)
    return _png(fig)


def trench_diagram() -> bytes:
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.add_patch(patches.Rectangle((0, -2.2), 12, 2.2, fc=SOIL, alpha=0.55, ec="none"))
    ax.add_patch(patches.Rectangle((0, 0), 12, 0.12, fc=GREEN, ec="none"))
    ax.add_patch(patches.Rectangle((2.0, -1.5), 8.0, 1.5, fc="#D9C3A5", ec="#6B4E31", lw=1.2, ls="--"))
    ax.plot([2.0, 10.0], [-1.35, -1.35], color=ORANGE, lw=3, solid_capstyle="round")
    for x in (2.0, 10.0):
        ax.plot([x], [0.08], marker="s", markersize=11, color=NAVY)
    ax.text(2.0, 0.55, "Sensor", ha="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.text(10.0, 0.55, "Pasarela", ha="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.annotate("", xy=(11.2, -1.35), xytext=(11.2, 0), arrowprops=dict(arrowstyle="<->", color=NAVY))
    ax.text(11.35, -0.68, "30 cm", fontsize=11, fontweight="bold", color=NAVY, va="center")
    ax.text(6.0, -1.08, "Cable sin tensión", ha="center", fontsize=11, color="#7A4B00", fontweight="bold")
    ax.set_xlim(0, 12.6)
    ax.set_ylim(-2.2, 1.0)
    ax.axis("off")
    ax.set_title("Corte de la zanja del cable", loc="left", fontsize=14, fontweight="bold", color=NAVY)
    return _png(fig)


def sensor_diagram() -> bytes:
    fig, ax = plt.subplots(figsize=(4.4, 4.6))
    ax.add_patch(patches.Rectangle((-2, -3.2), 4, 3.2, fc=SOIL, alpha=0.5, ec="none"))
    ax.add_patch(patches.Rectangle((-2, 0), 4, 0.1, fc=GREEN, ec="none"))
    ax.add_patch(patches.FancyBboxPatch((-0.45, 0.1), 0.9, 1.5, boxstyle="round,pad=0.03,rounding_size=0.12", fc=NAVY, ec="none"))
    ax.add_patch(patches.Rectangle((-0.12, -2.3), 0.24, 2.3, fc="#C9D3DD", ec=GREY, lw=1))
    ax.plot([0, 0], [1.6, 2.7], color=GREY, lw=3)
    ax.add_patch(patches.Circle((0, 2.78), 0.12, fc=RED))
    for r in (0.35, 0.6):
        ax.add_patch(patches.Arc((0, 2.78), 2 * r, 2 * r, theta1=30, theta2=150, color=RED, lw=1.5))
    for (x, y, tx, ty, label) in [(0.12, 2.8, 1.25, 2.8, "Antena LoRa"), (0.45, 1.1, 1.25, 1.35, "Carcasa IP67"), (0.45, 0.55, 1.25, 0.65, "Batería de 12 V"), (0.12, -1.6, 1.25, -1.3, "Sonda de humedad")]:
        ax.annotate(label, xy=(x, y), xytext=(tx, ty), fontsize=11.5, color=NAVY, fontweight="bold", va="center", arrowprops=dict(arrowstyle="-", color=GREY, lw=1))
    ax.annotate("", xy=(-1.0, -2.3), xytext=(-1.0, 0), arrowprops=dict(arrowstyle="<->", color=NAVY))
    ax.text(-1.15, -1.15, "20 cm", rotation=90, ha="right", va="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.set_xlim(-2, 4.3)
    ax.set_ylim(-3.2, 3.7)
    ax.axis("off")
    return _png(fig)


def orgchart() -> bytes:
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    def box(cx, cy, name, role, col, w=2.5, h=1.0):
        ax.add_patch(patches.FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc="white", ec=col, lw=2, zorder=3))
        ax.add_patch(patches.Rectangle((cx - w / 2, cy + h / 2 - 0.12), w, 0.14, fc=col, ec="none", zorder=4))
        ax.text(cx, cy + 0.12, name, ha="center", va="center", fontsize=13, fontweight="bold", color=NAVY, zorder=5)
        ax.text(cx, cy - 0.22, role, ha="center", va="center", fontsize=10.5, color=GREY, zorder=5)
    box(5, 4.2, "Carlos Ruiz", "Gerente general", NAVY, w=3.0)
    people = [(1.7, "María González", "Directora de proyectos", GREEN), (5.0, "Luis Pardo", "Jefe de ingeniería", BLUE), (8.3, "Ana Torres", "Coordinadora de compras", ORANGE)]
    ax.plot([5, 5], [3.7, 3.2], color=GREY, lw=1.6, zorder=1)
    ax.plot([1.7, 8.3], [3.2, 3.2], color=GREY, lw=1.6, zorder=1)
    for x, n, r, c in people:
        ax.plot([x, x], [3.2, 2.5], color=GREY, lw=1.6, zorder=1)
        box(x, 2.0, n, r, c, w=2.9)
    ax.text(0, 5.1, "Organigrama · Agroandina S.A.S.", fontsize=15, fontweight="bold", color=NAVY)
    ax.set_xlim(-0.2, 10.2)
    ax.set_ylim(1.2, 5.3)
    ax.axis("off")
    return _png(fig)


def slide(title: str, sub: str, idx: int, total: int) -> np.ndarray:
    """Diapositiva 1280x720 (array RGB) para el video de ejemplo."""
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    grad = np.linspace(0, 1, 256)[None, :]
    ax.imshow(grad, extent=[0, 12.8, 0, 7.2], cmap=matplotlib.colors.LinearSegmentedColormap.from_list("g", ["#0E1F3D", "#1D4A7A"]), aspect="auto")
    ax.add_patch(patches.Circle((11.3, 6.2), 2.2, fc="white", alpha=0.05))
    ax.add_patch(patches.Circle((12.4, 1.0), 1.4, fc=GREEN, alpha=0.18))
    ax.add_patch(patches.Rectangle((0.8, 3.55), 1.6, 0.07, fc="#5BD08F", ec="none"))
    ax.text(0.8, 4.2, title, fontsize=40, fontweight="bold", color="white", va="bottom")
    ax.text(0.8, 3.2, sub, fontsize=21, color="#C9DCF2", va="top", wrap=True)
    ax.text(0.8, 0.6, "Agroandina S.A.S. · Capacitación de seguridad", fontsize=14, color="#8FB0D6")
    ax.text(12.0, 0.6, f"{idx} / {total}", fontsize=16, color="#8FB0D6", ha="right")
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 7.2)
    ax.axis("off")
    fig.canvas.draw()
    arr = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return arr
