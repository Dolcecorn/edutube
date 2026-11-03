"""Dibuja las gráficas (Pillow) y arma los reels (ffmpeg) con los colores de la marca."""
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

RAIZ = Path(__file__).resolve().parent
MARCA_DIR = RAIZ / "marca"
FUENTES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]
POST = (1080, 1350)   # 4:5, el formato que más ocupa en el feed
REEL = (1080, 1920)   # 9:16


FOTOS_DIR = MARCA_DIR / "fotos"
VIDEOS_DIR = MARCA_DIR / "videos"


def fotos():
    """Lista de fotos disponibles: [{archivo, descripcion, orientacion}]."""
    f = FOTOS_DIR / "fotos.json"
    if not f.exists():
        return []
    return [x for x in json.loads(f.read_text(encoding="utf-8")) if (FOTOS_DIR / x["archivo"]).exists()]


def videos():
    """Clips de video disponibles para los reels: [{archivo, descripcion}]."""
    f = VIDEOS_DIR / "videos.json"
    if not f.exists():
        return []
    return [x for x in json.loads(f.read_text(encoding="utf-8")) if (VIDEOS_DIR / x["archivo"]).exists()]


def _cubrir(ruta, ancho, alto):
    """Recorta y escala la foto para llenar exactamente ancho x alto (como object-fit: cover)."""
    im = ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")
    return ImageOps.fit(im, (ancho, alto), Image.LANCZOS, centering=(0.5, 0.55))


def _degradado(img, desde, hasta, alfa_ini, alfa_fin, color=(0, 0, 0)):
    """Oscurece una franja vertical de la imagen con un degradado (para que el texto se lea)."""
    W = img.width
    capa = Image.new("RGBA", (W, hasta - desde), color + (0,))
    dc = ImageDraw.Draw(capa)
    for y in range(hasta - desde):
        a = int(alfa_ini + (alfa_fin - alfa_ini) * y / max(1, hasta - desde - 1))
        dc.line([(0, y), (W, y)], fill=color + (a,))
    base = img.convert("RGBA")
    base.alpha_composite(capa, (0, desde))
    return base.convert("RGB")


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


def _logo(blanco, ancho_max, alto_max):
    ruta = MARCA_DIR / ("logo-blanco.png" if blanco else "logo.png")
    if not ruta.exists():
        return None
    lg = Image.open(ruta).convert("RGBA")
    lg.thumbnail((ancho_max, alto_max), Image.LANCZOS)
    return lg


