"""Script para generar 'guia_visual_animales.pdf' con imágenes reales de alta calidad y fichas descriptivas.
Se guarda directamente en 'base_conocimiento/'.
"""
import io
import os
import sys
import urllib.request
from pathlib import Path
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "base_conocimiento"
OUTPUT_PDF = KB_DIR / "guia_visual_animales.pdf"

# Paleta de colores elegante
PRIMARY = colors.HexColor("#1A365D")    # Azul marino oscuro
SECONDARY = colors.HexColor("#2B6CB0")  # Azul medio
ACCENT = colors.HexColor("#2C7A7B")     # Verde azulado / teal
DARK = colors.HexColor("#2D3748")       # Texto oscuro suave
LIGHT_BG = colors.HexColor("#EDF2F7")   # Fondo gris muy claro
BORDER = colors.HexColor("#CBD5E0")     # Borde suave
GOLD = colors.HexColor("#D69E2E")       # Acento dorado

ANIMALS = [
    {
        "name": "León Africano",
        "scientific": "Panthera leo",
        "class": "Mamífero | Carnívoro | Felidae",
        "habitat": "Sabanas, estepas y pastizales del África subsahariana",
        "diet": "Carnívoro (ñus, cebras, búfalos, facóqueros)",
        "status": "Vulnerable (Lista Roja UICN)",
        "weight_size": "150 - 250 kg | Longitud: 1.8 - 2.5 m",
        "url": "https://images.unsplash.com/photo-1546182990-dffeafbe841d?w=800",
        "description": (
            "El león africano es uno de los felinos más imponentes y el único que presenta un marcado "
            "dimorfismo sexual y una estructura social compleja en manadas. Los machos destacan por su densa "
            "melena, cuyo color oscurece con la edad y la salud. Las hembras colaboran de forma sincronizada "
            "en las cacerías nocturnas o crepusculares, utilizando estrategias de emboscada coordinada. "
            "Su rugido puede escucharse a más de 8 kilómetros de distancia, sirviendo como advertencia "
            "territorial ante manadas rivales y leones nómadas."
        )
    },
    {
        "name": "Elefante Africano de Sabana",
        "scientific": "Loxodonta africana",
        "class": "Mamífero | Proboscidea | Elephantidae",
        "habitat": "Sabanas, matorrales y bosques abiertos de África central y meridional",
        "diet": "Herbívoro estricto (hierbas, cortezas, hojas, frutos, raíces)",
        "status": "En Peligro de Extinción (UICN)",
        "weight_size": "4.000 - 6.500 kg | Altura en cruz: 3 - 3.5 m",
        "url": "https://images.unsplash.com/photo-1557050543-4d5f4e07ef46?w=800",
        "description": (
            "El elefante africano es el animal terrestre más pesado y grande que existe sobre la Tierra. "
            "Su rasgo más característico es la trompa, una asombrosa estructura muscular sin huesos compuesta "
            "por decenas de miles de músculos individuales que le otorga un olfato agudo, la capacidad de recolectar "
            "alimento a alturas elevadas y manipular objetos diminutos. Sus grandes orejas actúan como radiadores "
            "térmicos, permitiendo enfriar la sangre en climas cálidos. Viven en sociedades matriarcales dirigidas "
            "por la hembra de mayor edad y experiencia."
        )
    },
    {
        "name": "Tigre de Bengala",
        "scientific": "Panthera tigris tigris",
        "class": "Mamífero | Carnívoro | Felidae",
        "habitat": "Selvas tropicales, bosques húmedos caducifolios y manglares de la India y Nepal",
        "diet": "Carnívoro (ciervos chital, sambares, jabalíes, gaures)",
        "status": "En Peligro de Extinción (UICN)",
        "weight_size": "180 - 260 kg | Longitud: 2.7 - 3.1 m",
        "url": "https://images.unsplash.com/photo-1534188753412-3e26d0d618d6?w=800",
        "description": (
            "El tigre de Bengala es el mayor de los félidos salvajes y un depredador alfa supremo. Cada individuo "
            "presenta un patrón único e irrepetible de rayas oscuras sobre pelaje rojizo que le brinda un camuflaje "
            "perfecto entre las sombras de la vegetación alta. A diferencia de muchos otros felinos, los tigres son "
            "excelentes nadadores y disfrutan sumergiéndose en ríos y lagunas para refrescarse y cazar. Son animales "
            "marcadamente solitarios y patrullan extensos territorios que marcan con orina y rasguños en los árboles."
        )
    },
    {
        "name": "Oso Panda Gigante",
        "scientific": "Ailuropoda melanoleuca",
        "class": "Mamífero | Carnívoro (adaptado a herbívoro) | Ursidae",
        "habitat": "Bosques montañosos templados y densos cañaverales de bambú en Sichuan y Shaanxi (China)",
        "diet": "Herbívoro especializado (99% bambú fresco, brotes y tallos)",
        "status": "Vulnerable (UICN)",
        "weight_size": "80 - 130 kg | Longitud: 1.5 - 1.8 m",
        "url": "https://images.unsplash.com/photo-1564349683136-77e08dba1ef7?w=800",
        "description": (
            "El panda gigante es el icono universal de la protección de la fauna salvaje. Aunque anatómicamente "
            "pertenece al orden de los carnívoros, su dieta se basa casi exclusivamente en el consumo de bambú, "
            "lo que le exige alimentarse entre 10 y 14 horas diarias consumiendo hasta 15 kg de material vegetal. "
            "Posee una modificación ósea única en la muñeca llamada 'falso pulgar', que le permite sujetar y deshojar "
            "las cañas con notable destreza. Su carácter pacífico y su reproducción pausada han sido objeto de intensos "
            "programas mundiales de conservación."
        )
    },
    {
        "name": "Jirafa",
        "scientific": "Giraffa camelopardalis",
        "class": "Mamífero | Artiodáctilo | Giraffidae",
        "habitat": "Sabanas abiertas con acacias, matorrales y bosques secos de África",
        "diet": "Herbívoro ramoneador (hojas y brotes tiernos de acacias y mimosas)",
        "status": "Vulnerable (UICN)",
        "weight_size": "800 - 1.400 kg | Altura: 4.5 - 5.8 m",
        "url": "https://images.unsplash.com/photo-1547721064-da6cfb341d50?w=800",
        "description": (
            "La jirafa es el ser vivo terrestre más alto del planeta. A pesar de la impresionante longitud de su "
            "cuello, este posee exactamente siete vértebras cervicales, al igual que los humanos, aunque muy alargadas. "
            "Para bombear sangre hasta la cabeza a semejante altura, su corazón pesa más de 11 kg y genera una presión "
            "arterial casi el doble de la humana. Su lengua prensil de color azul oscuro alcanza los 45 centímetros "
            "y está dotada de una capa protectora mucosa que le permite arrancar hojas entre las afiladas espinas de acacia."
        )
    },
    {
        "name": "Delfín Mular o Nariz de Botella",
        "scientific": "Tursiops truncatus",
        "class": "Mamífero | Cetáceo odontoceto | Delphinidae",
        "habitat": "Aguas templadas, tropicales y costeras de todos los océanos del mundo",
        "diet": "Carnívoro (peces pelágicos, calamares, sepias y crustáceos)",
        "status": "Preocupación Menor (UICN)",
        "weight_size": "200 - 450 kg | Longitud: 2.4 - 3.8 m",
        "url": "https://images.unsplash.com/photo-1570481662006-a3a1374699e8?w=800",
        "description": (
            "El delfín mular es célebre por su extraordinaria inteligencia, cognición avanzada y compleja sociabilidad. "
            "Utiliza la ecolocalización emitiendo clics de alta frecuencia que rebotan en los objetos submarinos, creando "
            "un mapa acústico tridimensional de su entorno incluso en la más absoluta oscuridad. Cada individuo posee un "
            "'silbido firma' propio que actúa como un nombre personal para comunicarse con otros miembros del grupo. "
            "Muestran cooperación coordinada durante la caza y notables conductas de juego y empatía."
        )
    },
    {
        "name": "Oso Polar",
        "scientific": "Ursus maritimus",
        "class": "Mamífero | Carnívoro | Ursidae",
        "habitat": "Banquisa y plataformas de hielo marino del Círculo Polar Ártico",
        "diet": "Hipercarnívoro marino (focas oceladas y barbudas, morsas)",
        "status": "Vulnerable (UICN)",
        "weight_size": "350 - 650 kg | Longitud: 2.2 - 2.8 m",
        "url": "https://images.unsplash.com/photo-1589656966895-2f33e7653819?w=800",
        "description": (
            "El oso polar es el mayor carnívoro terrestre del planeta y una especie adaptada de forma extrema al frío polar. "
            "Bajo su pelaje blanco translúcido, que atrapa la radiación y actúa como aislante, posee una piel completamente negra "
            "que absorbe la máxima cantidad posible de calor. Su gruesa capa de grasa subcutánea de más de 10 cm le permite nadar "
            "durante días seguidos en aguas congeladas sin hipotermia. Depende críticamente del hielo marino como plataforma para "
            "acechar a las focas en sus respiraderos."
        )
    },
    {
        "name": "Pingüino Emperador",
        "scientific": "Aptenodytes forsteri",
        "class": "Aves | Esfenisciforme | Spheniscidae",
        "habitat": "Plataformas de hielo costeras y aguas oceánicas de la Antártida",
        "diet": "Piscívoro y carnívoro marino (peces antárticos, krill, calamares)",
        "status": "Casi Amenazado (UICN)",
        "weight_size": "25 - 40 kg | Altura: 1.1 - 1.25 m",
        "url": "https://images.unsplash.com/photo-1598439210625-5067c578f3f6?w=800",
        "description": (
            "El pingüino emperador es la especie de pingüino de mayor tamaño y el rey indiscutible de la supervivencia "
            "en el clima antártico. Cría durante el riguroso invierno polar, desafiando temperaturas de hasta -50 °C y vientos "
            "huracanados. El macho asume en solitario la incubación del único huevo durante más de 60 días en su bolsa de "
            "cría sobre las patas mientras la hembra viaja kilómetros hasta el mar para alimentarse. Para resistir las ventiscas, "
            "forman enormes compactaciones sociales ('huddles') que rotan continuamente para compartir el calor corporal."
        )
    }
]

