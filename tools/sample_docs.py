"""Documentos PDF con diseño corporativo (reportlab) para la base de conocimiento de ejemplo.

Datos ficticios y coherentes entre archivos. Las cifras que solo deben poder leerse mirando un gráfico NO aparecen en el texto.
"""
import io
from pathlib import Path

import numpy as np
from PIL import Image as PILImage
from PIL import ImageFilter
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

import sample_charts as ch

W, H = A4
NAVY, GREEN, BLUE, ORANGE, RED = (colors.HexColor(c) for c in (ch.NAVY, ch.GREEN, ch.BLUE, ch.ORANGE, ch.RED))
LIGHT, LINE, INK, GREY = colors.HexColor("#F2F6FA"), colors.HexColor("#D5DDE6"), colors.HexColor("#26303B"), colors.HexColor("#5A6677")
MINT = colors.HexColor("#7FE0A8")

# ---------- fuentes ----------
REG, BOLD, ITAL = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
_win = Path("C:/Windows/Fonts")
if all((_win / f).exists() for f in ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf")):
    for name, f in (("Calibri", "calibri.ttf"), ("Calibri-Bold", "calibrib.ttf"), ("Calibri-Italic", "calibrii.ttf"), ("Calibri-BoldItalic", "calibriz.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(_win / f)))
    pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold", italic="Calibri-Italic", boldItalic="Calibri-BoldItalic")
    REG, BOLD, ITAL = "Calibri", "Calibri-Bold", "Calibri-Italic"

S = {
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=20, leading=24, textColor=NAVY, spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=13.5, leading=17, textColor=GREEN, spaceBefore=12, spaceAfter=4),
    "body": ParagraphStyle("body", fontName=REG, fontSize=11.5, leading=17, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=7),
    "bullet": ParagraphStyle("bullet", fontName=REG, fontSize=11.5, leading=17, textColor=INK, leftIndent=16, bulletIndent=4, spaceAfter=3),
    "small": ParagraphStyle("small", fontName=REG, fontSize=9, leading=12, textColor=GREY),
    "caption": ParagraphStyle("caption", fontName=ITAL, fontSize=9.5, leading=12, textColor=GREY, alignment=1, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName=REG, fontSize=11, leading=15, textColor=INK),
    "head": ParagraphStyle("head", fontName=BOLD, fontSize=11, leading=15, textColor=colors.white),
    "kpi": ParagraphStyle("kpi", fontName=BOLD, fontSize=28, leading=32, alignment=1),
    "kpil": ParagraphStyle("kpil", fontName=REG, fontSize=10, leading=13, textColor=GREY, alignment=1),
}


# ---------- bloques reutilizables ----------

def H1(t): return Paragraph(t, S["h1"])
def H2(t): return Paragraph(t, S["h2"])
def P(t): return Paragraph(t, S["body"])
def bullets(items): return [Paragraph(t, S["bullet"], bulletText="•") for t in items]
def numbered(items): return [Paragraph(t, S["bullet"], bulletText=f"{i}.") for i, t in enumerate(items, 1)]


def pic(png: bytes, width_cm: float, caption: str | None = None):
    w, h = PILImage.open(io.BytesIO(png)).size
    im = Image(io.BytesIO(png), width=width_cm * cm, height=width_cm * cm * h / w)
    im.hAlign = "CENTER"
    return KeepTogether([im, Paragraph(caption, S["caption"])]) if caption else im


def callout(title: str, text: str, color=BLUE):
    t = Table([[Paragraph(f'<font color="{color.hexval().replace("0x", "#")}"><b>{title}</b></font><br/>{text}', S["cell"])]], colWidths=[W - 4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8FC")), ("LINEBEFORE", (0, 0), (0, -1), 4, color),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return KeepTogether([t, Spacer(1, 8)])


def kpis(cards):
    """cards: [(valor, etiqueta, color)] -> fila de tarjetas con el número grande."""
    n, gap = len(cards), 0.35 * cm
    cw = (W - 4 * cm - gap * (n - 1)) / n
    cells, widths, style = [], [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, (v, label, col) in enumerate(cards):
        cells.append([Paragraph(f'<font color="{col.hexval().replace("0x", "#")}">{v}</font>', S["kpi"]), Paragraph(label, S["kpil"])])
        widths.append(cw)
        style += [("BACKGROUND", (len(widths) - 1, 0), (len(widths) - 1, 0), LIGHT), ("LINEABOVE", (len(widths) - 1, 0), (len(widths) - 1, 0), 3, col),
                  ("TOPPADDING", (len(widths) - 1, 0), (len(widths) - 1, 0), 12), ("BOTTOMPADDING", (len(widths) - 1, 0), (len(widths) - 1, 0), 12)]
        if i < n - 1:
            cells.append("")
            widths.append(gap)
    t = Table([cells], colWidths=widths)
    t.setStyle(TableStyle(style))
    return KeepTogether([t, Spacer(1, 10)])


def data_table(rows, widths_cm, zebra=True):
    body = [[Paragraph(str(c), S["head" if r == 0 else "cell"]) for c in row] for r, row in enumerate(rows)]
    t = Table(body, colWidths=[w * cm for w in widths_cm], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return KeepTogether([t, Spacer(1, 10)])


def chip(text, color):
    return f'<font color="{color.hexval().replace("0x", "#")}"><b>{text}</b></font>'


def title_band(tag, title, subtitle):
    t = Table([[Paragraph(f'<font color="#7FE0A8" size="10"><b>{tag}</b></font><br/><font color="white" size="26"><b>{title}</b></font><br/>'
                          f'<font color="#C9DCF2" size="11">{subtitle}</font>', ParagraphStyle("b", fontName=REG, leading=30))]], colWidths=[W - 4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LINEBELOW", (0, 0), (-1, -1), 4, GREEN), ("LEFTPADDING", (0, 0), (-1, -1), 18),
                           ("TOPPADDING", (0, 0), (-1, -1), 18), ("BOTTOMPADDING", (0, 0), (-1, -1), 16)]))
    return [t, Spacer(1, 14)]


# ---------- página: portada, encabezado y pie ----------

def draw_cover(c, doc, data):
    c.saveState()
    top = H * 0.46
    c.setFillColor(NAVY); c.rect(0, top, W, H - top, fill=1, stroke=0)
    c.setFillColor(GREEN); c.rect(0, top, W, 7, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFillAlpha(0.06); c.circle(W - 3 * cm, H - 4.5 * cm, 5.5 * cm, fill=1, stroke=0)
    c.setFillColor(GREEN); c.setFillAlpha(0.35); c.circle(W - 1.2 * cm, top + 1.6 * cm, 2.4 * cm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFillColor(MINT); c.circle(2.35 * cm, H - 2.35 * cm, 0.28 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont(BOLD, 15); c.drawString(3 * cm, H - 2.5 * cm, "AGROANDINA")
    c.setFont(REG, 10); c.setFillColor(colors.HexColor("#C9DCF2")); c.drawString(3 * cm, H - 3.05 * cm, "Tecnología para el campo")
    c.setFillColor(MINT); c.setFont(BOLD, 12); c.drawString(2 * cm, top + 8.4 * cm, data["tag"])
    y = top + 6.9 * cm
    c.setFillColor(colors.white); c.setFont(BOLD, 38)
    for line in simpleSplit(data["title"], BOLD, 38, W - 6 * cm):
        c.drawString(2 * cm, y, line); y -= 1.6 * cm
    c.setFillColor(colors.HexColor("#C9DCF2")); c.setFont(REG, 15)
    for line in simpleSplit(data["subtitle"], REG, 15, W - 6 * cm):
        c.drawString(2 * cm, y - 0.2 * cm, line); y -= 0.75 * cm
    c.setFillColor(MINT); c.rect(2 * cm, top + 1.2 * cm, 2.2 * cm, 4, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#C9DCF2")); c.setFont(REG, 11); c.drawString(2 * cm, top + 0.6 * cm, data["date"])
    c.restoreState()


def _header(c, doc):
    c.saveState()
    c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(2 * cm, H - 1.75 * cm, W - 2 * cm, H - 1.75 * cm)
    c.setFillColor(GREEN); c.circle(2.12 * cm, H - 1.32 * cm, 0.12 * cm, fill=1, stroke=0)
    c.setFont(BOLD, 9.5); c.setFillColor(NAVY); c.drawString(2.4 * cm, H - 1.45 * cm, "AGROANDINA")
    c.setFont(REG, 9.5); c.setFillColor(GREY); c.drawRightString(W - 2 * cm, H - 1.45 * cm, doc.title)
    c.restoreState()


def _canvas_with_footer(skip_first: bool):
    class Numbered(canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for i, state in enumerate(self._pages, 1):
                self.__dict__.update(state)
                if not (skip_first and i == 1):
                    self.setStrokeColor(LINE); self.setLineWidth(0.8); self.line(2 * cm, 1.75 * cm, W - 2 * cm, 1.75 * cm)
                    self.setFont(REG, 9); self.setFillColor(GREY)
                    self.drawString(2 * cm, 1.2 * cm, "Agroandina S.A.S. · Documento de ejemplo con datos ficticios")
                    self.drawRightString(W - 2 * cm, 1.2 * cm, f"Página {i} de {total}")
                super().showPage()
            super().save()
    return Numbered


def build(path: Path, story: list, title: str, cover: dict | None = None):
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.5 * cm, bottomMargin=2.3 * cm,
                          title=title, author="Agroandina S.A.S.")
    body = PageTemplate(id="body", frames=[Frame(2 * cm, 2.3 * cm, W - 4 * cm, H - 4.8 * cm, id="f")], onPage=_header)
    if cover:
        top = H * 0.46
        cover_t = PageTemplate(id="cover", frames=[Frame(2 * cm, 2.3 * cm, W - 4 * cm, top - 3.6 * cm, id="c")], onPage=lambda c, d: draw_cover(c, d, cover))
        doc.addPageTemplates([cover_t, body])
        story = story + []
    else:
        doc.addPageTemplates([body])
    doc.build(story, canvasmaker=_canvas_with_footer(skip_first=bool(cover)))


# ---------- documentos ----------

def manual_sensor(path: Path):
    s = title_band("MANUAL TÉCNICO · VERSIÓN 2.1", "Sensor de humedad AG-200", "Fabricado por Andina SA, Bogotá · Distribuido por Agroandina S.A.S.")
    left = [H2("Descripción general"),
            P("El AG-200 mide la humedad del suelo a la profundidad de las raíces y envía la lectura por radio a la pasarela de la finca. "
              "Funciona con batería, resiste la intemperie y está pensado para instalarse una vez y olvidarse durante meses."),
            H2("Características destacadas")] + bullets(["Comunicación inalámbrica de largo alcance", "Carcasa sellada contra polvo y agua", "Lectura cada 15 minutos", "Indicador luminoso de estado"])
    two = Table([[left, pic(ch.sensor_diagram(), 5.6)]], colWidths=[10.4 * cm, 6.6 * cm])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    s += [two, H1("1. Especificaciones"),
          data_table([["Característica", "Valor"], ["Rango de temperatura de operación", "-10 °C a 60 °C"], ["Alimentación", "Batería de 12 V"],
                      ["Comunicación", "LoRa 868 MHz, alcance de 2 km"], ["Protección", "IP67"], ["Garantía", "24 meses"]], [8.5, 8.5])]
    s += [PageBreak(), H1("2. Instalación")]
    s += numbered(["Elija un punto despejado, a un mínimo de 50 cm de la línea de goteo.", "Entierre la sonda a 20 cm de profundidad, sin forzarla.",
                   "Oriente la antena hacia el norte.", "Conecte la batería y verifique que el indicador luminoso parpadee en verde.", "Cubra el hoyo y compacte la tierra alrededor de la sonda."])
    s += [Spacer(1, 8), callout("Advertencia", "No instale el sensor con el conector mojado: la humedad en los contactos produce lecturas falsas y puede dañar la sonda.", ORANGE),
          H1("3. Calibración"),
          P("El sensor debe calibrarse cada 6 meses con la solución patrón de 1413 µS/cm. Sumerja la sonda durante 60 segundos y mantenga pulsado "
            "el botón de calibración hasta que el indicador parpadee dos veces."),
          callout("Nota", "Después de calibrar, espere 10 minutos antes de interpretar las lecturas: el sensor necesita estabilizarse.", BLUE),
          H1("Materiales necesarios"),
          data_table([["Elemento", "Cantidad"], ["Sensor AG-200 con su antena", "1"], ["Batería de 12 V", "1"], ["Solución patrón de calibración", "1 frasco"], ["Pala pequeña o barreno", "1"]], [11, 6])]
    s += [PageBreak(), H1("4. Códigos de error"),
          data_table([["Código", "Significado", "Acción recomendada", "Gravedad"],
                      ["E-4471", "Sensor de humedad desconectado", "Revisar el conector de la sonda y reiniciar", chip("Alta", RED)],
                      ["E-5102", "Batería baja (menos de 3,2 V)", "Reemplazar la batería", chip("Media", ORANGE)],
                      ["E-6003", "Pérdida de señal LoRa", "Reubicar la antena o acercar la pasarela", chip("Media", ORANGE)],
                      ["E-7010", "Error de memoria interna", "Reiniciar y contactar a soporte", chip("Baja", GREEN)]], [2.2, 5.2, 7.0, 2.6]),
          H1("5. Mantenimiento preventivo")] + bullets(["Limpie la sonda con un paño húmedo en cada visita.", "Revise el estado de la batería cada trimestre.",
                                                         "Verifique que la antena no esté cubierta por vegetación.", "Registre cada calibración en la bitácora de la finca."])
    s += [H1("6. Preguntas frecuentes"),
          data_table([["Pregunta", "Respuesta"], ["¿Cuánto dura la batería?", "Varios meses, según la frecuencia de lectura configurada."],
                      ["¿Se puede instalar en invernadero?", "Sí, siempre que la antena tenga visibilidad hacia la pasarela."],
                      ["¿Qué hago si el indicador parpadea en rojo?", "Consulte la tabla de códigos de error de la sección 4."]], [7, 10]),
          H1("7. Soporte técnico"),
          callout("Contacto", "Escriba a soporte@agroandina.example o llame a la extensión 305, de lunes a viernes de 8 a. m. a 5 p. m.", GREEN)]
    build(path, s, "Manual técnico del sensor AG-200")


def contrato(path: Path):
    def clausula(n, titulo, texto):
        return [Paragraph(f"CLÁUSULA {n}. {titulo.upper()}", S["h2"]), P(texto)]
    s = title_band("CONTRATO No. 2026-014", "Prestación de servicios", "Instalación y mantenimiento de una red de sensores de riego")
    s += [Paragraph("Medellín, 25 de marzo de 2026", S["small"]), Spacer(1, 8),
          data_table([["Parte", "Datos"], ["<b>El prestador</b>", "Agroandina S.A.S., NIT 900.123.456-7, representada por Carlos Ruiz, gerente general."],
                      ["<b>El cliente</b>", "Fincas del Valle S.A., NIT 800.765.432-1, representada por Jorge Valencia, representante legal."]], [3.4, 13.6]),
          P("Las partes, obrando en la calidad indicada, han acordado celebrar el presente contrato, que se regirá por las siguientes cláusulas:")]
    s += clausula("PRIMERA", "Objeto", "El prestador instalará y mantendrá una red de sensores de riego en las fincas del cliente, así como la plataforma de monitoreo asociada.")
    s += clausula("SEGUNDA", "Duración", "El contrato dura 24 meses contados desde el 1 de abril de 2026 y podrá renovarse por periodos iguales si las partes lo acuerdan por escrito.")
    s += clausula("TERCERA", "Valor y forma de pago", "El cliente pagará un valor mensual de 4.200 dólares, dentro de los primeros cinco días de cada mes, mediante transferencia bancaria.")
    s += [PageBreak()]
    s += clausula("CUARTA", "Terminación anticipada", "Cualquiera de las partes podrá cancelar el servicio con un aviso previo de treinta días calendario. Si el cliente cancela antes de "
                  "finalizar el plazo, pagará una penalización equivalente al 10 % del valor restante del contrato.")
    s += [callout("Importante", "El aviso de cancelación debe enviarse por escrito al domicilio de la otra parte; el plazo se cuenta desde la fecha de recibo.", ORANGE)]
    s += clausula("QUINTA", "Confidencialidad", "Las partes guardarán reserva sobre la información técnica y comercial a la que accedan por causa de este contrato durante cinco años.")
    s += clausula("SEXTA", "Jurisdicción", "Cualquier controversia derivada de este contrato se resolverá ante los jueces de Medellín.")
    s += clausula("SÉPTIMA", "Notificaciones", "Las notificaciones se enviarán a los correos electrónicos y domicilios indicados por cada parte en el anexo de este contrato.")
    s += clausula("OCTAVA", "Obligaciones del prestador", "El prestador mantendrá la red en funcionamiento, atenderá los avisos de falla dentro de las 48 horas siguientes y entregará un informe mensual del estado de los sensores.")
    s += clausula("NOVENA", "Obligaciones del cliente", "El cliente facilitará el acceso a las fincas, mantendrá despejadas las zonas de instalación y designará una persona de contacto para coordinar las visitas técnicas.")
    s += [PageBreak(), H1("Firmas"), P("En constancia, las partes firman en dos ejemplares del mismo tenor, en Medellín, el 25 de marzo de 2026."), Spacer(1, 40)]
    sig = Table([["", ""], ["Carlos Ruiz", "Jorge Valencia"], ["Gerente general · Agroandina S.A.S.", "Representante legal · Fincas del Valle S.A."]], colWidths=[8.5 * cm, 8.5 * cm])
    sig.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.8, INK), ("LINEABOVE", (1, 1), (1, 1), 0.8, INK), ("FONTNAME", (0, 1), (-1, 1), BOLD), ("FONTNAME", (0, 2), (-1, 2), REG),
                             ("FONTSIZE", (0, 1), (-1, 2), 10.5), ("TEXTCOLOR", (0, 2), (-1, 2), GREY), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, 0), 30)]))
    s += [sig, Spacer(1, 36), H1("Anexo 1. Fincas cubiertas"),
          data_table([["Finca", "Municipio", "Hectáreas"], ["La Esperanza", "Rionegro", "42"], ["El Roble", "Marinilla", "35"], ["San José", "Guarne", "28"]], [7, 6, 4])]
    build(path, s, "Contrato de prestación de servicios")


def informe_ventas(path: Path):
    cover = {"tag": "INFORME ANUAL", "title": "Informe de ventas 2026", "subtitle": "Dirección comercial · Agroandina S.A.S.", "date": "Enero de 2027"}
    s = [Spacer(1, 10), Paragraph("Elaborado por la Dirección comercial. Versión 1.0.<br/>Documento de ejemplo con datos ficticios, con fines de demostración.", S["small"]),
         NextPageTemplate("body"), PageBreak()]
    s += [H1("1. Resumen ejecutivo"),
          P("Durante 2026 las ventas de Agroandina crecieron de forma sostenida frente a 2025, impulsadas por la línea de sensores de riego y por la apertura de "
            "nuevas fincas clientes. El detalle de cada trimestre se presenta únicamente en el gráfico de la sección 2."),
          kpis([("+18 %", "Crecimiento frente a 2025", GREEN), ("12", "Nuevas fincas clientes", BLUE), ("36 %", "Margen bruto", ORANGE)]),
          H2("Hallazgos clave")] + bullets(["La demanda se concentró en la segunda mitad del año, con la temporada de siembra.", "Los clientes que instalaron sensores aumentaron sus pedidos de controladores.",
                                           "El tiempo de instalación en campo limitó la capacidad de atender más fincas al mismo tiempo."])
    s += [Spacer(1, 8), callout("Contexto", "Las cifras están expresadas en millones de pesos colombianos y provienen del sistema contable de Agroandina.", BLUE),
          H2("Canales de venta"),
          data_table([["Canal", "Comentario"], ["Venta directa a fincas", "Canal principal; relación cercana con cada cliente."],
                      ["Distribuidores regionales", "Amplían la cobertura en zonas alejadas."], ["Plataforma en línea", "Reposición de controladores y accesorios."]], [5.5, 11.5]),
          H2("Perspectiva"),
          P("Para 2027 se espera mantener el ritmo de crecimiento, siempre que la capacidad de instalación acompañe la demanda.")]
    s += [PageBreak(), H1("2. Ventas por trimestre"),
          P("El siguiente gráfico muestra las ventas de cada trimestre de 2026. La barra resaltada en verde corresponde al trimestre de mayor facturación del año."),
          pic(ch.sales_bar(), 15.5, "Figura 1. Ventas 2026 por trimestre (millones de pesos)"),
          P("La comparación trimestre a trimestre permite planificar el inventario y la contratación del equipo técnico con anticipación suficiente."),
          H2("Factores que influyeron en el año")] + bullets(["La temporada de siembra concentró los pedidos de sensores y controladores.", "Las promociones para fincas nuevas aceleraron las primeras instalaciones.",
                                                              "La disponibilidad mensual de sensores del proveedor condicionó el ritmo de entrega.", "El clima seco impulsó la demanda de riego automatizado."]) + [
          Spacer(1, 6), callout("Recomendación", "Programar las instalaciones grandes con al menos dos meses de anticipación para no depender del inventario del proveedor.", GREEN)]
    s += [PageBreak(), H1("3. Ventas por línea de producto"), pic(ch.product_donut(), 14, "Figura 2. Participación por línea de producto"),
          data_table([["Línea", "Participación", "Comentario"], ["Sensores de riego", "48 %", "Línea líder; crece con cada finca nueva"],
                      ["Controladores", "31 %", "Se venden junto con los sensores"], ["Servicios de instalación", "21 %", "Dependen de la capacidad del equipo técnico"]], [5.2, 3.2, 8.6]),
          H1("4. Conclusiones y recomendaciones"),
          P("La directora comercial recomienda reforzar el inventario antes del trimestre más fuerte del año e invertir en capacitación del equipo técnico. "
            "El proveedor principal de sensores continúa siendo Andina SA, con sede en Bogotá, con entregas mensuales.")]
    build(path, s, "Informe de ventas 2026", cover)


def guia_instalacion(path: Path):
    s = title_band("GUÍA DE INGENIERÍA", "Instalación de la red de riego", "Agroandina S.A.S. · Departamento de ingeniería")
    s += [H2("1. Alcance"),
          P("Esta guía describe cómo instalar la red de sensores de riego AG-200 en una finca nueva, desde la preparación del terreno hasta la entrega "
            "al cliente. Está dirigida a los técnicos de campo y al jefe de ingeniería."),
          data_table([["Ficha rápida", ""], ["Tiempo estimado", "La instalación de cada sensor toma 45 minutos con un equipo de dos técnicos."],
                      ["Personal", "Dos técnicos de campo y un supervisor"], ["Dificultad", "Media"]], [4.5, 12.5]),
          callout("Seguridad", "Use casco, gafas y guantes de nitrilo durante toda la instalación y no trabaje con el sistema de riego en marcha.", RED),
          H2("1.1 Herramientas necesarias"),
          data_table([["Herramienta", "Uso"], ["Taladro con broca de 12 mm", "Perforar los soportes de la pasarela"], ["Llave de 17 mm", "Ajustar los anclajes"],
                      ["Receptor GPS", "Marcar los puntos de instalación"], ["Multímetro", "Verificar la batería y el cable"]], [7, 10])]
    s += [PageBreak(), H1("2. Preparación del terreno"),
          P("Antes de instalar, recorra la finca con el receptor GPS y marque los puntos de instalación cada 15 metros a lo largo de cada línea de riego. "
            "Evite zonas encharcadas y raíces grandes."),
          H2("2.1 Zanja del cable"),
          P("Abra una zanja de 30 cm de profundidad entre el punto de instalación y la pasarela. El cable debe quedar sin tensión."),
          pic(ch.trench_diagram(), 14.5, "Figura 1. Corte de la zanja del cable"),
          H2("2.2 Presión del sistema"),
          callout("Verificación", "Antes de conectar el primer sensor, compruebe que la presión de trabajo del sistema de riego sea de 2,5 bar.", ORANGE)]
    s += [PageBreak(), H1("3. Distribución por zonas"),
          P("La finca se divide en tres zonas según el tipo de cultivo. La cantidad de sensores asignada a cada zona se muestra en la figura 2; "
            "respete esa distribución para que la cobertura sea uniforme."),
          pic(ch.zones_map(), 15.5, "Figura 2. Sensores por zona de la finca"),
          data_table([["Zona", "Cultivo principal"], ["Zona A", "Café"], ["Zona B", "Aguacate"], ["Zona C", "Cítricos"]], [5, 12]),
          callout("Cambios", "Cualquier cambio en la distribución debe ser aprobado por el jefe de ingeniería.", BLUE)]
    s += [PageBreak(), H1("4. Puesta en marcha y verificación"),
          P("Al terminar de conectar un sensor, espere 10 minutos para la primera lectura. La lectura normal de humedad del suelo debe estar entre el 20 % y el 60 %. "
            "Si aparece un código de error, consulte el manual técnico del sensor."),
          H2("4.1 Lista de verificación"),
          data_table([["Paso", "Verificación", "Estado"], ["1", "El indicador parpadea en verde", "☐"], ["2", "La pasarela recibe la lectura", "☐"], ["3", "La humedad está en el rango normal", "☐"],
                      ["4", "La zanja quedó cubierta y señalizada", "☐"]], [2, 12, 3]),
          H2("4.2 Entrega al cliente"),
          P("Cuando todos los sensores reportan, el jefe de ingeniería, Luis Pardo, firma el acta de entrega junto con el representante de la finca. "
            "El cliente recibe una capacitación de una hora sobre el uso de la plataforma."),
          H2("4.3 Registro de la instalación")] + bullets(["Fotografía de cada sensor instalado, con el punto GPS.", "Lectura inicial de humedad de cada sensor.", "Observaciones del cliente sobre el estado de la finca."]) + [
          Spacer(1, 6), callout("Archivo", "Guarde el registro en la carpeta de la finca; el equipo de soporte lo usará ante cualquier reclamo.", BLUE)]
    build(path, s, "Guía de instalación de la red de riego")


def plan_estrategico(path: Path):
    cover = {"tag": "DOCUMENTO INTERNO", "title": "Plan estratégico 2027", "subtitle": "Hacia 500 sensores y 12 fincas · Agroandina S.A.S.", "date": "Aprobado en marzo de 2026"}
    s = [Paragraph("Contenido", S["h2"]),
         data_table([["Sección", "Página"], ["1. Diagnóstico", "2"], ["2. Objetivos", "3"], ["3. Presupuesto", "4"], ["4. Riesgos", "5"], ["5. Cronograma", "6"], ["6. Equipo y conclusiones", "7"]], [12, 3]),
         NextPageTemplate("body"), PageBreak()]
    s += [H1("1. Diagnóstico"),
          P("Este diagnóstico resume la situación de la empresa al cierre de 2026 y sirve de punto de partida para las decisiones de inversión del año siguiente."),
          kpis([("38", "Clientes activos al cierre de 2026", BLUE), ("92 %", "Tasa de retención de clientes", GREEN), ("12", "Fincas nuevas en 2026", ORANGE)]),
          H2("Principal debilidad"),
          P("El tiempo de instalación en campo es la principal debilidad identificada: limita cuántas fincas se pueden atender al mismo tiempo."),
          H2("Principal fortaleza"),
          P("La relación con el proveedor Andina SA permite obtener los sensores con entregas mensuales."),
          H2("Contexto de mercado"),
          P("La adopción de riego automatizado crece en la región y los clientes piden soluciones fáciles de instalar y de mantener. Esto favorece a "
            "las empresas capaces de instalar rápido y dar soporte cercano.")]
    s += [PageBreak(), H1("2. Objetivos para 2027"),
          kpis([("500", "sensores instalados en 12 fincas", GREEN), ("+25 %", "ventas frente a 2026", BLUE), ("30 min", "por sensor, desde los 45 minutos actuales", ORANGE)]),
          H2("Detalle de los objetivos")] + numbered(["Instalar 500 sensores en 12 fincas.", "Aumentar las ventas un 25 % frente a 2026.", "Reducir el tiempo de instalación de 45 a 30 minutos por sensor."])
    s += [Spacer(1, 8), P("Cada objetivo tiene un responsable asignado, descrito en la última sección de este documento."),
          H2("Responsables por objetivo"),
          data_table([["Objetivo", "Responsable"], ["Instalar los sensores en las fincas", "Luis Pardo"], ["Aumentar las ventas", "Carlos Ruiz"], ["Reducir el tiempo de instalación", "Luis Pardo"]], [11, 6])]
    s += [PageBreak(), H1("3. Presupuesto"),
          P("La inversión prevista para 2027 se reparte entre cuatro áreas. La distribución exacta aparece en la figura 1."),
          pic(ch.budget_bars(), 15.5, "Figura 1. Inversión 2027 por área"),
          H2("Criterios de asignación")] + bullets(["Prioridad a las iniciativas que reducen el tiempo de instalación.", "Inversión en capacitación para sostener el crecimiento del equipo técnico.",
                                                    "Reserva para imprevistos del proveedor y variaciones del tipo de cambio."]) + [
          data_table([["Aprobación", "Detalle"], ["Aprobado por", "Gerencia general"], ["Fecha de aprobación", "14 de marzo de 2026"], ["Moneda", "Dólares estadounidenses (USD)"]], [5, 12])]
    s += [PageBreak(), H1("4. Riesgos"),
          data_table([["Riesgo", "Probabilidad", "Impacto"],
                      ["Retraso del proveedor Andina SA", chip("Media", ORANGE), chip("Alto", RED)], ["Sequía prolongada", chip("Baja", GREEN), chip("Medio", ORANGE)],
                      ["Rotación del personal técnico", chip("Alta", RED), chip("Medio", ORANGE)], ["Variación del tipo de cambio", chip("Alta", RED), chip("Bajo", GREEN)]], [9, 4, 4]),
          callout("Seguimiento", "Los riesgos de probabilidad alta se revisan cada mes en el comité de gerencia.", ORANGE),
          H2("Plan de respuesta")] + bullets(["Rotación del personal técnico: capacitación cruzada para que cada zona tenga al menos dos técnicos preparados.",
                                              "Variación del tipo de cambio: acordar con el proveedor precios en dólares y revisar la cobertura cada trimestre."])
    s += [PageBreak(), H1("5. Cronograma"),
          P("Los hitos principales del año se resumen en la figura 2. El lanzamiento oficial está sujeto a que el piloto cumpla las metas de calidad."),
          pic(ch.gantt(), 16, "Figura 2. Hitos del proyecto 2027"),
          callout("Condición", "Si el piloto no cumple las metas de calidad, el lanzamiento oficial se reprograma con aviso a los clientes.", BLUE),
          H2("Dependencias")] + bullets(["Entrega mensual de sensores por parte de Andina SA.", "Contratación de los técnicos adicionales antes de empezar el piloto.",
                                         "Aprobación del presupuesto por la gerencia general."])
    s += [PageBreak(), H1("6. Equipo y conclusiones"),
          data_table([["Rol", "Persona"], ["Responsable general", "Carlos Ruiz"], ["Dirección del proyecto", "María González"], ["Ingeniería", "Luis Pardo"], ["Compras", "Ana Torres"]], [7, 10]),
          H2("Conclusiones"),
          P("El plan prioriza reducir el tiempo de instalación y asegurar el suministro de sensores. La próxima revisión del plan será el 15 de enero de 2027."),
          H2("Próximos pasos")] + numbered(["Confirmar con el proveedor el calendario de entregas.", "Abrir el proceso de selección de los técnicos adicionales.", "Preparar a las tres fincas del piloto."])
    build(path, s, "Plan estratégico 2027", cover)


def acta_escaneada(path: Path):
    """Acta firmada y 'escaneada': papel envejecido, ruido y leve inclinación. No tiene texto seleccionable."""
    import pymupdf

    def stamp_and_sign(c, doc):
        c.saveState()
        c.setStrokeColor(colors.HexColor("#B3261E")); c.setFillColor(colors.HexColor("#B3261E")); c.setLineWidth(2.2)
        c.translate(W - 5.2 * cm, 7.4 * cm); c.rotate(14)
        c.circle(0, 0, 1.9 * cm); c.circle(0, 0, 1.65 * cm)
        c.setFont(BOLD, 14); c.drawCentredString(0, 0.15 * cm, "APROBADO"); c.setFont(REG, 8.5); c.drawCentredString(0, -0.5 * cm, "AGROANDINA S.A.S.")
        c.restoreState()
        c.saveState(); c.setStrokeColor(colors.HexColor("#1B3A8C")); c.setLineWidth(1.4)
        for x, seed in ((2.6 * cm, 0.0), (9.4 * cm, 1.0), (15.8 * cm, 2.0)):
            p = c.beginPath(); p.moveTo(x, 4.15 * cm)
            p.curveTo(x + 0.8 * cm, 4.9 * cm + seed * 2, x + 1.1 * cm, 3.5 * cm, x + 1.9 * cm, 4.4 * cm)
            p.curveTo(x + 2.4 * cm, 4.9 * cm, x + 2.7 * cm, 3.7 * cm, x + 3.4 * cm, 4.3 * cm)
            c.drawPath(p, stroke=1, fill=0)
        c.restoreState()

    buf = io.BytesIO()
    tmp = BaseDocTemplate(buf, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    tmp.addPageTemplates([PageTemplate(id="a", frames=[Frame(2.2 * cm, 2 * cm, W - 4.4 * cm, H - 4 * cm)], onPage=stamp_and_sign)])
    story = [Paragraph('<font color="#12284C" size="20"><b>AGROANDINA S.A.S.</b></font><br/><font color="#5A6677" size="10">Tecnología para el campo · Bogotá y Medellín</font>', ParagraphStyle("l", fontName=REG, leading=24)),
             Spacer(1, 6), Table([[""]], colWidths=[W - 4.4 * cm], rowHeights=[3], style=[("BACKGROUND", (0, 0), (-1, -1), NAVY)]), Spacer(1, 12),
             Paragraph("ACTA DE REUNIÓN No. 07", ParagraphStyle("t", fontName=BOLD, fontSize=19, leading=24, textColor=INK, spaceAfter=10)),
             data_table([["Proyecto", "Colibri"], ["Fecha", "14 de marzo de 2026, 3:00 p. m."], ["Lugar", "Oficina de Bogotá"],
                         ["Asistentes", "Carlos Ruiz, María González, Luis Pardo y Ana Torres"]], [3.6, 13.2], zebra=False),
             Paragraph("DECISIONES", S["h2"])] + numbered([
                 "Se aprueba el presupuesto del proyecto Colibri por 85.000 dólares.", "El proveedor de sensores será Andina SA, con sede en Bogotá.",
                 "Se contratarán dos técnicos de campo adicionales.", "La fecha de entrega del proyecto es el 30 de junio de 2027."]) + [
             Spacer(1, 8), P("<b>Responsable del proyecto:</b> María González, directora de proyectos."), P("<b>Próxima reunión:</b> 11 de abril de 2026.")]
    tmp.build(story)

    page = pymupdf.open(stream=buf.getvalue())[0]
    img = PILImage.open(io.BytesIO(page.get_pixmap(dpi=150, alpha=False).tobytes("png"))).convert("RGB")
    rng = np.random.default_rng(7)
    arr = np.asarray(img, dtype=np.float32) * np.array([0.97, 0.955, 0.90])  # papel ligeramente amarillento
    yy, xx = np.mgrid[0:arr.shape[0], 0:arr.shape[1]]
    vignette = 1 - 0.10 * (((xx / arr.shape[1] - 0.5) ** 2 + (yy / arr.shape[0] - 0.5) ** 2) * 2)
    arr = arr * vignette[..., None] + rng.normal(0, 4.5, arr.shape)
    scan = PILImage.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).rotate(0.7, resample=PILImage.BICUBIC, fillcolor=(236, 231, 215)).filter(ImageFilter.GaussianBlur(0.5))
    jpg = io.BytesIO()
    scan.save(jpg, format="JPEG", quality=84)
    out = pymupdf.open()
    out.new_page(width=W, height=H).insert_image(pymupdf.Rect(0, 0, W, H), stream=jpg.getvalue())
    out.save(path)
