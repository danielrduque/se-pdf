"""Generador de la 'Enciclopedia del Sistema Solar y Exploración Espacial'
Genera un documento PDF de 35 páginas, ilustrado con fotografías espaciales reales,
tablas de parámetros astrofísicos y descripciones científicas exhaustivas.
Se almacena en base_conocimiento/atlas_sistema_solar_exploracion_espacial.pdf
"""
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
OUTPUT_PDF = KB_DIR / "atlas_sistema_solar_exploracion_espacial.pdf"

# Paleta espacial corporativa
COSMIC_BLUE = colors.HexColor("#0B132B")
NAVY_ACCENT = colors.HexColor("#1C2541")
CYAN_ACCENT = colors.HexColor("#3A86C8")
TEAL_STAR = colors.HexColor("#2C7A7B")
GOLD_ACCENT = colors.HexColor("#D4AF37")
DARK_TEXT = colors.HexColor("#1A202C")
LIGHT_CELL = colors.HexColor("#F0F4F8")
BORDER_COLOR = colors.HexColor("#CBD5E1")

# Imágenes verificadas de alta calidad (Unsplash / NASA)
IMAGE_POOL = [
    "https://images.unsplash.com/photo-1532693322450-2cb5c511067d?w=800", # sol
    "https://images.unsplash.com/photo-1522030299830-16b8d3d049fe?w=800", # luna
    "https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?w=800", # tierra / marte
    "https://images.unsplash.com/photo-1614728423169-3f65fd722b7e?w=800", # jupiter
    "https://images.unsplash.com/photo-1614732414444-096e5f1122d5?w=800", # saturno
    "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?w=800", # galaxia
    "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=800", # astronauta
    "https://images.unsplash.com/photo-1541185933-ef5d8ed016c2?w=800", # cohete
    "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=800", # via lactea
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800", # superficie marte / crater
    "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?w=800", # nebulosa
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800", # espacio profundo
    "https://images.unsplash.com/photo-1531366936337-7c912a4589a7?w=800", # aurora boreal
    "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=800", # observatorio
    "https://images.unsplash.com/photo-1447433589675-4aaa569f3e05?w=800", # cosmos
    "https://images.unsplash.com/photo-1509773896068-7fd415d91e2e?w=800", # cometa
    "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=800", # cielo estrellado
    "https://images.unsplash.com/photo-1446776877081-d282a0f896e2?w=800", # satelite
    "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?w=800", # eclipse
    "https://images.unsplash.com/photo-1579202673506-ca3ce28943ef?w=800", # rover / tecnologia
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800", # paisaje alienigena
    "https://images.unsplash.com/photo-1516849841032-87cbac4d88f7?w=800", # cohete despegue
]

