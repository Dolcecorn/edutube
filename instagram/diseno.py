"""Dibuja las gráficas (Pillow) y arma los reels (ffmpeg) con los colores de la marca."""
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent
MARCA_DIR = RAIZ / "marca"
FUENTES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]
POST = (1080, 1350)   # 4:5, el formato que más ocupa en el feed
REEL = (1080, 1920)   # 9:16


def marca():
    return json.loads((MARCA_DIR / "marca.json").read_text(encoding="utf-8"))


def _fuente(negrita, tam):
    propias = sorted((MARCA_DIR / "fuentes").glob("*.ttf")) if (MARCA_DIR / "fuentes").exists() else []
    if propias:  # marca/fuentes/: la primera es negrita, la segunda normal
        return ImageFont.truetype(str(propias[0 if negrita or len(propias) == 1 else 1]), tam)
    for neg, reg in FUENTES:
        if Path(neg).exists():
            return ImageFont.truetype(neg if negrita else reg, tam)
    return ImageFont.load_default(tam)


def _envolver(draw, texto, fuente, ancho):
    lineas = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if draw.textlength(prueba, font=fuente) <= ancho:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def _ajustar(draw, texto, negrita, tam_max, tam_min, ancho, alto_max, interlineado=1.25):
    """Busca el tamaño de letra más grande con el que el texto cabe en el espacio."""
    tam = tam_max
    while True:
        f = _fuente(negrita, tam)
        lineas = _envolver(draw, texto, f, ancho)
        alto = int(len(lineas) * tam * interlineado)
        if alto <= alto_max or tam <= tam_min:
            return f, lineas, tam, alto
        tam -= 4


def lamina(titulo, texto, destino, tamano=POST, numero=None, total=None, portada=False):
    """Una lámina: franja superior con marca, título grande, texto y pie con la cuenta."""
    m = marca()
    c = m["colores"]
    W, H = tamano
    img = Image.new("RGB", tamano, c["claro"] if not portada else c["principal"])
    d = ImageDraw.Draw(img)
    margen = 90
    fondo_txt = c["claro"] if portada else c["oscuro"]

    # Franja superior
    alto_franja = 150 if H < 1600 else 260
    d.rectangle([0, 0, W, alto_franja], fill=c["oscuro"] if portada else c["principal"])
    logo = MARCA_DIR / "logo.png"
    x_nombre = margen
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((alto_franja - 50, alto_franja - 50))
        img.paste(lg, (margen, (alto_franja - lg.height) // 2 + (0 if H < 1600 else 40)), lg)
        x_nombre = margen + lg.width + 30
    f_nombre = _fuente(True, 46 if H < 1600 else 56)
    y_nombre = (alto_franja - 46) // 2 + (0 if H < 1600 else 40)
    d.text((x_nombre, y_nombre), m["nombre"].upper(), font=f_nombre, fill=c["claro"])
    # Cruz de vida simple a la derecha
    cx, cy, r = W - margen - 40, alto_franja // 2 + (0 if H < 1600 else 40), 40
    d.rectangle([cx - r // 3, cy - r, cx + r // 3, cy + r], fill=c["claro"])
    d.rectangle([cx - r, cy - r // 3, cx + r, cy + r // 3], fill=c["claro"])

    # Pie
    alto_pie = 120 if H < 1600 else 300
    y_pie = H - alto_pie
    pie = m["usuario"] + (f"  ·  {m['telefono']}" if m.get("telefono") else "")
    f_pie = _fuente(True, 38 if H < 1600 else 48)
    d.text((margen, y_pie + 30), pie, font=f_pie, fill=fondo_txt)
    if numero and total:
        t = f"{numero}/{total}"
        d.text((W - margen - d.textlength(t, font=f_pie), y_pie + 30), t, font=f_pie, fill=fondo_txt)

    # Zona de contenido
    arriba = alto_franja + 90
    disponible = y_pie - arriba - 60
    ancho = W - 2 * margen
    color_tit = c["claro"] if portada else c["principal"]
    esc = 1.35 if H >= 1600 else 1.0   # letras más grandes en el reel
    f_t, l_t, tam_t, alto_t = _ajustar(d, titulo, True, int((104 if portada else 84) * esc), 48, ancho,
                                       disponible * (0.8 if portada or not texto else 0.45))
    alto_x, l_x, f_x, tam_x = 0, [], None, 0
    if texto:
        f_x, l_x, tam_x, alto_x = _ajustar(d, texto, False, int(56 * esc), 30, ancho,
                                           disponible - alto_t - 120, 1.4)
    alto_total = alto_t + 85 + alto_x
    # Centrado vertical en portadas, láminas sin texto y reels; arriba en el resto
    centrar = portada or not texto or H >= 1600
    y = arriba + (max(0, (disponible - alto_total) // 2) if centrar else 0)
    for linea in l_t:
        d.text((margen, y), linea, font=f_t, fill=color_tit)
        y += int(tam_t * 1.25)
    y += 25
    d.rectangle([margen, y, margen + 160, y + 12], fill=c["acento"])
    y += 60
    for linea in l_x:
        d.text((margen, y), linea, font=f_x, fill=fondo_txt)
        y += int(tam_x * 1.4)

    if destino.suffix.lower() == ".png":
        img.save(destino, "PNG")
    else:
        img.save(destino, "JPEG", quality=92)
    return destino


def reel(escenas, destino):
    """escenas: [(titulo, texto)]. Arma un MP4 9:16 con zoom suave y fundidos; música si existe marca/musica.mp3."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, (titulo, texto) in enumerate(escenas):
            jpg = lamina(titulo, texto, tmp / f"e{i}.jpg", REEL, portada=(i == 0))
            dur = max(3.5, min(8.0, 2.0 + len(f"{titulo} {texto}".split()) * 0.32))  # tiempo para leer
            frames = int(dur * 30)
            clip = tmp / f"c{i}.mp4"
            vf = (f"scale=1188:2112,zoompan=z='min(zoom+0.0006,1.08)':d={frames}"
                  f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
                  f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4,format=yuv420p")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(jpg), "-vf", vf,
                            "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(clip)],
                           check=True)
            clips.append(clip)
        lista = tmp / "lista.txt"
        lista.write_text("".join(f"file '{c}'\n" for c in clips))
        musica = MARCA_DIR / "musica.mp3"
        audio = ["-stream_loop", "-1", "-i", str(musica)] if musica.exists() else \
            ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                        *audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        *(["-af", "volume=0.6"] if musica.exists() else []),
                        "-shortest", "-movflags", "+faststart", str(destino)], check=True)
    return destino
