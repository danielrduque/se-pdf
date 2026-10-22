"""Genera una base de conocimiento de ejemplo (empresa ficticia "Agroandina"): PDFs, imagen, audio y video.

Uso:  python tools/make_sample_kb.py [carpeta_destino]     (por defecto: base_conocimiento/)
Requiere las herramientas de diseño:  pip install -r requirements-dev.txt   (reportlab + matplotlib)
Los datos son inventados y coherentes entre archivos, para poder probar preguntas que crucen documentos.
El audio y el video usan las voces de Windows (System.Speech); en otros sistemas solo se generan PDFs e imagen.
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
import pymupdf

import sample_charts as ch
import sample_docs as docs

ROOT = Path(__file__).resolve().parent.parent
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "base_conocimiento"


# ---------- PDFs e imagen ----------

# archivo -> (nº de páginas, {página: [textos que DEBEN estar en esa página]}, {página: [textos que NO deben estar: viven solo en el gráfico]})
EXPECT = {
    "manual_sensor_AG200.pdf": (3, {1: ["-10 °C a 60 °C"], 2: ["6 meses"], 3: ["E-4471", "Sensor de humedad desconectado"]}, {}),
    "contrato_servicios.pdf": (3, {1: ["4.200 dólares", "24 meses"], 2: ["treinta días", "10 %", "cinco años", "Medellín"]}, {}),
    "informe_ventas_2026.pdf": (4, {4: ["48 %", "Andina SA"]}, {3: ["210", "T3"]}),
    "guia_instalacion_riego.pdf": (4, {1: ["45 minutos"], 2: ["15 metros", "2,5 bar"], 4: ["10 minutos", "Luis Pardo"]}, {3: ["18 sensores", "12 sensores"]}),
    "plan_estrategico_2027.pdf": (7, {2: ["38"], 3: ["30 minutos"], 5: ["Rotación del personal técnico"], 7: ["15 de enero de 2027"]}, {4: ["120"], 6: ["Piloto", "junio"]}),
}


def make_pdfs(dest: Path):
    docs.manual_sensor(dest / "manual_sensor_AG200.pdf")
    docs.contrato(dest / "contrato_servicios.pdf")
    docs.informe_ventas(dest / "informe_ventas_2026.pdf")
    docs.guia_instalacion(dest / "guia_instalacion_riego.pdf")
    docs.plan_estrategico(dest / "plan_estrategico_2027.pdf")
    docs.acta_escaneada(dest / "acta_reunion_escaneada.pdf")
    (dest / "organigrama.png").write_bytes(ch.orgchart())


def verify(dest: Path):
    """Comprueba que cada dato esté en la página prevista y que las cifras 'solo en el gráfico' no estén en el texto."""
    for name, (pages, must, must_not) in EXPECT.items():
        pdf = pymupdf.open(dest / name)
        text = [" ".join(p.get_text().split()) for p in pdf]  # las celdas de tabla parten líneas: se normalizan los espacios
        assert len(pdf) == pages, f"{name}: tiene {len(pdf)} páginas y debería tener {pages}"
        for page, needles in must.items():
            for n in needles:
                assert n in text[page - 1], f"{name}: falta «{n}» en la pág. {page}"
        for page, needles in must_not.items():
            for n in needles:
                assert n not in text[page - 1], f"{name}: «{n}» no debería estar en el texto de la pág. {page} (solo en el gráfico)"
    acta = pymupdf.open(dest / "acta_reunion_escaneada.pdf")
    assert len(acta) == 1 and not acta[0].get_text().strip() and acta[0].get_images(), "el acta debe ser solo imagen"
    print("verificación OK: páginas, datos por página y cifras solo-en-gráfico")


# ---------- audio y video (voces de Windows) ----------

PS_TTS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($args[0]); $s.SetOutputToWaveFile($args[1])
$s.Speak([IO.File]::ReadAllText($args[2], [Text.Encoding]::UTF8)); $s.Dispose()
"""


def tts(text: str, voice: str, out: Path, tmp: Path):
    (tmp / "tts.ps1").write_text(PS_TTS, encoding="utf-8")
    (tmp / "tts.txt").write_text(text, encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp / "tts.ps1"), voice, str(out), str(tmp / "tts.txt")],
                   check=True, capture_output=True)


def make_audio(dest: Path, tmp: Path):
    tts("Les habla Carlos Ruiz, gerente general de Agroandina. Quiero felicitar al equipo del proyecto Colibri. "
        "La meta para dos mil veintisiete es instalar quinientos sensores en doce fincas. "
        "La fecha de lanzamiento oficial es el doce de noviembre. Gracias por su esfuerzo.",
        "Microsoft Raul", dest / "mensaje_del_gerente.wav", tmp)


def make_video(dest: Path, tmp: Path, fps: int = 5):
    import av

    slides = [
        ("Capacitación de seguridad", "Agroandina S.A.S. · Personal de campo",
         "Bienvenidos a la capacitación de seguridad de Agroandina. Esta sesión es obligatoria para todo el personal de campo."),
        ("1. Equipo de protección", "Casco, gafas y guantes de nitrilo",
         "Primero, el equipo de protección. En la zona de instalación es obligatorio usar casco, gafas y guantes de nitrilo."),
        ("2. Extintores", "Tipo ABC cada 15 metros · revisión el primer lunes de cada mes",
         "Segundo, los extintores. Hay un extintor tipo A B C cada quince metros, y se revisan el primer lunes de cada mes."),
        ("3. En caso de emergencia", "Punto de encuentro: parqueadero norte · Extensión 911",
         "Tercero, en caso de emergencia diríjase al punto de encuentro del parqueadero norte y llame a la extensión nueve uno uno."),
    ]
    frames, audio, params = [], [], None
    for i, (title, sub, narration) in enumerate(slides):
        wav = tmp / f"s{i}.wav"
        tts(narration, "Microsoft Sabina Desktop", wav, tmp)
        with wave.open(str(wav)) as w:
            params, pcm = w.getparams(), w.readframes(w.getnframes())
        n = int((len(pcm) / 2 / params.framerate + 0.8) * fps) + 1  # narración + 0,8 s de pausa
        audio.append(pcm + b"\x00\x00" * int(params.framerate * n / fps - len(pcm) / 2))
        frames += [ch.slide(title, sub, i + 1, len(slides))] * n

    out = av.open(str(dest / "capacitacion_seguridad.mp4"), "w")
    v = out.add_stream("libx264", rate=fps)
    v.width, v.height, v.pix_fmt = 1280, 720, "yuv420p"
    a = out.add_stream("aac", rate=params.framerate)
    a.layout = "mono"
    for img in frames:
        for pkt in v.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
            out.mux(pkt)
    for pkt in v.encode():
        out.mux(pkt)
    pcm = np.frombuffer(b"".join(audio), np.int16).reshape(1, -1)
    frame = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
    frame.sample_rate = params.framerate
    res = av.AudioResampler(format="fltp", layout="mono", rate=params.framerate)
    for rf in res.resample(frame) + res.resample(None):
        for pkt in a.encode(rf):
            out.mux(pkt)
    for pkt in a.encode():
        out.mux(pkt)
    out.close()


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    make_pdfs(DEST)
    verify(DEST)
    print("PDFs e imagen listos en", DEST)
    if sys.platform == "win32":
        with tempfile.TemporaryDirectory() as t:
            make_audio(DEST, Path(t))
            make_video(DEST, Path(t))
        print("audio y video listos")
    else:
        print("Audio y video omitidos: requieren las voces de Windows.")