def lamina(titulo, texto, destino, tamano=POST, numero=None, total=None, portada=False, foto=None):
    """Una lámina. Normal: fondo blanco, logo arriba, título rojo, detalle cyan, pie rojo con teléfono.
    Portada: fondo rojo, logo y textos en blanco, detalle cyan.
    Con foto (nombre de archivo en marca/fotos/): en portadas, posts sueltos y reels la foto va de fondo
    oscurecida; en las láminas interiores del carrusel, como franja bajo el logo."""
    m = marca()
    c = m["colores"]
    W, H = tamano
    reel = H >= 1600
    esc = 1.35 if reel else 1.0
    margen = 90
    ruta_foto = FOTOS_DIR / foto if foto and (FOTOS_DIR / foto).exists() else None
    modo = None
    if ruta_foto:
        modo = "fondo" if (portada or reel or not numero) else "franja"
    if modo == "fondo":
        img = _cubrir(ruta_foto, W, H)
        img = _degradado(img, 0, int(H * 0.22), 150, 0)              # arriba, para el logo
        img = _degradado(img, int(H * 0.28), H, 50, 235)              # abajo, para el texto
        portada = True                                                # textos y logo en blanco
        fondo = None
    else:
        fondo = c["principal"] if portada else c["claro"]
        img = Image.new("RGB", tamano, fondo)
    d = ImageDraw.Draw(img)

    # Encabezado: logo (en el reel se deja espacio arriba para la interfaz de Instagram)
    y_logo = 230 if reel else 70
    lg = _logo(portada, int(W * (0.62 if not reel else 0.8)), 120 if not reel else 200)
    if lg:
        img.paste(lg, (margen, y_logo), lg)
        alto_logo = lg.height
    else:
        f = _fuente(True, 56)
        d.text((margen, y_logo), m["nombre"].upper(), font=f, fill=c["claro"] if portada else c["principal"])
        alto_logo = 60
    y_linea = y_logo + alto_logo + 40
    if not portada:
        d.rectangle([margen, y_linea, W - margen, y_linea + 4], fill=c["acento"])
    alto_franja = 0
    if modo == "franja":
        alto_franja = int(H * 0.34)
        img.paste(_cubrir(ruta_foto, W, alto_franja), (0, y_linea + 4))
        d.rectangle([0, y_linea + 4 + alto_franja - 8, W, y_linea + 4 + alto_franja], fill=c["acento"])

    # Pie: franja con teléfono y cuenta
    alto_pie = 110 if not reel else 130
    y_pie = H - alto_pie - (300 if reel else 0)
    color_pie = c["claro"] if portada and modo != "fondo" else c["principal"]
    texto_pie_color = c["principal"] if portada and modo != "fondo" else c["claro"]
    d.rectangle([0, y_pie, W, y_pie + alto_pie], fill=color_pie)
    tam_pie = 38 if not reel else 44
    f_pie = _fuente(True, tam_pie)
    izquierda = m.get("telefono") or m["usuario"]
    derecha = f"{numero}/{total}" if numero and total else ((m.get("web") or m["usuario"]) if m.get("telefono") else "")
    while derecha and d.textlength(f"{izquierda}   {derecha}", font=f_pie) > W - 2 * margen and tam_pie > 30:
        tam_pie -= 2
        f_pie = _fuente(True, tam_pie)
    if derecha and d.textlength(f"{izquierda}   {derecha}", font=f_pie) > W - 2 * margen:
        derecha = f"{numero}/{total}" if numero and total else ""
    y_txt = y_pie + (alto_pie - tam_pie) // 2 - 4
    d.text((margen, y_txt), izquierda, font=f_pie, fill=texto_pie_color)
    if derecha:
        d.text((W - margen - d.textlength(derecha, font=f_pie), y_txt), derecha, font=f_pie, fill=texto_pie_color)
    if reel and fondo:  # bajo el pie, el mismo color de la lámina (con foto, se ve la foto)
        d.rectangle([0, y_pie + alto_pie, W, H], fill=fondo)

    # Contenido
    arriba = y_linea + 80 + alto_franja
    disponible = y_pie - arriba - 70
    if modo == "fondo":  # el texto va en la mitad inferior, sobre la parte oscurecida
        arriba = max(arriba, int(H * 0.36))
        disponible = y_pie - arriba - 60
    ancho = W - 2 * margen
    color_tit = c["claro"] if portada else c["principal"]
    color_txt = c["claro"] if portada else c["oscuro"]
    parte_titulo = 0.8 if not texto else (0.5 if modo == "fondo" else (0.8 if portada else 0.45))
    f_t, l_t, tam_t, alto_t = _ajustar(d, titulo, True, int((104 if portada else 84) * esc), 48, ancho,
                                       disponible * parte_titulo)
    alto_x, l_x, f_x, tam_x = 0, [], None, 0
    if texto:
        f_x, l_x, tam_x, alto_x = _ajustar(d, texto, False, int(56 * esc), 36, ancho,
                                           disponible - alto_t - 120, 1.4)
    alto_total = alto_t + 85 + alto_x
    centrar = (portada or not texto or reel) and modo != "fondo"
    if modo == "fondo":  # pegado abajo, justo sobre el pie
        y = arriba + max(0, disponible - alto_total)
    else:
        y = arriba + (max(0, (disponible - alto_total) // 2) if centrar else 0)
    for linea in l_t:
        d.text((margen, y), linea, font=f_t, fill=color_tit)
        y += int(tam_t * 1.25)
    y += 25
    d.rectangle([margen, y, margen + 160, y + 12], fill=c["acento"])
    y += 60
    for linea in l_x:
        d.text((margen, y), linea, font=f_x, fill=color_txt)
        y += int(tam_x * 1.4)

    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() == ".png":
        img.save(destino, "PNG")
    else:
        img.save(destino, "JPEG", quality=92)
    return destino


def reel(escenas, destino):
    """escenas: [(titulo, texto)] o [(titulo, texto, foto)]. Arma un MP4 9:16 con zoom suave y fundidos; música si existe marca/musica.mp3."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, escena in enumerate(escenas):
            titulo, texto = escena[0], escena[1]
            foto = escena[2] if len(escena) > 2 else None
            jpg = lamina(titulo, texto, tmp / f"e{i}.jpg", REEL, portada=(i == 0), foto=foto)
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


def historia(etiqueta, gancho, texto, llamado, destino=None, foto=None, capas=False):
    """Historia 9:16: foto de fondo oscurecida, etiqueta cyan, gancho grande, texto y tarjeta blanca con
    el llamado a la acción, teléfono y sitio web. Deja libres las zonas de la interfaz de Instagram
    (~250 px arriba y ~300 px abajo).
    capas=True: no guarda; devuelve (fondo RGB, [(nombre, imagen RGBA recortada, (x, y))]) para animarla."""
    m = marca()
    c = m["colores"]
    W, H = REEL
    margen = 80
    ancho = W - 2 * margen
    ruta = FOTOS_DIR / foto if foto and (FOTOS_DIR / foto).exists() else None
    if ruta:
        fondo = _cubrir(ruta, W, H)
        fondo = _degradado(fondo, 0, H, 70, 70)            # oscurece parejo
        fondo = _degradado(fondo, 0, 520, 140, 0)          # arriba, para el logo
        fondo = _degradado(fondo, 520, H, 0, 230)          # abajo, para el texto
    else:
        fondo = Image.new("RGB", (W, H), c["principal"])
    medir = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    elementos = []

    def capa(nombre):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        elementos.append((nombre, im))
        return ImageDraw.Draw(im), im

    lg = _logo(True, 470, 150)
    if lg:
        _, im = capa("logo")
        im.paste(lg, (margen, 250), lg)

    # Tarjeta del llamado a la acción (de abajo hacia arriba)
    f_cta = _fuente(True, 50)
    f_tel = _fuente(True, 66)
    f_web = _fuente(False, 38)
    tel, web = m.get("telefono", ""), m.get("web") or m.get("usuario", "")
    lin_cta = _envolver(medir, llamado, f_cta, ancho - 100)
    alto_card = 50 + len(lin_cta) * 62 + 20 + 80 + 56 + 45
    y_card = H - 320 - alto_card
    d, _ = capa("tarjeta")
    d.rounded_rectangle([margen, y_card, W - margen, y_card + alto_card], radius=36, fill=c["claro"])
    d.rectangle([margen, y_card + 36, margen + 14, y_card + alto_card - 36], fill=c["acento"])
    y = y_card + 50
    for ln in lin_cta:
        d.text((margen + 50, y), ln, font=f_cta, fill=c["oscuro"])
        y += 62
    y += 20
    d.text((margen + 50, y), "\u260E " + tel, font=f_tel, fill=c["principal"])
    y += 80
    d.text((margen + 50, y), web, font=f_web, fill=c["acento"])

    # Gancho y texto (encima de la tarjeta)
    f_txt, lin_txt, tam_c, alto_txt = _ajustar(medir, texto, False, 50, 38, ancho, 330, 1.35)
    f_tag = _fuente(True, 36)
    y_txt = y_card - 60 - alto_txt
    y_bar = y_txt - 40
    tope = 250 + (lg.height if lg else 60) + 60 + 92   # bajo el logo y la etiqueta
    f_gan, lin_gan, tam_g, alto_gan = _ajustar(medir, gancho, True, 104, 56, ancho, max(150, y_bar - 26 - tope), 1.12)
    y_gan = y_bar - 26 - alto_gan
    y_tag = y_gan - 92
    if etiqueta:
        d, _ = capa("etiqueta")
        tw = d.textlength(etiqueta.upper(), font=f_tag)
        d.rounded_rectangle([margen, y_tag, margen + tw + 44, y_tag + 62], radius=31, fill=c["acento"])
        d.text((margen + 22, y_tag + 11), etiqueta.upper(), font=f_tag, fill=c["claro"])
    y = y_gan
    for ln in lin_gan:
        d, _ = capa("gancho")
        d.text((margen + 3, y + 3), ln, font=f_gan, fill=(0, 0, 0))
        d.text((margen, y), ln, font=f_gan, fill=c["claro"])
        y += int(tam_g * 1.12)
    d, _ = capa("barra")
    d.rectangle([margen, y_bar, margen + 120, y_bar + 10], fill=c["acento"])
    y = y_txt
    for ln in lin_txt:
        d, _ = capa("texto")
        d.text((margen, y), ln, font=f_txt, fill=c["claro"])
        y += int(tam_c * 1.35)

    if capas:
        res = []
        for nombre, im in elementos:
            caja = im.getbbox()
            if caja:
                res.append((nombre, im.crop(caja), (caja[0], caja[1])))
        return fondo, res
    img = fondo.convert("RGBA")
    for _, im in elementos:
        img.alpha_composite(im)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(destino, "JPEG", quality=92)
    return destino