class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular e imprimir 'Página X de Y' y encabezado corporativo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        w, h = A4
        # Decoración superior (en todas las páginas excepto la portada si la hubiera)
        self.saveState()
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.75)
        self.line(40, h - 40, w - 40, h - 40)
        
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(SECONDARY)
        self.drawString(40, h - 34, "GUÍA VISUAL DE FAUNA SILVESTRE")
        self.setFont("Helvetica", 8)
        self.setFillColor(DARK)
        self.drawRightString(w - 40, h - 34, "Base de Conocimiento Multimodal")

        # Decoración inferior (pie de página)
        self.line(40, 42, w - 40, 42)
        self.setFont("Helvetica", 8)
        self.setFillColor(DARK)
        self.drawString(40, 30, "Documento de Referencia Científica y Divulgación Biológica")
        self.drawRightString(w - 40, 30, f"Página {self._pageNumber} de {total_pages}")
        self.restoreState()


def download_and_prepare_image(url: str, target_width_pt: float, target_height_pt: float) -> str:
    """Descarga la imagen, la recorta/ajusta a la proporción deseada y la guarda en caché temporal."""
    cache_dir = ROOT / "data" / "temp_images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("?")[0].split("/")[-1] + ".jpg"
    cache_path = cache_dir / filename
    
    if not cache_path.exists():
        print(f"Descargando {filename}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            cache_path.write_bytes(content)

    # Procesar con Pillow para garantizar ratio perfecto y calidad optimizada
    with PILImage.open(cache_path) as im:
        im = im.convert("RGB")
        target_aspect = target_width_pt / target_height_pt
        curr_aspect = im.width / im.height
        
        if curr_aspect > target_aspect:
            # Demasiado ancha: recortar lados
            new_w = int(im.height * target_aspect)
            left = (im.width - new_w) // 2
            im = im.crop((left, 0, left + new_w, im.height))
        else:
            # Demasiado alta: recortar arriba/abajo
            new_h = int(im.width / target_aspect)
            top = (im.height - new_h) // 2
            im = im.crop((0, top, im.width, top + new_h))
            
        processed_path = cache_dir / f"proc_{filename}"
        im.resize((int(target_width_pt * 2), int(target_height_pt * 2)), PILImage.Resampling.LANCZOS).save(
            processed_path, "JPEG", quality=92
        )
        return str(processed_path)


def generate_pdf():
    KB_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55
    )

    styles = getSampleStyleSheet()
    
    # Estilos tipográficos
    title_style = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=PRIMARY,
        spaceAfter=6,
        alignment=0
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=ACCENT,
        spaceAfter=14,
        alignment=0
    )
    intro_style = ParagraphStyle(
        "Intro",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=DARK,
        spaceAfter=18,
        alignment=4 # Justificado
    )
    animal_title = ParagraphStyle(
        "AnimalTitle",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=PRIMARY,
        spaceAfter=2
    )
    scientific_style = ParagraphStyle(
        "ScientificName",
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=14,
        textColor=SECONDARY,
        spaceAfter=8
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=PRIMARY
    )
    meta_val = ParagraphStyle(
        "MetaVal",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=DARK
    )
    body_style = ParagraphStyle(
        "AnimalBody",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=DARK,
        spaceBefore=6,
        spaceAfter=6,
        alignment=4 # Justificado
    )

    story = []

    # Portada / Encabezado general
    story.append(Paragraph("ENCICLOPEDIA VISUAL: FAUNA Y BIODIVERSIDAD", title_style))
    story.append(Paragraph("Catálogo ilustrado de especies emblemáticas del reino animal y sus ecosistemas", subtitle_style))
    story.append(Paragraph(
        "Esta guía recopila fichas biológicas completas con fotografías de alta resolución de ocho especies "
        "icónicas de la fauna mundial. Cada ficha incluye su taxonomía, hábitat natural, patrones de comportamiento, "
        "estrategias de caza o alimentación y su actual estado de conservación según la UICN. Diseñado para consulta "
        "rápida y análisis multimodal de texto e imágenes.",
        intro_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=SECONDARY, spaceBefore=0, spaceAfter=14))

    img_w_pt = 515  # ancho completo de la página disponible
    img_h_pt = 220  # altura panorámica proporcional

    # Añadimos los animales: 1 por página para que tenga diseño de catálogo de museo / enciclopedia
    for i, a in enumerate(ANIMALS):
        if i > 0 or len(story) > 5:
            story.append(PageBreak())

        # Descargar y preparar imagen
        img_path = download_and_prepare_image(a["url"], img_w_pt, img_h_pt)
        
        # Título y Nombre Científico
        story.append(Paragraph(f"{i + 1}. {a['name']}", animal_title))
        story.append(Paragraph(f"Nombre científico: <b>{a['scientific']}</b>", scientific_style))

        # Imagen
        story.append(RLImage(img_path, width=img_w_pt, height=img_h_pt))
        story.append(Spacer(1, 8))

        # Tabla de Ficha Técnica
        table_data = [
            [
                Paragraph("<b>Taxonomía:</b>", meta_label), Paragraph(a["class"], meta_val),
                Paragraph("<b>Estado UICN:</b>", meta_label), Paragraph(f"<b>{a['status']}</b>", meta_val)
            ],
            [
                Paragraph("<b>Hábitat:</b>", meta_label), Paragraph(a["habitat"], meta_val),
                Paragraph("<b>Dimensiones:</b>", meta_label), Paragraph(a["weight_size"], meta_val)
            ],
            [
                Paragraph("<b>Alimentación:</b>", meta_label), Paragraph(a["diet"], meta_val),
                Paragraph("<b>Distribución:</b>", meta_label), Paragraph("Global / Específica según región", meta_val)
            ]
        ]

        t = Table(table_data, colWidths=[75, 185, 75, 180])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        # Texto descriptivo
        story.append(Paragraph("<b>Descripción biológica y comportamiento:</b>", meta_label))
        story.append(Paragraph(a["description"], body_style))

    # Construir PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado con éxito en: {OUTPUT_PDF}")


if __name__ == "__main__":
    generate_pdf()