# Definición estructurada de capítulos (Páginas 3 a 34 = 32 capítulos temáticos)
CHAPTERS = [
    {
        "num": 1,
        "title": "El Sol: Corazón Térmico y Motor del Sistema Solar",
        "category": "Astrofísica Estelar | Estrella Tipo Espectral G2V",
        "img_idx": 0,
        "table": [
            ("Tipo Espectral", "G2V (Enana Amarilla)", "Distancia media Tierra", "149.597.870 km (1 UA)"),
            ("Masa solar", "1,989 x 10^30 kg (99,86% del sist.)", "Temperatura Núcleo", "15.000.000 K (Fusión H->He)"),
            ("Diámetro ecuatorial", "1.392.700 km (109 veces la Tierra)", "Temperatura Corona", "1 a 3 millones K (viento solar)")
        ],
        "p1": "El Sol es la estrella central del sistema planetario y concentra el 99,86 % de toda la masa conocida en el sistema solar. En su núcleo opera un reactor de fusión nuclear donde cuatro protones de hidrógeno se fusionan para dar lugar a un núcleo de helio mediante la cadena protón-protón, liberando enormes cantidades de energía en forma de fotones gamma y neutrinos.",
        "p2": "La atmósfera solar está compuesta por la fotosfera, la cromosfera y la corona exterior. La interacción de los intensos campos magnéticos solares genera manchas solares, fulguraciones de alta energía y eyecciones de masa coronal (CME), las cuales desencadenan tormentas geomagnéticas al colisionar con la magnetosfera de los planetas rocosos."
    },
    {
        "num": 2,
        "title": "Mercurio: El Centinela de Hierro y Silicio",
        "category": "Planetas Terrestres | Mundo Interior",
        "img_idx": 1,
        "table": [
            ("Distancia al Sol", "57,9 millones km (0,387 UA)", "Periodo orbital", "87,97 días terrestres"),
            ("Radio ecuatorial", "2.439,7 km (0,383 Tierras)", "Régimen térmico", "-180 °C (noche) a +430 °C (día)"),
            ("Composición núcleo", "Hierro metálico (~70% masa)", "Misiones clave", "Mariner 10, MESSENGER, BepiColombo")
        ],
        "p1": "Mercurio es el planeta más pequeño del sistema solar y el más cercano al Sol. Carece prácticamente de atmósfera densa, albergando tan solo una tenue exosfera formada por átomos desprendidos por el viento solar. Debido a esta carencia, experimenta la fluctuación térmica superficial más violenta de todos los planetas.",
        "p2": "Su superficie está profusamente craterizada, guardando gran similitud visual con la Luna. Destaca la descomunal Cuenca Caloris, un cráter de impacto de 1.550 km de diámetro provocado por un asteroide hace miles de millones de años, cuyas ondas de choque deformaron la corteza en el antípoda exacto del planeta."
    },
    {
        "num": 3,
        "title": "Venus: El Velo Tóxico y el Invernadero Desbocado",
        "category": "Planetas Terrestres | Gemelo Inhóspito",
        "img_idx": 2,
        "table": [
            ("Distancia al Sol", "108,2 millones km (0,723 UA)", "Presión superficial", "92 atmósferas (como a 900 m bajo el mar)"),
            ("Atmósfera", "96,5% CO2, 3,5% N2, gotas H2SO4", "Temperatura media", "465 °C (constante día y noche)"),
            ("Rotación", "243 días terrestres (retrógrada)", "Misiones clave", "Venera 7/13, Magellan, Akatsuki, DAVINCI+")
        ],
        "p1": "Venus es el planeta más caliente del sistema solar pese a estar a mayor distancia del Sol que Mercurio. Su atmósfera superdensa de dióxido de carbono genera un efecto invernadero desbocado que eleva la temperatura superficial a niveles suficientes para fundir plomo, acompañada de densas nubes de ácido sulfúrico.",
        "p2": "Un aspecto notable de Venus es su rotación retrógrada: el planeta gira sobre su eje de este a oeste, muy lentamente, tardando más en completar un giro sobre sí mismo (243 días) que en orbitar al Sol (225 días). La misión soviética Venera 13 logró descender en 1982 y operar durante 127 minutos enviando las primeras imágenes a color."
    },
    {
        "num": 4,
        "title": "La Tierra: Dinámica de un Planeta Vivo",
        "category": "Planetas Terrestres | Biosfera Activa",
        "img_idx": 17,
        "table": [
            ("Distancia al Sol", "149,6 millones km (1,00 UA)", "Superficie hídrica", "70,8% océanos de agua líquida"),
            ("Radio ecuatorial", "6.378,1 km", "Atmósfera", "78,08% N2, 20,95% O2, 0,93% Ar"),
            ("Inclinación axial", "23,44° (genera estaciones)", "Campo magnético", "Geodinamo en núcleo externo de hierro")
        ],
        "p1": "La Tierra es el único planeta conocido que alberga vida orgánica compleja y agua líquida superficial de forma perenne. Su geodinamo interna, impulsada por la convección del hierro fundido en el núcleo externo, genera un escudo magnético dipolar que desvía la radiación cósmica y las partículas ionizadas del viento solar.",
        "p2": "La tectónica de placas recicla activamente la corteza terrestre, regulando los niveles de dióxido de carbono a escala geológica a través del ciclo silicato-carbonato. Esta homeostasis geoquímica ha mantenido una biosfera estable a lo largo de más de 3.800 millones de años de historia evolutiva continua."
    },
    {
        "num": 5,
        "title": "La Luna: Crónicas del Regolito y el Gran Impacto",
        "category": "Satélites Naturales | Satélite Terrestre",
        "img_idx": 1,
        "table": [
            ("Distancia a Tierra", "384.400 km (media)", "Periodo orbital/rotación", "27,3 días (acoplamiento de marea)"),
            ("Diámetro", "3.474 km (0,27 Tierras)", "Composición suelo", "Regolito basáltico y anortositas"),
            ("Gravedad superficial", "1,62 m/s² (1/6 de la terrestre)", "Misiones humanas", "Apolo 11 al 17 (1969-1972)")
        ],
        "p1": "La Luna se formó hace aproximadamente 4.510 millones de años, según la hipótesis del gran impacto, tras la colisión cataclísmica de un protoplaneta del tamaño de Marte (llamado Theia) contra la proto-Tierra. Los escombros expulsados al espacio se aglutinaron rápidamente formando nuestro único satélite natural.",
        "p2": "Al estar sincronizada por las fuerzas de marea gravitacionales, la Luna muestra siempre la misma cara a la Tierra. En los polos lunares, dentro de cráteres de sombra perpetua donde la luz solar jamás penetra, telescopios y sondas orbitales han detectado vastos depósitos de hielo de agua, recurso vital para la futura exploración humana."
    },
    {
        "num": 6,
        "title": "Marte: El Mundo Escarlata y su Geología Monumental",
        "category": "Planetas Terrestres | Planeta Exterior Rocoso",
        "img_idx": 9,
        "table": [
            ("Distancia al Sol", "227,9 millones km (1,524 UA)", "Duración del año", "687 días terrestres"),
            ("Diámetro ecuatorial", "6.779 km (0,53 Tierras)", "Gravedad", "3,72 m/s² (0,38 g)"),
            ("Presión atmosférica", "610 Pa (menos del 1% terrestre)", "Satélites", "Fobos y Deimos (asteroides capturados)")
        ],
        "p1": "Marte debe su característico color rojizo al polvo rico en óxido de hierro (III) que cubre la mayor parte de su árida superficie. Presenta algunos de los accidentes topográficos más extremos de todo el sistema solar, moldeados durante el periodo Noeico y Hespérico por intensos procesos de actividad volcánica e hidrológica.",
        "p2": "Destacan el Monte Olimpo (Olympus Mons), un colosal volcán en escudo que se eleva más de 21 kilómetros sobre el nivel de referencia marciano, y Valles Marineris, un sistema de cañones tectónicos que se extiende por más de 4.000 kilómetros a lo largo del ecuador, empequeñeciendo al Gran Cañón de Arizona."
    },
    {
        "num": 7,
        "title": "El Agua en Marte: Glaciares Ocultos y Mares Primigenios",
        "category": "Geología Planetaria | Hidrología Marciana",
        "img_idx": 2,
        "table": [
            ("Evidencia fósil", "Redes fluviales, deltas, abanicos aluviales", "Hielo actual", "Casquetes polares y permafrost"),
            ("Cráteres clave", "Gale, Jezero, Gusev, Holden", "Minerales hidratados", "Arcillas esmectitas, sulfatos jarosita"),
            ("Misiones científicas", "Mars Express (radar MARSIS), MRO, MAVEN", "Potencial biológico", "Búsqueda de fósiles microbianos")
        ],
        "p1": "Las observaciones realizadas por satélites orbitales y rovers de superficie han corroborado de forma concluyente que Marte albergó abundante agua líquida superficial hace más de 3.500 millones de años, con ríos caudalosos, extensos lagos de cráter e incluso un océano septentrional que cubría el tercio norte del planeta.",
        "p2": "La pérdida del campo magnético global provocó la erosión atmosférica gradual a manos del viento solar. Actualmente, el agua marciana subsiste en forma de hielo en los casquetes polares y como permafrost subsuperficial generalizado en latitudes medias, detectado por los radares de penetración terrestre de las misiones internacionales."
    },
    {
        "num": 8,
        "title": "El Cinturón Principal de Asteroides: Escombros Primordiales",
        "category": "Cuerpos Menores | Frontera Interior-Exterior",
        "img_idx": 9,
        "table": [
            ("Ubicación orbital", "Entre 2,2 y 3,2 UA del Sol", "Masa total", "~4% de la masa de la Luna"),
            ("Mayor objeto", "Ceres (planeta enano, 940 km)", "Segundo mayor", "Vesta (protoplaneta rocoso, 525 km)"),
            ("Tipos espectrales", "Tipo C (carbonáceos), S (silicatos), M (metálicos)", "Misiones de estudio", "Dawn (NASA), Hayabusa2, OSIRIS-REx")
        ],
        "p1": "Ubicado en la brecha entre las órbitas de Marte y Júpiter, el cinturón de asteroides alberga millones de fragmentos rocosos y metálicos remanentes de la nebulosa protosolar. La inmensa perturbación gravitatoria ejercida por Júpiter impidió que estos cuerpos protoplanetarios pudieran agregarse para formar un planeta unificado.",
        "p2": "Ceres, reclasificado en 2006 como planeta enano, compone por sí solo un tercio de la masa total del cinturón. La sonda Dawn descubrió en su cráter Occator brillantes depósitos de carbonato sódico depositados por surgencias hidrotermales criovolcánicas, demostrando que Ceres alberga o albergó un océano subsuperficial."
    },
    {
        "num": 9,
        "title": "Júpiter: El Coloso Joviano y su Dinámica Atmosférica",
        "category": "Gigantes Gaseosos | El Mayor Planeta",
        "img_idx": 3,
        "table": [
            ("Distancia al Sol", "778,5 millones km (5,20 UA)", "Masa joviana", "1,898 x 10^27 kg (318 Tierras)"),
            ("Volumen", "1.321 veces la Tierra", "Periodo rotacional", "9 h 55 m (la más rápida del sistema)"),
            ("Composición principal", "89% Hidrógeno molecular, 10% Helio", "Misiones clave", "Pioneer, Voyager, Galileo, Juno")
        ],
        "p1": "Júpiter posee una masa dos veces y media superior a la de todos los demás planetas del sistema solar combinados. Su rápida rotación aplana visiblemente sus polos y organiza su atmósfera superior en bandas zonales alternas de corrientes en chorro y vientos de hasta 500 km/h enriquecidos con cristales de hielo de amoníaco.",
        "p2": "El rasgo más emblemático de su atmósfera es la Gran Mancha Roja, un anticiclón gigantesco de más de 16.000 km de diámetro que ha persistido durante más de tres siglos consecutivos. En sus profundidades, las presiones descomunales convierten el hidrógeno molecular gaseoso en un exótico estado de hidrógeno metálico líquido."
    },
    {
        "num": 10,
        "title": "Ío y Europa: Fuego Volcánico y Océanos Abisales",
        "category": "Lunas Galileanas | Geodinámica Extrema",
        "img_idx": 13,
        "table": [
            ("Ío: Actividad", "Más de 400 volcanes de azufre activos", "Mecanismo térmico", "Calentamiento de marea por resonancia"),
            ("Europa: Superficie", "Corteza de hielo liso con lineae fracturadas", "Océano de Europa", "Agua salada líquida (100 km profundidad)"),
            ("Misiones en curso", "Juno, JUICE (ESA), Europa Clipper (NASA)", "Volumen agua Europa", "El doble de todos los océanos terrestres")
        ],
        "p1": "Las lunas galileanas interiores de Júpiter presentan los contrastes más fascinantes del sistema solar. Ío está sometido a un calentamiento por marea gravitacional colosal por la interacción combinada de Júpiter, Europa y Ganimedes, lo que convierte a su corteza en el territorio geológicamente más activo del cosmos, con plumas volcánicas de 300 km.",
        "p2": "Por contraste, Europa está recubierta por una prístina capa de hielo agrietada por fracturas tectónicas. Bajo esta corteza helada de entre 15 y 25 km de grosor yace un océano global de agua líquida en contacto directo con un lecho rocoso hidrotermal, configurándose como el candidato principal para albergar vida extraterrestre."
    },
    {
        "num": 11,
        "title": "Ganimedes y Calisto: Colosos Helados de Júpiter",
        "category": "Lunas Galileanas | Cuerpos Mayores",
        "img_idx": 14,
        "table": [
            ("Ganimedes: Diámetro", "5.268 km (mayor que Mercurio)", "Magnetosfera propia", "Única luna con campo magnético intrínseco"),
            ("Calisto: Diámetro", "4.821 km (tercera luna mayor)", "Superficie Calisto", "El suelo más antiguo y craterizado del sistema"),
            ("Composición global", "Silicatos rocosos y hielo hídrico", "Misión insignia", "JUICE (Jupiter Icy Moons Explorer)")
        ],
        "p1": "Ganimedes es la luna más grande de todo el sistema solar, superando en volumen al planeta Mercurio y al planeta enano Plutón. Cuenta con un núcleo metálico diferenciado de hierro fundido que genera su propio campo magnético dipolar integrado dentro de la inmensa magnetosfera del gigante Júpiter.",
        "p2": "Calisto, la más externa de las cuatro lunas galileanas, presenta una superficie saturada de impactos cósmicos que data de hace 4.000 millones de años, prácticamente inalterada por procesos tectónicos. Su estructura interna no está totalmente diferenciada, ofreciendo una ventana intacta a las condiciones de la nebulosa protoplanetaria."
    },
    {
        "num": 12,
        "title": "Saturno: La Joya Anillada y la Física Orbital",
        "category": "Gigantes Gaseosos | Sistema de Anillos",
        "img_idx": 4,
        "table": [
            ("Distancia al Sol", "1.433 millones km (9,58 UA)", "Radio ecuatorial", "58.232 km (9,1 Tierras)"),
            ("Densidad media", "0,687 g/cm³ (flotaría en agua)", "Extensión anillos", "Hasta 282.000 km desde el centro"),
            ("Espesor anillos", "Apenas 10 a 30 metros en promedio", "Misión histórica", "Cassini-Huygens (2004-2017)")
        ],
        "p1": "Saturno es el segundo planeta más masivo del sistema solar y el único cuya densidad media es menor que la del agua. Posee un sistema de anillos majestuoso visible incluso con pequeños telescopios terrestres, estructurado en divisiones principales como la División de Cassini, modeladas por las resonancias de sus lunas pastoras.",
        "p2": "Los anillos no son estructuras sólidas, sino billones de partículas individuales compuestas en un 99 % por hielo de agua puro con trazas de tolinas, cuyo tamaño oscila desde granos microscópicos de polvo hasta peñascos del tamaño de casas. En su polo norte, Saturno exhibe un enigmático vórtice atmosférico hexagonal estable."
    },
    {
        "num": 13,
        "title": "Titán: El Mundo Naranja de Metano y Química Orgánica",
        "category": "Lunas del Sistema Solar | Satélite Saturniano",
        "img_idx": 20,
        "table": [
            ("Diámetro", "5.150 km (segunda luna mayor)", "Presión superficial", "1,45 atmósferas terrestres"),
            ("Atmósfera", "95% Nitrógeno, 5% Metano (CH4)", "Temperatura superficial", "-179 °C"),
            ("Cuerpos líquidos", "Kraken Mare, Ligeia Mare (lagos de metano)", "Próxima misión", "Dragonfly (helicóptero octocóptero NASA)")
        ],
        "p1": "Titán es el único satélite del sistema solar con una atmósfera densa y el único mundo además de la Tierra con un ciclo hidrológico activo en su superficie, aunque compuesto de hidrocarburos líquidos en lugar de agua. Llueven gotas de metano y etano que alimentan redes fluviales y desembocan en mares árticos de hidrocarburos.",
        "p2": "La sonda europea Huygens aterrizó en su superficie helada en enero de 2005 transportada por Cassini, revelando llanuras de cantos rodados de hielo redondeados por corrientes fluviales líquidas. La atmósfera de Titán actúa como un reactor fotoquímico que sintetiza moléculas orgánicas complejas precursoras de la química prebiótica."
    },
    {
        "num": 14,
        "title": "Encélado: Criovulcanismo y Fuentes Hidrotermales",
        "category": "Lunas del Sistema Solar | Mundos Oceánicos",
        "img_idx": 11,
        "table": [
            ("Diámetro", "504 km (satélite menor de Saturno)", "Albedo superficial", "0,99 (el cuerpo más reflectante del sistema)"),
            ("Región activa", "Franjas de Tigre en polo sur", "Géiseres detectados", "Más de 100 plumas de vapor y hielo"),
            ("Composición plumas", "H2O, sal común, sílice, CH4, CO2, H2", "Alimentación anillo E", "Sus plumas forman el anillo E de Saturno")
        ],
        "p1": "A pesar de su reducido tamaño (apenas el tamaño del Reino Unido), Encélado es una de las joyas científicas más fascinantes de la astrobiología moderna. En su región polar meridional, la sonda Cassini descubrió fracturas tectónicas activas ('franjas de tigre') desde las cuales escapan colosales géiseres de vapor de agua y sales al vacío.",
        "p2": "Cassini atravesó directamente estas columnas de vapor identificando nanopartículas de sílice y gas hidrógeno libre, firma inequívoca de fuentes hidrotermales submarinas activas similares a las dorsales oceánicas terrestres, donde el agua líquida cálida y los minerales interactúan bajo el manto de hielo."
    },
    {
        "num": 15,
        "title": "Urano: El Gigante de Hielo Reclinado",
        "category": "Gigantes Helados | Planeta Exterior",
        "img_idx": 5,
        "table": [
            ("Distancia al Sol", "2.871 millones km (19,2 UA)", "Inclinación axial", "97,77° (órbita prácticamente de lado)"),
            ("Diámetro ecuatorial", "50.724 km (4,0 Tierras)", "Temperatura mínima", "-224 °C (atmósfera más fría registrada)"),
            ("Atmósfera", "83% H2, 15% He, 2,3% CH4", "Descubridor", "William Herschel (1781, primer planeta por telescopio)")
        ],
        "p1": "Urano fue el primer planeta descubierto en tiempos modernos mediante telescopio. Se clasifica junto a Neptuno como un gigante de hielo, diferenciándose de los gigantes gaseosos puros por poseer un manto supercrítico denso compuesto de hielos volátiles de agua, amoníaco y metano sobre un núcleo rocoso silicatado.",
        "p2": "Su característica más extraordinaria es su inclinación axial extrema de 98 grados, probablemente causada por una colisión colosal con un protoplaneta durante la infancia del sistema solar. Esto provoca que sus polos apunten directamente hacia el Sol durante solsticios que duran más de 42 años terrestres ininterrumpidos."
    },
    {
        "num": 16,
        "title": "Neptuno: El Reino de las Tormentas Supersónicas",
        "category": "Gigantes Helados | El Último Planeta Oficial",
        "img_idx": 11,
        "table": [
            ("Distancia al Sol", "4.498 millones km (30,07 UA)", "Periodo orbital", "164,8 años terrestres"),
            ("Velocidad del viento", "Hasta 2.100 km/h (los más veloces del sistema)", "Color azul intenso", "Absorción de luz roja por metano atmosférico"),
            ("Mayor satélite", "Tritón (órbita retrógrada, criovulcanismo)", "Descubrimiento", "Predicho por Le Verrier matemáticamente (1846)")
        ],
        "p1": "Neptuno es el planeta más distante del sistema solar. Fue el primer planeta descubierto gracias al poder del cálculo matemático antes de ser observado por telescopio, al deducir Urbain Le Verrier su posición exacta basándose en las anomalías orbitales que provocaba en la trayectoria calculada de Urano.",
        "p2": "A pesar de recibir solo el 0,1 % de la luz solar que llega a la Tierra, su atmósfera impulsa las tormentas más rápidas y violentas del sistema solar con vientos supersónicos de más de 2.000 km/h. Su luna mayor, Tritón, fue capturada del Cinturón de Kuiper y alberga géiseres activos de nitrógeno líquido en ebullición."
    },
    {
        "num": 17,
        "title": "El Cinturón de Kuiper y Plutón: La Frontera Helada",
        "category": "Objetos Transneptunianos | Planetas Enanos",
        "img_idx": 10,
        "table": [
            ("Ubicación", "De 30 a 55 UA del Sol", "Plutón: Radio", "1.188 km (0,18 Tierras)"),
            ("Planetas enanos clave", "Plutón, Eris, Haumea, Makemake", "Glaciar Sputnik Planitia", "Vasto mar congelado de nitrógeno y CO"),
            ("Misión pionera", "New Horizons (NASA, sobrevuelo julio 2015)", "Satélite mayor de Plutón", "Caronte (sistema binario gravitacional)")
        ],
        "p1": "El Cinturón de Kuiper es un inmenso disco circunestelar de cuerpos menores congelados que se extiende más allá de la órbita de Neptuno. Es el hogar de cientos de miles de planetesimales helados ricos en volátiles primitivos que no llegaron a colapsar en planetas mayores durante la formación del sistema solar.",
        "p2": "La histórica visita de la nave New Horizons en 2015 transformó nuestra comprensión de Plutón al revelar un mundo geológicamente activo. En lugar de una superficie muerta y craterizada, mostró la llanura Sputnik Planitia, un inmenso glaciar de nitrógeno en lenta convección con cordilleras de hielo hídrico de 3.500 m de altitud."
    },
    {
        "num": 18,
        "title": "La Nube de Oort y los Cometas: Mensajeros del Vórtice",
        "category": "Cosmología del Sistema Solar | Límite Gravitacional",
        "img_idx": 15,
        "table": [
            ("Distancia Nube Oort", "2.000 a 100.000 UA (cerca de 1 a 2 años luz)", "Morfología cometaria", "Núcleo, coma y colas de polvo/gas ionizado"),
            ("Masa estimada", "5 a 100 veces la masa terrestre", "Cometas históricos", "Halley, Hale-Bopp, NEOWISE, Churyumov"),
            ("Misiones cometa", "Giotto (1986), Deep Impact (2005), Rosetta (2014)", "Aportación a la Tierra", "Agua, volátiles y aminoácidos primitivos")
        ],
        "p1": "En los confines más extremos de la influencia gravitatoria del Sol, a casi un año luz de distancia, se postula la existencia de la Nube de Oort: una colosal envoltura esférica que alberga billones de cometas y cuerpos helados primitivos expulsados durante las migraciones de los gigantes gaseosos.",
        "p2": "Cuando perturbaciones gravitatorias de estrellas vecinas alteran sus órbitas, estos cuerpos se precipitan hacia el sistema interior. Al aproximarse al calor solar, los hielos se subliman formando una vistosa cabellera o coma y dos colas características: una de polvo curvada y otra de gas ionizado que apunta en dirección opuesta al Sol."
    },
    {
        "num": 19,
        "title": "Telescopio Espacial Hubble: Tres Décadas de Revolución Óptica",
        "category": "Instrumentación Espacial | Órbita Baja Terrestre",
        "img_idx": 8,
        "table": [
            ("Lanzamiento", "24 de abril de 1990 (Transbordador Discovery)", "Órbita", "Circular a 540 km de altitud"),
            ("Espejo primario", "2,4 metros de diámetro", "Espectro cubierto", "Ultravioleta, visible y cercano infrarrojo"),
            ("Misiones de servicio", "5 vuelos de astronautas (SM1 a SM4)", "Hitos clave", "Campo Ultra Profundo, aceleración cósmica")
        ],
        "p1": "El Telescopio Espacial Hubble (HST) es sinónimo del triunfo de la astrofísica observacional moderna. Situado por encima de la turbulencia y distorsión de la atmósfera terrestre, ha operado durante más de tres décadas brindando imágenes incomparables que redefinieron nuestra comprensión de la escala del universo observable.",
        "p2": "Entre sus contribuciones fundamentales destacan la determinación precisa de la constante de Hubble (la tasa de expansión del universo), el descubrimiento de la energía oscura junto con estudios de supernovas tipo Ia, y la histórica imagen del Campo Profundo del Hubble, revelando miles de galaxias primitivas en una porción minúscula de cielo."
    },
    {
        "num": 20,
        "title": "Telescopio Espacial James Webb: Desvelando el Cosmos Primitivo",
        "category": "Instrumentación Espacial | Punto de Lagrange L2",
        "img_idx": 14,
        "table": [
            ("Lanzamiento", "25 de diciembre de 2021 (Ariane 5)", "Ubicación", "Punto de Lagrange Sol-Tierra L2 (1,5 M km)"),
            ("Espejo primario", "6,5 metros (18 hexágonos de berilio bañado en oro)", "Protector solar", "5 capas de Kapton del tamaño de una pista de tenis"),
            ("Rango de detección", "Infrarrojo cercano y medio (0,6 a 28 micras)", "Temperatura operativa", "-233 °C (detector MIRI a -266 °C con helio)")
        ],
        "p1": "El Telescopio Espacial James Webb (JWST) es la obra cumbre de la ingeniería óptica espacial desarrollada conjuntamente por NASA, ESA y CSA. Diseñado para observar el universo en el infrarrojo, puede penetrar densas nubes de polvo interestelar y capturar la débil luz desplazada al rojo de las primeras estrellas y galaxias nacidas tras el Big Bang.",
        "p2": "Su monumental espejo segmentado de berilio recubierto de oro opera protegido del calor solar por una pantalla térmica de cinco capas. En sus primeros años de servicio ha detectado galaxias luminosas formadas apenas 300 millones de años después del Big Bang y ha analizado con detalle molecular las atmósferas de exoplanetas distantes."
    },
    {
        "num": 21,
        "title": "La Gran Travesía de las Misiones Voyager 1 y 2",
        "category": "Sondas Espaciales | Misiones Interestelares",
        "img_idx": 17,
        "table": [
            ("Lanzamiento", "Agosto y septiembre de 1977", "Distancia Voyager 1", "Más de 24.000 millones km (>160 UA)"),
            ("Fuente energética", "Generadores termoeléctricos de radioisótopos (RTG)", "Mensaje embarcado", "El Disco de Oro con sonidos e imágenes de la Tierra"),
            ("Hito histórico", "Primer artefacto humano en entrar al medio interestelar", "Duración operativa", "Cerca de medio siglo de telemetría ininterrumpida")
        ],
        "p1": "Aprovechando una alineación geométrica de los planetas exteriores que ocurre solo una vez cada 175 años, las sondas gemelas Voyager 1 y Voyager 2 despegaron en 1977 para completar el 'Grand Tour' del sistema solar exterior, empleando la asistencia gravitatoria de Júpiter para catapultarse hacia Saturno, Urano y Neptuno.",
        "p2": "En 2012, Voyager 1 cruzó la heliopausa, abandonando la burbuja magnética del Sol para adentrarse en el medio interestelar virgen. Ambas naves portan el célebre Disco de Oro comisariado por Carl Sagan, con grabaciones sonoras, música y diagramas explicativos como una botella lanzada al océano cósmico."
    },
    {
        "num": 22,
        "title": "El Programa Apolo: El Mayor Salto de la Humanidad",
        "category": "Vuelos Espaciales Tripulados | Carrera Lunar",
        "img_idx": 6,
        "table": [
            ("Periodo activo", "1961 a 1972 (primer alunizaje: 20 de julio de 1969)", "Vehículo lanzador", "Saturn V (Wernher von Braun, 110 m altura)"),
            ("Misiones lunares", "6 alunizajes exitosos (Apolo 11, 12, 14, 15, 16, 17)", "Astronautas en la Luna", "12 seres humanos caminaron sobre la superficie"),
            ("Carga recuperada", "382 kg de rocas lunares y muestras de regolito", "Módulo de descenso", "Módulo Lunar (LEM) con motor de empuje regulable")
        ],
        "p1": "El programa Apolo representó el cenit de la ingeniería aeroespacial del siglo XX. Conducido por la NASA bajo el impulso de llegar a la Luna antes del final de la década de 1960, movilizó a más de 400.000 ingenieros, científicos y técnicos para diseñar sistemas tecnológicos que sencillamente no existían, desde computadoras de guía integradas hasta trajes espaciales presurizados.",
        "p2": "El cohete Saturn V, que aún ostenta el récord de haber transportado con éxito misiones tripuladas sin fallos en vuelo, generaba más de 34 millones de newtons de empuje al despegue. El legado científico del programa persiste vivo: las muestras de roca lunar traídas a la Tierra siguen siendo analizadas en laboratorios modernos con tecnologías actuales."
    },
    {
        "num": 23,
        "title": "La Estación Espacial Internacional: Microgravedad y Cooperación",
        "category": "Laboratorios Orbitales | Vuelo Espacial Continuo",
        "img_idx": 17,
        "table": [
            ("Inicio de montaje", "1998 (módulo ruso Zaryá)", "Habitación continua", "Desde el 2 de noviembre de 2000"),
            ("Masa en órbita", "Aproximadamente 420 toneladas", "Envergadura solar", "109 metros (mayor que un campo de fútbol)"),
            ("Velocidad orbital", "27.600 km/h (da la vuelta a la Tierra en 92 minutos)", "Agencias socias", "NASA, Roscosmos, ESA, JAXA, CSA")
        ],
        "p1": "La Estación Espacial Internacional (ISS) es el objeto artificial más grande y complejo que orbita la Tierra. Fruto de la colaboración pacífica entre quince naciones tras el fin de la Guerra Fría, funciona como un laboratorio de investigación científica en régimen de microgravedad permanente donde tripulaciones internacionales conviven durante meses.",
        "p2": "En sus módulos presurizados se llevan a cabo miles de experimentos sobre cristalización de proteínas, física de fluidos cuánticos, cultivo hidropónico de vegetales y adaptación fisiológica del cuerpo humano a la ausencia prolongada de gravedad, allanando el camino para futuras expediciones hacia la Luna y Marte."
    },
    {
        "num": 24,
        "title": "Exploradores Robóticos en Marte: La Saga de los Rovers",
        "category": "Exploración Planetaria | Robótica Autónoma",
        "img_idx": 19,
        "table": [
            ("Sojourner (1997)", "10,6 kg (demostrador tecnológico)", "Spirit & Opportunity (2004)", "185 kg (Opportunity operó 14 años recorriendo 45 km)"),
            ("Curiosity (2012)", "899 kg (laboratorio químico SAM, motor RTG)", "Perseverance (2021)", "1.025 kg (perforación y retorno de muestras en Jezero)"),
            ("Dron Ingenuity", "Primer vuelo a motor en otro planeta (72 vuelos)", "Objetivo clave", "Paleoambientes y astrobiología marciana")
        ],
        "p1": "La exploración de Marte dio un salto cualitativo al pasar de sondas estáticas a plataformas móviles automatizadas. Desde el diminuto Sojourner hasta los complejos laboratorios rodantes Curiosity y Perseverance, la NASA ha desarrollado vehículos autónomos capaces de superar terrenos abruptos, escalar dunas y analizar la mineralogía in situ.",
        "p2": "Perseverance cuenta además con el helicóptero Ingenuity, que superó todas las expectativas al volar 72 veces en la enrarecida atmósfera marciana. Actualmente, Perseverance extrae y sella testigos de roca en tubos de titanio en el lecho del antiguo lago del Cráter Jezero, para ser recuperados por la futura misión conjunta Mars Sample Return."
    },
    {
        "num": 25,
        "title": "El Programa Artemis: La Nueva Era de Exploración Lunar",
        "category": "Programas Tripulados Actuales | Retorno Lunar",
        "img_idx": 7,
        "table": [
            ("Vehículo de lanzamiento", "Space Launch System (SLS Block 1)", "Cápsula tripulada", "Orion (módulo europeo de servicio ESM)"),
            ("Artemis I (2022)", "Vuelo no tripulado de 25 días a órbita retrógrada", "Artemis II (previsto)", "Vuelo orbital lunar tripulado con 4 astronautas"),
            ("Artemis III", "Alunizaje en el polo sur lunar", "Estación Gateway", "Puesto avanzado orbital en órbita halo NRHO")
        ],
        "p1": "El programa Artemis liderado por la NASA, con la participación fundamental de Europa, Japón y Canadá, tiene como objetivo establecer una presencia humana sostenible y permanente en la Luna, como escalón indispensable previo al envío de las primeras tripulaciones humanas al planeta Marte.",
        "p2": "A diferencia de las misiones Apolo, Artemis centra sus alunizajes en el polo sur de la Luna, donde existen cráteres de sombra eterna con depósitos masivos de hielo de agua. La futura estación espacial Gateway en órbita lunar servirá como puerto de acoplamiento, centro de comunicaciones y base logística para descensos repetidos."
    },
    {
        "num": 26,
        "title": "Ingeniería de Propulsión: De Cohetes Químicos a Motores Iónicos",
        "category": "Tecnología Aeroespacial | Física de Propulsión",
        "img_idx": 21,
        "table": [
            ("Propulsión química", "Queroseno/LOX, Hidrógeno/LOX, Metano/LOX", "Megacohete Starship", "Totalmente reutilizable, 150 t a LEO, motores Raptor"),
            ("Propulsión iónica", "Efecto Hall / Rejilla electrostática (gas xenón)", "Impulso específico (Isp)", "Cohetes químicos: 300-450 s | Motores iónicos: >3.000 s"),
            ("Propulsión nuclear", "Térmica nuclear (NTP) y fusión futura", "Ventaja propulsión iónica", "Aceleración continua con consumo mínimo de masa")
        ],
        "p1": "El mayor desafío del viaje espacial radica en la ecuación del cohete de Tsiolkovsky: para elevar una carga al espacio, la inmensa mayoría de la masa de despegue debe ser propelente. Motores criogénicos como el RS-25 o el Raptor de combustión por etapas completa han alcanzado los límites de eficiencia química teórica.",
        "p2": "Para trayectorias interplanetarias de largo alcance, la propulsión eléctrica e iónica cobra protagonismo. Al ionizar gases como el xenón y acelerar sus partículas mediante campos electromagnéticos a decenas de kilómetros por segundo, estos motores logran impulsos específicos monumentales, permitiendo a sondas como Dawn navegar durante años."
    },
    {
        "num": 27,
        "title": "La Búsqueda de Exoplanetas y Mundos Habitables",
        "category": "Astronomía Extrasolar | Nuevos Mundos",
        "img_idx": 18,
        "table": [
            ("Primer hallazgo", "51 Pegasi b (1995, Michel Mayor y Didier Queloz)", "Exoplanetas confirmados", "Más de 5.500 planetas fuera del sistema solar"),
            ("Método principal", "Tránsito fotométrico (Kepler, TESS)", "Método complementario", "Velocidad radial / Efecto Doppler espectroscópico"),
            ("Sistemas emblemáticos", "TRAPPIST-1 (7 planetas rocosos), Proxima b", "Zona de habitabilidad", "Distancia estelar que permite agua líquida superficial")
        ],
        "p1": "Hasta finales del siglo XX no se conocía con certeza si existían otros sistemas planetarios más allá del nuestro. El descubrimiento en 1995 del planeta 'Júpiter caliente' 51 Pegasi b desató una auténtica revolución en la astrofísica observacional que fue reconocida con el Premio Nobel de Física en 2019.",
        "p2": "Telescopios espaciales como Kepler y TESS han revelado que los sistemas planetarios son la norma y no la excepción en la Vía Láctea. El sistema TRAPPIST-1, a 40 años luz, alberga siete planetas de tamaño terrestre orbitando una enana roja ultrafría, con tres de ellos situados en la zona de habitabilidad donde el agua líquida es teóricamente viable."
    },
    {
        "num": 28,
        "title": "Agujeros Negros: Gravedad Extrema y Relatividad General",
        "category": "Astrofísica de Altas Energías | Singularidades",
        "img_idx": 10,
        "table": [
            ("Horizonte de sucesos", "Frontera donde la velocidad de escape iguala a c", "Singularidad central", "Punto de densidad y curvatura espacio-temporal infinita"),
            ("Sagitario A*", "Agujero negro supermasivo en el centro de la Vía Láctea (4,1 millones M☉)", "Colaboración EHT", "Primera imagen directa del horizonte de M87* (2019) y Sgr A* (2022)"),
            ("Ondas gravitacionales", "LIGO/Virgo detectan fusiones de agujeros negros", "Efecto Doppler relativista", "Dilatación temporal extrema y espaguetificación")
        ],
        "p1": "Predichos matemáticamente por las soluciones de Karl Schwarzschild a las ecuaciones de campo de Albert Einstein, los agujeros negros son las concentraciones de masa más compactas del cosmos. Su atracción gravitatoria es tan colosal que ninguna partícula ni radiación electromagnética puede escapar una vez cruza el horizonte de sucesos.",
        "p2": "En 2019, la colaboración global Event Horizon Telescope (EHT), conectando radiotelescopios de todo el planeta como un espejo virtual del tamaño de la Tierra, obtuvo la primera fotografía histórica de la silueta del agujero negro supermasivo de la galaxia M87, y posteriormente de Sagitario A* en el centro de nuestra propia galaxia."
    },
    {
        "num": 29,
        "title": "Evolución Estelar: De Nebulosas a Supernovas y Púlsares",
        "category": "Astrofísica Estelar | Ciclo Vital del Cosmos",
        "img_idx": 10,
        "table": [
            ("Cunas estelares", "Nebulosas moleculares gigantes ricas en H2 y polvo", "Equilibrio hidrostático", "Presión de radiación nuclear vs colapso gravitatorio"),
            ("Estrellas tipo solar", "Fase enana amarilla -> gigante roja -> nebulosa planetaria -> enana blanca", "Estrellas masivas (>8 M☉)", "Supernova de colapso de núcleo -> estrella de neutrones o agujero negro"),
            ("Estrellas de neutrones", "Púlsares y magnétares con campos magnéticos de billones de teslas", "Nucleosíntesis estelar", "Elementos pesados (carbono a uranio) forjados en estrellas")
        ],
        "p1": "Las estrellas no son eternas; nacen por el colapso gravitatorio de regiones densas dentro de nebulosas moleculares frías. Una vez iniciada la fusión termonuclear, la estrella permanece en la secuencia principal durante la mayor parte de su vida, equilibrando la gravedad hacia adentro con la presión de radiación hacia afuera.",
        "p2": "El destino final de una estrella depende estrictamente de su masa inicial. Estrellas masivas terminan su existencia en titánicas explosiones de supernova que esparcen por el espacio interestelar los elementos pesados (hierro, calcio, oro) forjados en su interior, sin los cuales no existirían planetas rocosos ni seres vivos."
    },
    {
        "num": 30,
        "title": "La Vía Láctea y las Galaxias del Grupo Local",
        "category": "Astronomía Extragaláctica | Estructura Cósmica",
        "img_idx": 8,
        "table": [
            ("Tipo de galaxia", "Espiral barrada (SBb)", "Diámetro del disco", "Aproximadamente 100.000 a 120.000 años luz"),
            ("Población estelar", "100.000 a 400.000 millones de estrellas", "Posición del Sol", "Brazo de Orión, a 26.000 años luz del núcleo galáctico"),
            ("Grupo Local", "Más de 50 galaxias (Andrómeda, Vía Láctea, Triángulo)", "Futura colisión", "Fusión con la Galaxia de Andrómeda en ~4.500 millones de años")
        ],
        "p1": "Nuestra galaxia natal, la Vía Láctea, es una majestuosa espiral barrada dotada de cuatro brazos espirales principales donde residen nebulosas de formación estelar activas. Todo el sistema rota en torno al núcleo galáctico, tardando el Sol cerca de 225 millones de años en completar un 'año galáctico'.",
        "p2": "La Vía Láctea forma parte del Grupo Local de galaxias, dominado por ella y por la descomunal Galaxia de Andrómeda (M31). Mediciones del telescopio Hubble confirman que ambas galaxias se aproximan a 110 kilómetros por segundo, y colisionarán dentro de cuatro mil millones de años formando una elíptica gigante ('Lactómeda')."
    },
    {
        "num": 31,
        "title": "Astrobiología y la Paradoja de Fermi",
        "category": "Fronteras de la Ciencia | Vida Extraterrestre",
        "img_idx": 18,
        "table": [
            ("Definición de vida", "Sistema químico autopoyético sujeto a evolución darwiniana", "Ecuación de Drake", "Probabilidad estadística de civilizaciones comunicativas"),
            ("Paradoja de Fermi", "¿Dónde está todo el mundo? Contradicción probabilidad vs evidencia", "Biofirmas atmosféricas", "Detección combinada de O2 + CH4 en desequilibrio termodinámico"),
            ("Extremófilos terrestres", "Bacterias radiorresistentes, termófilas de dorsales abisales", "Lunas objetivo", "Europa, Encélado, Titán")
        ],
        "p1": "La astrobiología es la ciencia interdisciplinar que estudia el origen, evolución, distribución y destino de la vida en el cosmos. El hallazgo de extremófilos en la Tierra—microorganismos que prosperan en fuentes ácidas hirvientes, en el hielo polar o bajo radiación letal—ha ensanchado enormemente el catálogo de entornos habitables potenciales.",
        "p2": "Si bien el universo es inmenso y antiguo, la paradoja planteada por Enrico Fermi cuestiona por qué no hemos hallado señales de civilizaciones tecnológicas extraterrestres. Las hipótesis van desde la existencia de un 'Gran Filtro' biológico hasta la necesidad de buscar biofirmas atmosféricas espectroscópicas con la nueva generación de telescopios."
    },
    {
        "num": 32,
        "title": "El Futuro de la Humanidad: Bases Lunares, Marte y Más Allá",
        "category": "Prospectiva Espacial | Civilización Interplanetaria",
        "img_idx": 6,
        "table": [
            ("Minería espacial", "Aprovechamiento de recursos in situ (ISRU) en asteroides y Luna", "Oxígeno en Marte", "Generación in situ probada por el instrumento MOXIE de Perseverance"),
            ("Energía en colonias", "Reactores nucleares compactos (Kilopower) y placas solares desplegables", "Escala de Kardashov", "Tipo I (planetaria), Tipo II (estelar), Tipo III (galáctica)"),
            ("Velas solares y láser", "Proyecto Breakthrough Starshot hacia Próxima Centauri (0,2 c)", "Terraformación teórica", "Calentamiento de polos marcianos y espesamiento atmosférico")
        ],
        "p1": "El siglo XXI marca la transición definitiva de la humanidad de especie uniplatanetaria a civilización espacial multiplanetaria. La utilización de recursos in situ (ISRU)—como extraer oxígeno y agua del regolito lunar y sintetizar combustible de metano en Marte usando dióxido de carbono atmosférico—reducirá drásticamente los costes logísticos.",
        "p2": "A más largo plazo, la minería de asteroides tipo M ricos en metales preciosos como platino y níquel, junto con el desarrollo de velas de fotones propulsadas por láseres ópticos que alcancen fracciones significativas de la velocidad de la luz, abrirá las puertas a las primeras misiones no tripuladas hacia los sistemas estelares más cercanos."
    }
]

class SpaceNumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular totales e incluir encabezados / pies con estilo técnico."""
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
        # Si es la portada (página 1), no dibujamos encabezado ni pie para conservar la elegancia
        if self._pageNumber == 1:
            return

        self.saveState()
        # Línea de encabezado
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.75)
        self.line(40, h - 38, w - 40, h - 38)
        
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(CYAN_ACCENT)
        self.drawString(40, h - 32, "ATLAS DEL SISTEMA SOLAR Y LA EXPLORACIÓN ESPACIAL")
        self.setFont("Helvetica", 8)
        self.setFillColor(NAVY_ACCENT)
        self.drawRightString(w - 40, h - 32, "Enciclopedia Multimodal de Astrofísica y Cosmología")

        # Línea de pie de página
        self.line(40, 40, w - 40, 40)
        self.setFont("Helvetica", 8)
        self.setFillColor(DARK_TEXT)
        self.drawString(40, 28, "Base de Conocimiento Científico | Publicación Monográfica")
        self.drawRightString(w - 40, 28, f"Página {self._pageNumber} de {total_pages}")
        self.restoreState()


def download_and_crop(url: str, target_width: float, target_height: float, prefix: str) -> str:
    cache_dir = ROOT / "data" / "space_images_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_path = cache_dir / f"raw_{prefix}.jpg"
    proc_path = cache_dir / f"proc_{prefix}_{int(target_width)}_{int(target_height)}.jpg"

    if proc_path.exists():
        return str(proc_path)

    if not raw_path.exists():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_path.write_bytes(resp.read())
        except Exception as e:
            print(f"Error descargando {url}: {e}")
            # Si falla la descarga, crear imagen sólida/gradiente de emergencia
            im = PILImage.new("RGB", (int(target_width * 2), int(target_height * 2)), (11, 19, 43))
            im.save(proc_path, "JPEG")
            return str(proc_path)

    with PILImage.open(raw_path) as im:
        im = im.convert("RGB")
        target_aspect = target_width / target_height
        curr_aspect = im.width / im.height
        
        if curr_aspect > target_aspect:
            new_w = int(im.height * target_aspect)
            left = (im.width - new_w) // 2
            im = im.crop((left, 0, left + new_w, im.height))
        else:
            new_h = int(im.width / target_aspect)
            top = (im.height - new_h) // 2
            im = im.crop((0, top, im.width, top + new_h))
            
        im.resize((int(target_width * 2), int(target_height * 2)), PILImage.Resampling.LANCZOS).save(
            proc_path, "JPEG", quality=90
        )
        return str(proc_path)


def generate_space_atlas():
    KB_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=52,
        bottomMargin=52
    )

    styles = getSampleStyleSheet()

    # Tipografía adaptada y refinada
    cover_title_style = ParagraphStyle(
        "CoverTitle", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=COSMIC_BLUE, spaceAfter=8
    )
    cover_sub_style = ParagraphStyle(
        "CoverSub", fontName="Helvetica", fontSize=13, leading=17, textColor=CYAN_ACCENT, spaceAfter=14
    )
    h1_style = ParagraphStyle(
        "PageTitle", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=COSMIC_BLUE, spaceAfter=2
    )
    sub_style = ParagraphStyle(
        "PageSub", fontName="Helvetica-Oblique", fontSize=9.5, leading=13, textColor=CYAN_ACCENT, spaceAfter=7
    )
    table_lbl = ParagraphStyle(
        "TableLbl", fontName="Helvetica-Bold", fontSize=8, leading=10.5, textColor=COSMIC_BLUE
    )
    table_val = ParagraphStyle(
        "TableVal", fontName="Helvetica", fontSize=8, leading=10.5, textColor=DARK_TEXT
    )
    p_style = ParagraphStyle(
        "BodyP", fontName="Helvetica", fontSize=9, leading=13, textColor=DARK_TEXT, spaceAfter=6, alignment=4
    )
    toc_title = ParagraphStyle(
        "TocTitle", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=COSMIC_BLUE, spaceAfter=8
    )
    toc_item = ParagraphStyle(
        "TocItem", fontName="Helvetica", fontSize=8, leading=11, textColor=DARK_TEXT
    )
    toc_bold = ParagraphStyle(
        "TocBold", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=COSMIC_BLUE
    )

    story = []

    # ==========================================
    # PÁGINA 1: PORTADA MONUMENTAL
    # ==========================================
    story.append(Paragraph("ENCICLOPEDIA DEL SISTEMA SOLAR", cover_title_style))
    story.append(Paragraph("Atlas visual y científico de los mundos conocidos, misiones espaciales y astrofísica moderna", cover_sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=CYAN_ACCENT, spaceBefore=0, spaceAfter=12))

    # Imagen principal de portada (Galaxia / Espacio profundo)
    cover_img_path = download_and_crop(IMAGE_POOL[5], 515, 290, "cover")
    story.append(RLImage(cover_img_path, width=515, height=290))
    story.append(Spacer(1, 14))

    # Ficha editorial y resumen institucional
    cover_box_data = [
        [
            Paragraph("<b>Coordinación Científica:</b>", table_lbl), Paragraph("División de Astrofísica y Exploración Planetaria", table_val),
            Paragraph("<b>Edición:</b>", table_lbl), Paragraph("Primera Edición Digital Multimodal", table_val)
        ],
        [
            Paragraph("<b>Áreas Temáticas:</b>", table_lbl), Paragraph("Mecánica celeste, geología comparada, espectroscopía, cosmoquímica", table_val),
            Paragraph("<b>Sistemas Tratados:</b>", table_lbl), Paragraph("Planetas interiores, exteriores, lunas oceánicas y espacio interestelar", table_val)
        ]
    ]
    t_cover = Table(cover_box_data, colWidths=[110, 155, 95, 155])
    t_cover.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_CELL),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_cover)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Esta monografía de 35 páginas compila el conocimiento contemporáneo consolidado a partir de observaciones "
        "telescópicas avanzadas (Hubble, James Webb) y telemetría directa obtenida por sondas y vehículos de superficie "
        "(Voyager, Cassini, Curiosity, Perseverance). Estructurada sistemáticamente desde la estrella central hasta los "
        "confines del cosmos profundo y la prospectiva de civilizaciones interplanetarias.",
        p_style
    ))
    story.append(PageBreak())

    # ==========================================
    # PÁGINA 2: ÍNDICE GENERAL Y PRÓLOGO
    # ==========================================
    story.append(Paragraph("ÍNDICE GENERAL Y PLAN DE LA OBRA", toc_title))
    story.append(Paragraph(
        "La presente enciclopedia se organiza en cuatro grandes secciones: los mundos interiores y rocosos, los gigantes "
        "gaseosos y sus mundos oceánicos, la tecnología de observación y vuelos tripulados, y la astrofísica cosmológica.",
        p_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=4, spaceAfter=8))

    # Tabla en dos columnas con los 32 capítulos y páginas
    toc_rows = []
    # 16 filas x 2 bloques (capítulo 1 a 16 a la izquierda, 17 a 32 a la derecha)
    for i in range(16):
        left_c = CHAPTERS[i]
        right_c = CHAPTERS[i + 16]
        left_page = i + 3
        right_page = i + 19
        toc_rows.append([
            Paragraph(f"<b>Cap. {left_c['num']}</b>", toc_bold),
            Paragraph(left_c['title'][:38] + "...", toc_item),
            Paragraph(f"Pág. {left_page}", toc_bold),
            Paragraph(f"<b>Cap. {right_c['num']}</b>", toc_bold),
            Paragraph(right_c['title'][:38] + "...", toc_item),
            Paragraph(f"Pág. {right_page}", toc_bold),
        ])

    t_toc = Table(toc_rows, colWidths=[40, 165, 45, 40, 180, 45])
    t_toc.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_toc)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>PRÓLOGO: LA ERA DORADA DE LA EXPLORACIÓN PLANETARIA</b>", table_lbl))
    story.append(Paragraph(
        "En poco más de seis décadas desde el lanzamiento del Sputnik en 1957, la humanidad ha extendido sus sentidos artificiales "
        "a través de miles de millones de kilómetros de vacío. Hemos posado ruedas en Marte, penetrado la atmósfera de Titán con la sonda Huygens, "
        "rozado la fotosfera solar con la sonda Parker y descifrado las atmósferas de planetas orbitando soles lejanos. Este atlas no es solo "
        "un catálogo de distancias y composiciones químicas, sino un testimonio de la curiosidad humana y de su constante empeño por "
        "comprender el universo y el lugar que ocupamos en él.",
        p_style
    ))
    story.append(PageBreak())

    # ==========================================
    # PÁGINAS 3 A 34: LOS 32 CAPÍTULOS TEMÁTICOS
    # ==========================================
    img_w = 515
    img_h = 165

    for idx, chap in enumerate(CHAPTERS):
        # Título y Subtítulo
        story.append(Paragraph(f"Capítulo {chap['num']}: {chap['title']}", h1_style))
        story.append(Paragraph(f"Clasificación Científica: <b>{chap['category']}</b>", sub_style))

        # Imagen
        url = IMAGE_POOL[chap['img_idx'] % len(IMAGE_POOL)]
        img_file = download_and_crop(url, img_w, img_h, f"ch_{chap['num']}")
        story.append(RLImage(img_file, width=img_w, height=img_h))
        story.append(Spacer(1, 6))

        # Tabla técnica de datos
        t_rows = []
        for row in chap['table']:
            t_rows.append([
                Paragraph(f"<b>{row[0]}:</b>", table_lbl),
                Paragraph(str(row[1]), table_val),
                Paragraph(f"<b>{row[2]}:</b>", table_lbl),
                Paragraph(str(row[3]), table_val),
            ])
        t_box = Table(t_rows, colWidths=[105, 155, 105, 150])
        t_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_CELL),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_box)
        story.append(Spacer(1, 6))

        # Párrafos de desarrollo
        story.append(Paragraph(chap['p1'], p_style))
        story.append(Paragraph(chap['p2'], p_style))

        story.append(PageBreak())

    # ==========================================
    # PÁGINA 35: CRONOLOGÍA HISTÓRICA Y GLOSARIO
    # ==========================================
    story.append(Paragraph("CRONOLOGÍA DE LA ERA ESPACIAL Y GLOSARIO CIENTÍFICO", toc_title))
    story.append(Paragraph(
        "Hitos históricos cardinales que marcaron el rumbo del conocimiento astronómico y la exploración in situ.",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=CYAN_ACCENT, spaceBefore=0, spaceAfter=8))

    # Cronología resumida en tabla
    chrono_data = [
        [Paragraph("<b>1609</b>", table_lbl), Paragraph("Galileo Galilei apunta por primera vez un telescopio óptico al cielo y descubre las lunas de Júpiter y las fases de Venus.", table_val)],
        [Paragraph("<b>1957</b>", table_lbl), Paragraph("Lanzamiento del Sputnik 1 (URSS): inicio oficial de la era espacial y primer satélite artificial en órbita terrestre.", table_val)],
        [Paragraph("<b>1969</b>", table_lbl), Paragraph("Misión Apolo 11 (NASA): Neil Armstrong y Buzz Aldrin realizan el primer alunizaje humano en el Mar de la Tranquilidad.", table_val)],
        [Paragraph("<b>1977</b>", table_lbl), Paragraph("Lanzamiento de las sondas Voyager 1 y 2 para explorar los cuatro gigantes gaseosos y viajar hacia el medio interestelar.", table_val)],
        [Paragraph("<b>1990</b>", table_lbl), Paragraph("Puesta en órbita del Telescopio Espacial Hubble, inaugurando una revolución de treinta años en astronomía observacional.", table_val)],
        [Paragraph("<b>2012</b>", table_lbl), Paragraph("Aterrizaje del rover Curiosity en Marte mediante grúa cohete (sky-crane) y entrada de Voyager 1 al espacio interestelar.", table_val)],
        [Paragraph("<b>2015</b>", table_lbl), Paragraph("La sonda New Horizons sobrevuela Plutón; primera detección directa de ondas gravitacionales por la colaboración LIGO.", table_val)],
        [Paragraph("<b>2021</b>", table_lbl), Paragraph("Lanzamiento del Telescopio Espacial James Webb (JWST) al punto de Lagrange L2 y primer vuelo del helicóptero Ingenuity en Marte.", table_val)],
    ]
    t_chrono = Table(chrono_data, colWidths=[45, 470])
    t_chrono.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_CELL),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_chrono)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>GLOSARIO DE TÉRMINOS ASTRONÓMICOS FUNDAMENTALES</b>", table_lbl))
    
    glossary_data = [
        [
            Paragraph("<b>Unidad Astronómica (UA):</b> Distancia media entre el centro de la Tierra y el centro del Sol, fijada en exactamente 149.597.870.700 metros.", table_val),
            Paragraph("<b>Albedo:</b> Fracción porcentual de radiación electromagnética que una superficie planetaria o lunar refleja respecto a la que recibe.", table_val)
        ],
        [
            Paragraph("<b>Año Luz:</b> Distancia que recorre un fotón en el vacío a lo largo de un año juliano (~9,46 billones de kilómetros).", table_val),
            Paragraph("<b>Heliopausa:</b> Límite exterior de la heliosfera donde el viento solar se frena por la presión opuesta del medio interestelar.", table_val)
        ],
        [
            Paragraph("<b>Criovulcanismo:</b> Erupción de sustancias volátiles congeladas (agua, metano o amoníaco) en mundos helados en lugar de roca fundida.", table_val),
            Paragraph("<b>Punto de Lagrange:</b> Posiciones gravitatoriamente estables donde las fuerzas de dos cuerpos masivos se cancelan para un tercer objeto menor.", table_val)
        ]
    ]
    t_gloss = Table(glossary_data, colWidths=[255, 260])
    t_gloss.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
    ]))
    story.append(t_gloss)

    # Construir PDF
    doc.build(story, canvasmaker=SpaceNumberedCanvas)
    print(f"Atlas espacial generado exitosamente en: {OUTPUT_PDF}")


if __name__ == "__main__":
    generate_space_atlas()
