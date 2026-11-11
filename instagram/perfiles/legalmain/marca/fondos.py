"""Genera los fondos abstractos de LegalMain (azul #171b30, grises y un acento dorado sutil), versión 2.

LegalMain no tiene banco de fotos propio: estos fondos cumplen ese rol (fotos/ + fotos.json) junto con los
clips de video. Calidad: se dibuja al doble de resolución y se reduce (bordes limpios), con luces suaves,
resplandor (glow) en las líneas, profundidad de campo (planos lejanos desenfocados) y un grano muy fino.
Uso: python3 instagram/perfiles/legalmain/marca/fondos.py
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 2                                  # supermuestreo
W, H = 1080 * S, 1920 * S
AZUL = np.array([23, 27, 48], float)   # #171b30
DORADO = (201, 164, 76)
BLANCO = (232, 236, 246)
DIR = Path(__file__).resolve().parent / "fotos"


def base(luces, semilla):
    """Fondo: azul de marca con 2-3 luces suaves (azul frío y un toque cálido) y bokeh muy tenue."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.repeat(np.repeat(AZUL[None, None, :], 1, 0), 1, 1) * np.ones((H, W, 1), np.float32)
    for cx, cy, r, color, k in luces:
        d2 = ((x / W - cx) ** 2 + ((y / H - cy) * 0.56) ** 2) / (r * r)
        img += np.exp(-d2)[..., None] * np.array(color, np.float32)[None, None, :] * k * 0.42
    # viñeta
    v = np.sqrt((x / W - 0.5) ** 2 + ((y / H - 0.5) * 0.7) ** 2)
    img *= (1 - 0.45 * np.clip((v - 0.25) / 0.5, 0, 1) ** 1.5)[..., None]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    # bokeh: discos grandes y desenfocados
    r = np.random.default_rng(semilla)
    b = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    for _ in range(14):
        rad = r.uniform(30, 110) * S
        cx, cy = r.uniform(0, W), r.uniform(0, H * 0.75)
        col = DORADO if r.random() < 0.25 else (150, 170, 220)
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col + (int(r.uniform(8, 22)),))
    im.alpha_composite(b.filter(ImageFilter.GaussianBlur(14 * S)))
    return im


def capa():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def con_brillo(img, c, glow=10, fuerza=0.9, desenfoque=0):
    """Pega una capa de líneas con resplandor suave; desenfoque > 0 simula un plano lejano."""
    if desenfoque:
        c = c.filter(ImageFilter.GaussianBlur(desenfoque * S))
    halo = c.filter(ImageFilter.GaussianBlur(glow * S))
    fuerza *= 1.6
    a = halo.split()[3].point(lambda v: int(min(255, v * fuerza)))
    halo.putalpha(a)
    img.alpha_composite(halo)
    img.alpha_composite(c)


def linea(d, pts, color, alfa, ancho=1.6):
    d.line([(px * S, py * S) for px, py in pts], fill=color + (alfa,), width=max(1, int(ancho * S)), joint="curve")


def punto(d, x, y, rad, color, alfa):
    d.ellipse([(x - rad) * S, (y - rad) * S, (x + rad) * S, (y + rad) * S], fill=color + (alfa,))


# ---------- motivos (coordenadas en 1080x1920) ----------

def globo(img, semilla, cx=540, cy=760, R=430):
    """Globo de puntos en perspectiva con arcos de conexión desde un origen dorado (internacionalización)."""
    r = np.random.default_rng(semilla)
    rot = r.uniform(0, math.pi)
    lejos, cerca = capa(), capa()
    dl, dc = ImageDraw.Draw(lejos), ImageDraw.Draw(cerca)
    for lat in np.linspace(-80, 80, 46):
        for lon in np.linspace(0, 360, int(110 * math.cos(math.radians(lat))) + 1)[:-1]:
            la, lo = math.radians(lat), math.radians(lon) + rot
            x3, y3, z3 = math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo)
            # continentes aproximados con ruido suave
            tierra = math.sin(lo * 2.1 + 1.3) * math.cos(la * 2.7) + 0.6 * math.sin(lo * 4.3 + la * 3.1)
            if tierra < -0.1:
                continue
            x, y = cx + R * x3, cy - R * y3
            if z3 > 0:
                punto(dc, x, y, 2.2 * (0.6 + 0.4 * z3), BLANCO, int(60 + 120 * z3))
            else:
                punto(dl, x, y, 1.6, BLANCO, 35)
    dc.ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], outline=BLANCO + (40,), width=2 * S)
    con_brillo(img, lejos, glow=4, fuerza=0.4, desenfoque=2)
    # arcos
    arcos = capa()
    da = ImageDraw.Draw(arcos)
    ox, oy = cx - R * 0.25, cy + R * 0.45
    destinos = [(cx + r.uniform(-0.8, 0.8) * R, cy + r.uniform(-0.75, 0.3) * R) for _ in range(6)]
    for tx, ty in destinos:
        mx, my = (ox + tx) / 2, min(oy, ty) - abs(tx - ox) * 0.45 - 60
        pts = [((1 - t) ** 2 * ox + 2 * (1 - t) * t * mx + t ** 2 * tx,
                (1 - t) ** 2 * oy + 2 * (1 - t) * t * my + t ** 2 * ty) for t in np.linspace(0, 1, 90)]
        linea(da, pts, (240, 222, 170), 150, 1.4)
        punto(da, tx, ty, 4.5, BLANCO, 230)
    punto(da, ox, oy, 8, DORADO, 255)
    con_brillo(img, cerca, glow=6, fuerza=0.6)
    con_brillo(img, arcos, glow=9, fuerza=1.0)


def documentos(img, semilla):
    """Hojas de vidrio esmerilado en profundidad, líneas de texto y firma dorada (contratos, bases)."""
    r = np.random.default_rng(semilla)
    for k, (x0, y0, ang, desen) in enumerate([(150, 330, -10, 5), (300, 470, 4, 2), (230, 600, -3, 0)]):
        c = capa()
        d = ImageDraw.Draw(c)
        w, h = 640, 860
        d.rounded_rectangle([x0 * S, y0 * S, (x0 + w) * S, (y0 + h) * S], radius=18 * S,
                            fill=(200, 212, 245, 12 + 6 * k), outline=BLANCO + (110,), width=int(1.5 * S))
        d.rectangle([(x0 + 60) * S, (y0 + 70) * S, (x0 + 300) * S, (y0 + 82) * S], fill=BLANCO + (120,))
        for i in range(13):
            ly = y0 + 140 + i * 46
            largo = w - 130 - int(r.uniform(0, 200))
            d.rounded_rectangle([(x0 + 60) * S, ly * S, (x0 + 60 + largo) * S, (ly + 7) * S], radius=3 * S,
                                fill=BLANCO + (45,))
        if k == 2:
            pts = [(x0 + 70 + t * 230, y0 + h - 120 - 22 * math.sin(t * 7) * (1 - t)) for t in np.linspace(0, 1, 60)]
            linea(d, pts, DORADO, 230, 2.2)
            linea(d, [(x0 + 60, y0 + h - 90), (x0 + 330, y0 + h - 90)], BLANCO, 90, 1.2)
        c = c.rotate(ang, resample=Image.BICUBIC, center=(W / 2, H / 2))
        con_brillo(img, c, glow=8, fuerza=0.35, desenfoque=desen)


def columnas(img, semilla):
    """Fachada clásica en perspectiva leve, líneas finas con luz cenital (derecho, Estado, instituciones)."""
    c = capa()
    d = ImageDraw.Draw(c)
    x0, x1, y0, y1 = 150, 930, 600, 1300
    linea(d, [(x0 - 60, y0), (540, y0 - 240), (x1 + 60, y0), (x0 - 60, y0)], BLANCO, 150, 2)
    linea(d, [(x0 - 20, y0 - 22), (540, y0 - 205), (x1 + 20, y0 - 22)], BLANCO, 60, 1.2)
    for yy, a in ((y0 + 18, 140), (y0 + 40, 90)):
        linea(d, [(x0 - 70, yy), (x1 + 70, yy)], BLANCO, a, 1.8)
    for i in range(6):
        x = x0 + 40 + i * (x1 - x0 - 80) / 5
        for dx, a, wd in ((-30, 120, 1.8), (30, 120, 1.8), (-12, 45, 1.0), (0, 30, 1.0), (12, 45, 1.0)):
            linea(d, [(x + dx, y0 + 70), (x + dx, y1)], BLANCO, a, wd)
        linea(d, [(x - 42, y0 + 62), (x + 42, y0 + 62)], BLANCO, 110, 1.6)
        linea(d, [(x - 42, y1 + 4), (x + 42, y1 + 4)], BLANCO, 110, 1.6)
    for k, a in enumerate((140, 100, 70)):
        linea(d, [(x0 - 90 - k * 30, y1 + 22 + k * 22), (x1 + 90 + k * 30, y1 + 22 + k * 22)], BLANCO, a, 1.6)
    linea(d, [(x0 - 190, y1 + 110), (x1 + 190, y1 + 110)], DORADO, 210, 2)
    con_brillo(img, c, glow=8, fuerza=0.7)


def escudo(img, semilla):
    """Escudo de vidrio con candado dorado y anillos de datos (protección de datos personales)."""
    cx, cy = 540, 820
    anillos = capa()
    d = ImageDraw.Draw(anillos)
    for k, (rad, n) in enumerate(((300, 24), (390, 36), (480, 48))):
        for i in range(n):
            a = 2 * math.pi * i / n + k * 0.2
            x, y = cx + rad * math.cos(a), cy + rad * math.sin(a) * 0.92
            punto(d, x, y, 2.6 if i % 3 else 4, BLANCO, 150 - k * 35)
        pts = [(cx + rad * math.cos(t), cy + rad * math.sin(t) * 0.92) for t in np.linspace(0.3, 5.4 - k * 0.6, 120)]
        linea(d, pts, BLANCO, 60, 1.2)
    con_brillo(img, anillos, glow=6, fuerza=0.6, desenfoque=1)
    c = capa()
    d = ImageDraw.Draw(c)
    s = [(cx, cy - 230), (cx + 185, cy - 160), (cx + 165, cy + 90), (cx, cy + 240), (cx - 165, cy + 90),
         (cx - 185, cy - 160)]
    d.polygon([(x * S, y * S) for x, y in s], fill=(30, 36, 66, 235))
    linea(d, s + [s[0]], BLANCO, 190, 2)
    s2 = [(cx + (x - cx) * 0.86, cy + (y - cy) * 0.86) for x, y in s]
    linea(d, s2 + [s2[0]], BLANCO, 50, 1.2)
    d.rounded_rectangle([(cx - 64) * S, (cy - 15) * S, (cx + 64) * S, (cy + 90) * S], radius=14 * S,
                        outline=DORADO + (255,), width=5 * S)
    d.arc([(cx - 44) * S, (cy - 88) * S, (cx + 44) * S, (cy + 4) * S], 180, 360, fill=DORADO + (255,), width=5 * S)
    punto(d, cx, cy + 32, 9, DORADO, 255)
    d.rectangle([(cx - 3) * S, (cy + 36) * S, (cx + 3) * S, (cy + 60) * S], fill=DORADO + (255,))
    con_brillo(img, c, glow=12, fuerza=0.5)


def crecimiento(img, semilla):
    """Cuadrícula técnica en perspectiva, barras de vidrio y línea dorada ascendente (empresa, decisiones)."""
    g = capa()
    d = ImageDraw.Draw(g)
    hz, fx = 1000, 540
    for i in range(-12, 13):            # líneas de fuga hacia el horizonte
        linea(d, [(fx + i * 30, hz), (fx + i * 260, 1920)], BLANCO, 22, 1)
    for k in range(14):
        y = hz + (1920 - hz) * (k / 14) ** 1.8
        linea(d, [(0, y), (1080, y)], BLANCO, 20, 1)
    con_brillo(img, g, glow=3, fuerza=0.3, desenfoque=1)
    c = capa()
    d = ImageDraw.Draw(c)
    alturas = [180, 250, 230, 330, 410, 520]
    for i, a in enumerate(alturas):
        x = 190 + i * 125
        d.rounded_rectangle([x * S, (1230 - a) * S, (x + 74) * S, 1230 * S], radius=6 * S,
                            fill=(210, 220, 245, 28 + i * 9), outline=BLANCO + (90,), width=int(1.2 * S))
    pts = [(227 + i * 125, 1230 - a - 40) for i, a in enumerate(alturas)]
    linea(d, pts, DORADO, 255, 2.6)
    for x, y in pts:
        punto(d, x, y, 6, DORADO, 255)
    linea(d, [(150, 1230), (930, 1230)], BLANCO, 120, 1.4)
    con_brillo(img, c, glow=10, fuerza=0.8)


def balanza(img, semilla):
    """Balanza de la justicia en línea fina con platos de vidrio y eje dorado."""
    c = capa()
    d = ImageDraw.Draw(c)
    cx = 540
    linea(d, [(cx, 440), (cx, 1200)], BLANCO, 200, 2.4)
    linea(d, [(cx - 320, 560), (cx + 320, 560)], BLANCO, 200, 2.4)
    linea(d, [(cx - 320, 560), (cx, 520), (cx + 320, 560)], BLANCO, 70, 1.2)
    for sx in (-320, 320):
        for dx in (-120, 0, 120):
            linea(d, [(cx + sx, 560), (cx + sx + dx, 860)], BLANCO, 90, 1.2)
        d.chord([(cx + sx - 140) * S, 790 * S, (cx + sx + 140) * S, 930 * S], 0, 180,
                fill=(210, 220, 245, 35), outline=BLANCO + (190,), width=int(2 * S))
    d.polygon([((cx - 130) * S, 1200 * S), ((cx + 130) * S, 1200 * S), ((cx + 175) * S, 1250 * S),
               ((cx - 175) * S, 1250 * S)], fill=(210, 220, 245, 30), outline=BLANCO + (160,))
    linea(d, [(cx - 230, 1268), (cx + 230, 1268)], DORADO, 220, 2)
    punto(d, cx, 430, 13, DORADO, 255)
    con_brillo(img, c, glow=10, fuerza=0.7)



# ---------- motivos "premium" (licitaciones, 2026-11-10): vidrio en perspectiva, oro metálico, reflejos ----------

def _coef(src, dst):
    """Coeficientes de Image.PERSPECTIVE que llevan cada punto de dst (salida) a src (entrada)."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float))


def _mapa(quad, w, h):
    """Función que lleva un punto (x, y) del panel (unidades 1080) a la pantalla (unidades 1080)."""
    c = _coef(quad, [(0, 0), (w, 0), (w, h), (0, h)])
    return lambda x, y: ((c[0] * x + c[1] * y + c[2]) / (c[6] * x + c[7] * y + 1),
                         (c[3] * x + c[4] * y + c[5]) / (c[6] * x + c[7] * y + 1))


def _proyectar(panel, quad):
    pw, ph = panel.size
    return panel.transform((W, H), Image.PERSPECTIVE,
                           _coef([(0, 0), (pw, 0), (pw, ph), (0, ph)], [(x * S, y * S) for x, y in quad]),
                           Image.BICUBIC)


_PARADAS = [(0.0, (104, 74, 26)), (0.22, (226, 188, 108)), (0.38, (255, 236, 176)), (0.52, (168, 124, 46)),
            (0.74, (242, 210, 138)), (1.0, (120, 86, 30))]


def _oro(mascara, angulo=35):
    """Relleno de oro cepillado (degradado metálico con brillos) recortado por una máscara L."""
    w, h = mascara.size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angulo)
    t = (x * math.cos(a) + y * math.sin(a))
    t = (t - t.min()) / (np.ptp(t) + 1e-6)
    t = (t * 2.2) % 1.0
    xs = [p for p, _ in _PARADAS]
    rgb = np.stack([np.interp(t, xs, [c[k] for _, c in _PARADAS]) for k in range(3)], -1)
    rgb += np.random.default_rng(3).normal(0, 3, (h, w, 1))          # cepillado fino
    im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    im.putalpha(mascara)
    return im


def _vidrio(w, h, radio=22, tinte=(214, 226, 255), alfa=(58, 16), borde=150):
    """Panel de vidrio: degradado vertical, filo iluminado arriba a la izquierda y un reflejo diagonal."""
    pw, ph = int(w * S), int(h * S)
    yy = np.linspace(0, 1, ph)[:, None] * np.ones((1, pw))
    xx = np.linspace(0, 1, pw)[None, :] * np.ones((ph, 1))
    al = alfa[0] * (1 - yy) + alfa[1] * yy
    al += 34 * np.exp(-((xx + yy * 0.55 - 0.42) / 0.07) ** 2)          # reflejo diagonal
    m = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=radio * S, fill=255)
    arr = np.zeros((ph, pw, 4), np.uint8)
    arr[..., :3] = tinte
    arr[..., 3] = (np.clip(al, 0, 255) * (np.asarray(m, np.float32) / 255)).astype(np.uint8)
    p = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([1, 1, pw - 2, ph - 2], radius=radio * S, outline=BLANCO + (borde,), width=int(1.6 * S))
    # filo superior e izquierdo más brillante
    filo = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(filo).rounded_rectangle([1, 1, pw - 2, ph - 2], radius=radio * S, outline=(255, 255, 255, 255),
                                           width=int(2.4 * S))
    g = np.clip(1.2 - (yy * 1.4 + xx * 0.8), 0, 1)
    fa = (np.asarray(filo.split()[3], np.float32) * g).astype(np.uint8)
    filo.putalpha(Image.fromarray(fa))
    p.alpha_composite(filo)
    return p, d


def _texto(d, w, filas, r, x0=46, y0=120, paso=46, oro=None, vistos=()):
    """Líneas de texto simuladas dentro de un panel (coordenadas del panel en unidades 1080)."""
    d.rounded_rectangle([x0 * S, (y0 - 66) * S, (x0 + w * 0.42) * S, (y0 - 54) * S], radius=4 * S, fill=BLANCO + (190,))
    ys = []
    for i in range(filas):
        y = y0 + i * paso
        largo = w - x0 * 2 - int(r.uniform(0, w * 0.28))
        col, a = (DORADO, 0) if i == oro else (BLANCO, 70)
        d.rounded_rectangle([x0 * S, y * S, (x0 + largo) * S, (y + 8) * S], radius=4 * S, fill=col + (a,))
        if i in vistos:
            cx = w - x0 + 6
            d.line([((cx - 14) * S, (y + 2) * S), ((cx - 6) * S, (y + 12) * S), ((cx + 10) * S, (y - 10) * S)],
                   fill=BLANCO + (200,), width=int(2.4 * S), joint="curve")
        ys.append((y, largo))
    return ys


def _escena(img, semilla, horizonte=1420):
    """Rayos de luz, piso reflectante con grilla en perspectiva; devuelve la capa de objetos y el cierre."""
    r = np.random.default_rng(semilla + 100)
    rayos = capa()
    d = ImageDraw.Draw(rayos)
    for k in range(5):
        x = r.uniform(-200, 500)
        ancho = r.uniform(60, 160)
        d.polygon([(x * S, -50 * S), ((x + ancho) * S, -50 * S), ((x + ancho + 900) * S, 2000 * S),
                   ((x + 700) * S, 2000 * S)], fill=(150, 175, 240, int(r.uniform(10, 20))))
    img.alpha_composite(rayos.filter(ImageFilter.GaussianBlur(40 * S)))
    piso = capa()
    d = ImageDraw.Draw(piso)
    for i in range(-16, 17):
        linea(d, [(540 + i * 22, horizonte), (540 + i * 210, 1920)], BLANCO, 16, 1)
    for k in range(12):
        y = horizonte + (1920 - horizonte) * (k / 12) ** 1.9
        linea(d, [(0, y), (1080, y)], BLANCO, 14, 1)
    linea(d, [(80, horizonte), (1000, horizonte)], BLANCO, 50, 1.2)
    img.alpha_composite(piso.filter(ImageFilter.GaussianBlur(0.6 * S)))
    resplandor = capa()
    ImageDraw.Draw(resplandor).ellipse([140 * S, (horizonte - 60) * S, 940 * S, (horizonte + 60) * S],
                                       fill=(120, 150, 230, 40))
    img.alpha_composite(resplandor.filter(ImageFilter.GaussianBlur(40 * S)))
    obj = capa()

    def cerrar():
        # reflejo en el piso: la parte de los objetos sobre el horizonte, invertida y desvanecida
        hz = horizonte * S
        arriba = obj.crop((0, 0, W, hz)).transpose(Image.FLIP_TOP_BOTTOM)
        alto = min(H - hz, hz)
        arriba = arriba.crop((0, 0, W, alto))
        fade = np.linspace(0.32, 0, alto)[:, None] * np.ones((1, W))
        al = (np.asarray(arriba.split()[3], np.float32) * fade).astype(np.uint8)
        arriba.putalpha(Image.fromarray(al))
        ref = capa()
        ref.paste(arriba.filter(ImageFilter.GaussianBlur(3 * S)), (0, hz))
        img.alpha_composite(ref)
        halo = obj.filter(ImageFilter.GaussianBlur(14 * S))
        halo.putalpha(halo.split()[3].point(lambda v: int(v * 0.55)))
        img.alpha_composite(halo)
        img.alpha_composite(obj)
        # partículas: cerca (desenfocadas) y lejos (nítidas)
        for n, tam, desen, alfa in ((70, (1.5, 3.5), 0, (60, 150)), (16, (8, 18), 6, (25, 60))):
            c = capa()
            dd = ImageDraw.Draw(c)
            for _ in range(n):
                x, y, rad = r.uniform(0, 1080), r.uniform(80, 1500), r.uniform(*tam)
                col = DORADO if r.random() < 0.35 else BLANCO
                punto(dd, x, y, rad, col, int(r.uniform(*alfa)))
            img.alpha_composite(c.filter(ImageFilter.GaussianBlur(desen * S)) if desen else c)
    return obj, cerrar


def _pegar(obj, capa_):
    obj.alpha_composite(capa_)


def lupa(img, semilla):
    """Documento de vidrio recostado y una lupa de oro que revela una línea dorada (revisar las bases)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 600, 840
    panel, d = _vidrio(w, h)
    filas = _texto(d, w, 15, r, oro=7)
    quad = [(250, 440), (860, 500), (930, 1360), (150, 1310)]
    _pegar(obj, _proyectar(panel, quad))
    f = _mapa(quad, w, h)
    y7 = filas[7][0] + 4
    (gx0, gy0), (gx1, gy1) = f(46, y7), f(46 + filas[7][1], y7)
    cx, cy, R = (gx0 + gx1) / 2 + 40, (gy0 + gy1) / 2, 215
    # lente: aumenta lo que hay debajo
    caja = (int((cx - R) * S), int((cy - R) * S), int((cx + R) * S), int((cy + R) * S))
    zoom = obj.crop(caja)
    zw = zoom.width
    zoom = zoom.crop((int(zw * 0.19), int(zw * 0.19), int(zw * 0.81), int(zw * 0.81))).resize((zw, zw), Image.LANCZOS)
    zm = Image.new("L", (zw, zw), 0)
    ImageDraw.Draw(zm).ellipse([0, 0, zw - 1, zw - 1], fill=255)
    lente = Image.new("RGBA", (zw, zw), (24, 30, 56, 210))
    lente.putalpha(zm)
    lente.alpha_composite(Image.composite(zoom, Image.new("RGBA", (zw, zw), (0, 0, 0, 0)), zm))
    dl = ImageDraw.Draw(lente)
    gm = Image.new("L", (zw, zw), 0)                                 # la línea dorada, aumentada
    ImageDraw.Draw(gm).rounded_rectangle([int(zw * 0.08), int(zw * 0.47), int(zw * 0.86), int(zw * 0.53)],
                                         radius=int(zw * 0.03), fill=255)
    gm = Image.composite(gm, Image.new("L", (zw, zw), 0), zm)
    lente.alpha_composite(_oro(gm, 10))
    brillo = Image.new("RGBA", (zw, zw), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse([int(zw * 0.12), int(zw * 0.08), int(zw * 0.7), int(zw * 0.42)],
                                   fill=(255, 255, 255, 40))
    lente.alpha_composite(Image.composite(brillo.filter(ImageFilter.GaussianBlur(10 * S)),
                                          Image.new("RGBA", (zw, zw), (0, 0, 0, 0)), zm))
    dl.arc([int(zw * 0.08), int(zw * 0.08), int(zw * 0.92), int(zw * 0.92)], 200, 260, fill=(255, 255, 255, 190),
           width=int(4 * S))
    obj.alpha_composite(lente, (caja[0], caja[1]))
    # aro y mango de oro
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    dm.ellipse([(cx - R - 12) * S, (cy - R - 12) * S, (cx + R + 12) * S, (cy + R + 12) * S], outline=255,
               width=int(26 * S))
    a = math.radians(48)
    x1, y1 = cx + (R + 20) * math.cos(a), cy + (R + 20) * math.sin(a)
    x2, y2 = x1 + 70 * math.cos(a), y1 + 70 * math.sin(a)
    dm.line([(x1 * S, y1 * S), (x2 * S, y2 * S)], fill=255, width=int(30 * S))
    obj.alpha_composite(_oro(m, 30))
    mango = Image.new("L", (W, H), 0)
    x3, y3 = x2 + 230 * math.cos(a), y2 + 230 * math.sin(a)
    ImageDraw.Draw(mango).line([(x2 * S, y2 * S), (x3 * S, y3 * S)], fill=255, width=int(44 * S))
    ImageDraw.Draw(mango).ellipse([(x3 - 22) * S, (y3 - 22) * S, (x3 + 22) * S, (y3 + 22) * S], fill=255)
    mg = Image.new("RGBA", (W, H), (18, 22, 40, 255))
    mg.putalpha(mango)
    obj.alpha_composite(mg)
    ImageDraw.Draw(obj).line([((x2 + 8) * S, (y2 + 2) * S), ((x3 - 6) * S, (y3 - 12) * S)], fill=(120, 140, 200, 120),
                             width=int(3 * S))
    cerrar()


def comparar(img, semilla):
    """Dos documentos de vidrio enfrentados en perspectiva, unidos por haces de luz; una diferencia en oro."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 420, 760
    qa = [(90, 430), (470, 520), (470, 1300), (90, 1380)]
    qb = [(610, 520), (990, 430), (990, 1380), (610, 1300)]
    pa, da = _vidrio(w, h)
    fa = _texto(da, w, 13, r, oro=6)
    pb, db = _vidrio(w, h)
    fb = _texto(db, w, 13, r, oro=6, vistos=(1, 3, 5, 9, 11))
    _pegar(obj, _proyectar(pa, qa))
    _pegar(obj, _proyectar(pb, qb))
    ma, mb = _mapa(qa, w, h), _mapa(qb, w, h)
    haz = capa()
    d = ImageDraw.Draw(haz)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for i, ((ya, la), (yb, lb)) in enumerate(zip(fa, fb)):
        p0, p1 = ma(46 + la + 6, ya + 4), mb(40, yb + 4)
        if i == 6:
            dm.line([(p0[0] * S, p0[1] * S), (p1[0] * S, p1[1] * S)], fill=255, width=int(4 * S))
            for (x, y) in (p0, p1):
                dm.polygon([((x) * S, (y - 12) * S), ((x + 12) * S, y * S), (x * S, (y + 12) * S), ((x - 12) * S, y * S)],
                           fill=255)
            for (pp, ll, mm) in ((fa[6], la, ma), (fb[6], lb, mb)):
                q = [mm(46, pp[0]), mm(46 + ll, pp[0]), mm(46 + ll, pp[0] + 8), mm(46, pp[0] + 8)]
                dm.polygon([(x * S, y * S) for x, y in q], fill=255)
        elif i % 2 == 1:
            d.line([(p0[0] * S, p0[1] * S), (p1[0] * S, p1[1] * S)], fill=(200, 215, 255, 70), width=int(1.6 * S))
    obj.alpha_composite(haz)
    obj.alpha_composite(_oro(m, 0))
    cerrar()


def carpeta(img, semilla):
    """Hojas de vidrio en abanico saliendo de una carpeta azul con pestaña de oro (conservar antecedentes)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 560, 700
    for k, (q, desen) in enumerate([([(200, 420), (720, 380), (760, 1060), (230, 1100)], 3),
                                    ([(330, 470), (850, 450), (860, 1100), (330, 1110)], 0)]):
        p, d = _vidrio(w, h, alfa=(50, 14))
        _texto(d, w, 12, r)
        c = _proyectar(p, q)
        if desen:
            c = c.filter(ImageFilter.GaussianBlur(desen * S))
        obj.alpha_composite(c)
    # carpeta
    fw, fh = 760, 560
    pf, dfp = _vidrio(fw, fh, radio=18, tinte=(30, 38, 74), alfa=(245, 250), borde=170)
    dfp.rounded_rectangle([70 * S, 90 * S, 470 * S, 102 * S], radius=6 * S, fill=BLANCO + (120,))
    dfp.rounded_rectangle([70 * S, 140 * S, 340 * S, 150 * S], radius=5 * S, fill=BLANCO + (60,))
    q = [(180, 950), (920, 920), (960, 1400), (140, 1420)]
    obj.alpha_composite(_proyectar(pf, q))
    f = _mapa(q, fw, fh)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    pest = [f(60, -40), f(250, -40), f(250, 4), f(60, 4)]
    dm.polygon([(x * S, y * S) for x, y in pest], fill=255)
    linea_oro = [f(0, fh + 30), f(fw, fh + 30)]
    dm.line([(x * S, y * S) for x, y in linea_oro], fill=255, width=int(3 * S))
    sello = f(fw - 110, fh - 120)
    dm.ellipse([(sello[0] - 42) * S, (sello[1] - 42) * S, (sello[0] + 42) * S, (sello[1] + 42) * S], outline=255,
               width=int(6 * S))
    obj.alpha_composite(_oro(m, 20))
    cerrar()


def reloj(img, semilla):
    """Reloj de vidrio en leve perspectiva con un arco de oro que avanza (plazos)."""
    obj, cerrar = _escena(img, semilla)
    D = 720
    p = Image.new("RGBA", (D * S, D * S), (0, 0, 0, 0))
    disco, _ = _vidrio(D, D, radio=D // 2, alfa=(60, 20))
    p.alpha_composite(disco)
    d = ImageDraw.Draw(p)
    c, R = D / 2, D / 2 - 40
    for i in range(60):
        a = 2 * math.pi * i / 60 - math.pi / 2
        l0 = R - (44 if i % 5 == 0 else 22)
        d.line([((c + l0 * math.cos(a)) * S, (c + l0 * math.sin(a)) * S),
                ((c + (R - 6) * math.cos(a)) * S, (c + (R - 6) * math.sin(a)) * S)],
               fill=BLANCO + (220 if i % 5 == 0 else 90,), width=int((3 if i % 5 == 0 else 1.4) * S))
    m = Image.new("L", p.size, 0)
    dm = ImageDraw.Draw(m)
    dm.arc([(c - R - 4) * S, (c - R - 4) * S, (c + R + 4) * S, (c + R + 4) * S], -90, 175, fill=255, width=int(16 * S))
    a = math.radians(175)
    px, py = c + (R - 4) * math.cos(a), c + (R - 4) * math.sin(a)
    dm.ellipse([(px - 18) * S, (py - 18) * S, (px + 18) * S, (py + 18) * S], fill=255)
    dm.ellipse([(c - 22) * S, (c - 22) * S, (c + 22) * S, (c + 22) * S], fill=255)
    for ang, largo, ancho in ((210, R * 0.5, 12), (265, R * 0.78, 7)):
        a = math.radians(ang - 90)
        d.line([(c * S, c * S), ((c + largo * math.cos(a)) * S, (c + largo * math.sin(a)) * S)],
               fill=(235, 240, 255, 240), width=int(ancho * S))
    p.alpha_composite(_oro(m, 40))
    quad = [(190, 470), (900, 430), (930, 1170), (160, 1190)]
    obj.alpha_composite(_proyectar(p, quad))
    cerrar()


def sello(img, semilla):
    """Resolución de vidrio recostada con un sello de oro en relieve y cintas (adjudicación)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 640, 880
    panel, d = _vidrio(w, h)
    _texto(d, w, 13, r)
    d.line([(60 * S, (h - 120) * S), (300 * S, (h - 120) * S)], fill=BLANCO + (110,), width=int(1.4 * S))
    quad = [(230, 420), (880, 470), (950, 1350), (140, 1300)]
    obj.alpha_composite(_proyectar(panel, quad))
    cx, cy, R = 700, 1150, 175
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for dx, ang in ((-60, 100), (60, 80)):                           # cintas
        a = math.radians(ang)
        x0, y0 = cx + dx * 0.6, cy + 60
        x1, y1 = x0 + 230 * math.cos(a), y0 + 230 * math.sin(a)
        dm.polygon([((x0 - 34) * S, y0 * S), ((x0 + 34) * S, y0 * S), ((x1 + 34) * S, y1 * S), (x1 * S, (y1 - 40) * S),
                    ((x1 - 34) * S, y1 * S)], fill=255)
    cinta = _oro(m, 80)
    cinta.alpha_composite(Image.new("RGBA", (W, H), (60, 20, 10, 70)))
    cinta.putalpha(m)
    obj.alpha_composite(cinta)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    pts = []
    for i in range(72):                                              # borde dentado
        a = 2 * math.pi * i / 72
        rr = R if i % 2 == 0 else R - 12
        pts.append(((cx + rr * math.cos(a)) * S, (cy + rr * math.sin(a)) * S))
    dm.polygon(pts, fill=255)
    obj.alpha_composite(_oro(m, 35))
    rel = capa()                                                     # relieve: anillos y estrella
    dr = ImageDraw.Draw(rel)
    for rad, a in ((R - 30, 150), (R - 44, 90), (R - 92, 120)):
        dr.ellipse([(cx - rad) * S, (cy - rad) * S, (cx + rad) * S, (cy + rad) * S], outline=(90, 62, 18, a),
                   width=int(3 * S))
        dr.ellipse([(cx - rad + 2) * S, (cy - rad + 3) * S, (cx + rad + 2) * S, (cy + rad + 3) * S],
                   outline=(255, 240, 190, a // 2), width=int(1.5 * S))
    for i in range(36):
        a = 2 * math.pi * i / 36
        punto(dr, cx + (R - 68) * math.cos(a), cy + (R - 68) * math.sin(a), 3.2, (110, 78, 22), 200)
    obj.alpha_composite(rel)
    m = Image.new("L", (W, H), 0)
    est = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = 64 if i % 2 == 0 else 27
        est.append(((cx + rr * math.cos(a)) * S, (cy + rr * math.sin(a)) * S))
    sombra = capa()
    ImageDraw.Draw(sombra).polygon([(x + 4 * S, y + 6 * S) for x, y in est], fill=(70, 45, 10, 200))
    obj.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(3 * S)))
    ImageDraw.Draw(m).polygon(est, fill=255)
    obj.alpha_composite(_oro(m, 120))
    cerrar()


# ---------- motivos premium: protección de datos / filtraciones (2026-11-10) ----------

def _cilindro(obj, cx, ytop, rx, ry, alto):
    """Disco de vidrio (un nivel de base de datos) en vista 3/4."""
    c = capa()
    d = ImageDraw.Draw(c)
    d.rectangle([(cx - rx) * S, ytop * S, (cx + rx) * S, (ytop + alto) * S], fill=(200, 214, 250, 26))
    d.ellipse([(cx - rx) * S, (ytop + alto - ry) * S, (cx + rx) * S, (ytop + alto + ry) * S], fill=(200, 214, 250, 26))
    d.arc([(cx - rx) * S, (ytop + alto - ry) * S, (cx + rx) * S, (ytop + alto + ry) * S], 0, 180,
          fill=BLANCO + (150,), width=int(1.8 * S))
    for x in (cx - rx, cx + rx):
        d.line([(x * S, ytop * S), (x * S, (ytop + alto) * S)], fill=BLANCO + (130,), width=int(1.6 * S))
    d.ellipse([(cx - rx) * S, (ytop - ry) * S, (cx + rx) * S, (ytop + ry) * S], fill=(225, 234, 255, 48),
              outline=BLANCO + (210,), width=int(2 * S))
    band = capa()                                                    # brillo vertical
    ImageDraw.Draw(band).rectangle([(cx - rx * 0.55) * S, ytop * S, (cx - rx * 0.35) * S, (ytop + alto) * S],
                                   fill=(255, 255, 255, 34))
    c.alpha_composite(band.filter(ImageFilter.GaussianBlur(6 * S)))
    for i in range(3):                                               # luces de estado
        punto(d, cx + rx * 0.55 + i * 22, ytop + alto * 0.55, 5, BLANCO if i else DORADO, 220)
    obj.alpha_composite(c)


def filtracion(img, semilla):
    """Base de datos de vidrio con una fuga de partículas doradas (filtración de datos personales)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    cx = 470
    for k, yt in enumerate((1080, 860, 640)):
        _cilindro(obj, cx, yt, 250, 70, 150)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    dm.ellipse([(cx - 254) * S, (1010 - 74) * S, (cx + 254) * S, (1010 + 74) * S], outline=255, width=int(5 * S))
    for _ in range(140):                                             # bits que escapan hacia arriba a la derecha
        t = r.uniform(0, 1) ** 0.8
        x = cx + 230 + t * 420 + r.normal(0, 18 + 60 * t)
        y = 1000 - t * 560 + r.normal(0, 14 + 50 * t)
        lado = r.uniform(4, 13) * (1 - 0.5 * t)
        dm.rectangle([(x - lado) * S, (y - lado) * S, (x + lado) * S, (y + lado) * S], fill=int(255 * (1 - 0.7 * t)))
    obj.alpha_composite(_oro(m, 30))
    cerrar()


def incidente(img, semilla):
    """Panel de análisis de vidrio en perspectiva con un triángulo de alerta de oro (evaluar el incidente)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 700, 820
    p, d = _vidrio(w, h)
    d.rounded_rectangle([46 * S, 54 * S, 300 * S, 66 * S], radius=4 * S, fill=BLANCO + (190,))
    pts = [(60 + i * 58, 520 - 140 * math.sin(i * 0.7) * math.exp(-i * 0.05) - (180 if i == 8 else 0))
           for i in range(11)]
    d.line([(x * S, y * S) for x, y in pts], fill=(220, 230, 255, 200), width=int(3 * S), joint="curve")
    for x, y in pts:
        d.ellipse([(x - 6) * S, (y - 6) * S, (x + 6) * S, (y + 6) * S], fill=(230, 236, 255, 220))
    for i in range(6):
        hh = r.uniform(40, 150)
        d.rounded_rectangle([(70 + i * 100) * S, (760 - hh) * S, (120 + i * 100) * S, 760 * S], radius=6 * S,
                            fill=(210, 222, 255, 60), outline=BLANCO + (120,))
    quad = [(120, 420), (900, 480), (960, 1340), (80, 1300)]
    obj.alpha_composite(_proyectar(p, quad))
    f = _mapa(quad, w, h)
    ax, ay = f(*pts[8])
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    cx, cy, L = 650, 640, 300
    tri = [(cx, cy - L * 0.62), (cx + L * 0.58, cy + L * 0.38), (cx - L * 0.58, cy + L * 0.38)]
    dm.polygon([(x * S, y * S) for x, y in tri], fill=255)
    hueco = [(cx, cy - L * 0.42), (cx + L * 0.41, cy + L * 0.27), (cx - L * 0.41, cy + L * 0.27)]
    dm.polygon([(x * S, y * S) for x, y in hueco], fill=0)
    oro = _oro(m, 50)
    obj.alpha_composite(oro)
    v = capa()
    dv = ImageDraw.Draw(v)
    dv.polygon([(x * S, y * S) for x, y in hueco], fill=(20, 26, 50, 215))
    dv.rounded_rectangle([(cx - 13) * S, (cy - 70) * S, (cx + 13) * S, (cy + 30) * S], radius=10 * S, fill=DORADO + (255,))
    dv.ellipse([(cx - 15) * S, (cy + 50) * S, (cx + 15) * S, (cy + 80) * S], fill=DORADO + (255,))
    obj.alpha_composite(v)
    ImageDraw.Draw(obj).line([(ax * S, ay * S), ((cx - L * 0.3) * S, (cy + L * 0.3) * S)], fill=DORADO + (160,),
                             width=int(2 * S))
    punto(ImageDraw.Draw(obj), ax, ay, 12, DORADO, 255)
    cerrar()


def reporte(img, semilla):
    """Informe de vidrio que viaja por una trayectoria dorada hasta una institución (reportar a la Agencia)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    c = capa()                                                       # institución (columnas de vidrio)
    d = ImageDraw.Draw(c)
    bx, by, bw = 560, 520, 420
    d.polygon([((bx - 20) * S, by * S), ((bx + bw / 2) * S, (by - 130) * S), ((bx + bw + 20) * S, by * S)],
              fill=(214, 226, 255, 40), outline=BLANCO + (200,))
    for i in range(5):
        x = bx + 20 + i * (bw - 40) / 4
        d.rounded_rectangle([(x - 22) * S, (by + 30) * S, (x + 22) * S, (by + 360) * S], radius=6 * S,
                            fill=(214, 226, 255, 42), outline=BLANCO + (150,), width=int(1.4 * S))
    d.rectangle([(bx - 40) * S, (by + 360) * S, (bx + bw + 40) * S, (by + 392) * S], fill=(214, 226, 255, 46),
                outline=BLANCO + (180,))
    obj.alpha_composite(c)
    w, h = 360, 460
    p, dp = _vidrio(w, h)
    _texto(dp, w, 7, r, paso=40)
    quad = [(90, 900), (420, 860), (470, 1300), (110, 1340)]
    obj.alpha_composite(_proyectar(p, quad))
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    ruta = [(430 + t * 330, 900 - 330 * math.sin(t * math.pi * 0.62) - t * 60) for t in np.linspace(0, 1, 40)]
    for i, (x, y) in enumerate(ruta[:-3]):
        if i % 2 == 0:
            dm.ellipse([(x - 6) * S, (y - 6) * S, (x + 6) * S, (y + 6) * S], fill=255)
    x1, y1 = ruta[-1]
    x0, y0 = ruta[-4]
    a = math.atan2(y1 - y0, x1 - x0)
    punta = [(x1 + 34 * math.cos(a), y1 + 34 * math.sin(a)), (x1 + 26 * math.cos(a + 2.4), y1 + 26 * math.sin(a + 2.4)),
             (x1 + 26 * math.cos(a - 2.4), y1 + 26 * math.sin(a - 2.4))]
    dm.polygon([(x * S, y * S) for x, y in punta], fill=255)
    dm.line([((bx - 60) * S, (by + 420) * S), ((bx + bw + 60) * S, (by + 420) * S)], fill=255, width=int(3 * S))
    obj.alpha_composite(_oro(m, 30))
    cerrar()


def titulares(img, semilla):
    """Personas de vidrio conectadas a un nodo central de oro; algunas reciben un aviso (comunicar a titulares)."""
    obj, cerrar = _escena(img, semilla)
    cx, cy = 540, 860
    posiciones = []
    for k, (rad, n, esc) in enumerate(((300, 6, 1.0), (470, 9, 0.75))):
        for i in range(n):
            a = 2 * math.pi * i / n + k * 0.3
            posiciones.append((cx + rad * math.cos(a), cy + rad * math.sin(a) * 0.62, esc))
    lineas = capa()
    dl = ImageDraw.Draw(lineas)
    for x, y, e in posiciones:
        dl.line([(cx * S, cy * S), (x * S, y * S)], fill=(200, 215, 255, 60), width=int(1.4 * S))
    obj.alpha_composite(lineas)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    avisados = {0, 2, 4, 7, 11}
    for i, (x, y, e) in enumerate(sorted(posiciones, key=lambda q: q[1])):
        c = capa()
        d = ImageDraw.Draw(c)
        rr = 62 * e
        d.ellipse([(x - rr) * S, (y - rr) * S, (x + rr) * S, (y + rr) * S], fill=(210, 224, 255, 40),
                  outline=BLANCO + (190,), width=int(1.8 * S))
        d.ellipse([(x - rr * 0.28) * S, (y - rr * 0.55) * S, (x + rr * 0.28) * S, (y - rr * 0.0) * S],
                  fill=BLANCO + (200,))
        d.chord([(x - rr * 0.55) * S, (y + rr * 0.08) * S, (x + rr * 0.55) * S, (y + rr * 0.9) * S], 180, 360,
                fill=BLANCO + (200,))
        if e < 1:
            c = c.filter(ImageFilter.GaussianBlur(1.5 * S))
        obj.alpha_composite(c)
        if i in avisados:
            bx, by = x + rr * 0.72, y - rr * 0.72
            dm.ellipse([(bx - 17 * e) * S, (by - 17 * e) * S, (bx + 17 * e) * S, (by + 17 * e) * S], fill=255)
    dm.ellipse([(cx - 46) * S, (cy - 46) * S, (cx + 46) * S, (cy + 46) * S], fill=255)
    dm.ellipse([(cx - 80) * S, (cy - 80) * S, (cx + 80) * S, (cy + 80) * S], outline=255, width=int(4 * S))
    obj.alpha_composite(_oro(m, 30))
    v = capa()
    ImageDraw.Draw(v).rounded_rectangle([(cx - 26) * S, (cy - 16) * S, (cx + 26) * S, (cy + 20) * S], radius=5 * S,
                                        outline=(40, 30, 10, 220), width=int(4 * S))
    ImageDraw.Draw(v).line([((cx - 24) * S, (cy - 14) * S), (cx * S, (cy + 4) * S), ((cx + 24) * S, (cy - 14) * S)],
                           fill=(40, 30, 10, 220), width=int(4 * S))
    obj.alpha_composite(v)
    cerrar()


def escudo_premium(img, semilla):
    """Escudo de vidrio con aro y candado de oro sobre anillos de datos en perspectiva (estar preparados)."""
    obj, cerrar = _escena(img, semilla)
    cx, cy = 540, 820
    an = capa()
    d = ImageDraw.Draw(an)
    for k, rad in enumerate((330, 420, 510)):
        for i in range(60 + k * 20):
            a = 2 * math.pi * i / (60 + k * 20)
            punto(d, cx + rad * math.cos(a), cy + 300 + rad * 0.28 * math.sin(a), 2.6, DORADO if i % 9 == 0 else BLANCO,
                  170 - k * 40)
    obj.alpha_composite(an)
    sh = [(cx, cy - 300), (cx + 240, cy - 205), (cx + 215, cy + 115), (cx, cy + 310), (cx - 215, cy + 115),
          (cx - 240, cy - 205)]
    bb = (cx - 260, cy - 320, cx + 260, cy + 330)
    pw, ph = bb[2] - bb[0], bb[3] - bb[1]
    p, _ = _vidrio(pw, ph, radio=1, alfa=(70, 26))
    mk = Image.new("L", p.size, 0)
    ImageDraw.Draw(mk).polygon([((x - bb[0]) * S, (y - bb[1]) * S) for x, y in sh], fill=255)
    p.putalpha(ImageChops.multiply(p.split()[3], mk))
    obj.alpha_composite(p, (bb[0] * S, bb[1] * S))
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    dm.line([(x * S, y * S) for x, y in sh + [sh[0]]], fill=255, width=int(10 * S), joint="curve")
    dm.rounded_rectangle([(cx - 82) * S, (cy - 20) * S, (cx + 82) * S, (cy + 112) * S], radius=18 * S, fill=255)
    dm.arc([(cx - 56) * S, (cy - 116) * S, (cx + 56) * S, (cy + 4) * S], 180, 360, fill=255, width=int(16 * S))
    for x in (cx - 56, cx + 56):
        dm.line([(x * S, (cy - 58) * S), (x * S, (cy - 16) * S)], fill=255, width=int(16 * S))
    obj.alpha_composite(_oro(m, 40))
    v = capa()
    dv = ImageDraw.Draw(v)
    dv.ellipse([(cx - 15) * S, (cy + 22) * S, (cx + 15) * S, (cy + 52) * S], fill=(40, 28, 8, 230))
    dv.rectangle([(cx - 6) * S, (cy + 44) * S, (cx + 6) * S, (cy + 82) * S], fill=(40, 28, 8, 230))
    obj.alpha_composite(v)
    cerrar()


def _persona(obj, x, y, e, alfa=190, oro=None):
    """Silueta de persona de vidrio (cabeza y hombros) dentro de un círculo; oro: máscara L opcional."""
    c = capa()
    d = ImageDraw.Draw(c)
    rr = 62 * e
    d.ellipse([(x - rr) * S, (y - rr) * S, (x + rr) * S, (y + rr) * S], fill=(210, 224, 255, 40),
              outline=BLANCO + (alfa,), width=int(1.8 * S))
    d.ellipse([(x - rr * 0.28) * S, (y - rr * 0.55) * S, (x + rr * 0.28) * S, y * S], fill=BLANCO + (alfa,))
    d.chord([(x - rr * 0.55) * S, (y + rr * 0.08) * S, (x + rr * 0.55) * S, (y + rr * 0.9) * S], 180, 360,
            fill=BLANCO + (alfa,))
    if e < 0.9:
        c = c.filter(ImageFilter.GaussianBlur(1.2 * S))
    obj.alpha_composite(c)


def _candado(dm, cx, cy, k=1.0, abierto=False):
    """Candado (en una máscara L) centrado en cx, cy."""
    dm.rounded_rectangle([(cx - 40 * k) * S, (cy - 8 * k) * S, (cx + 40 * k) * S, (cy + 56 * k) * S], radius=9 * k * S,
                         fill=255)
    dx = 30 * k if abierto else 0
    dm.arc([(cx - 27 * k + dx) * S, (cy - 58 * k) * S, (cx + 27 * k + dx) * S, (cy + 2 * k) * S], 180, 360, fill=255,
           width=int(8 * k * S))
    dm.line([((cx - 27 * k + dx) * S, (cy - 28 * k) * S), ((cx - 27 * k + dx) * S, (cy - 10 * k) * S)], fill=255,
            width=int(8 * k * S))
    if not abierto:
        dm.line([((cx + 27 * k) * S, (cy - 28 * k) * S), ((cx + 27 * k) * S, (cy - 10 * k) * S)], fill=255,
                width=int(8 * k * S))


def acceso(img, semilla):
    """Puerta de vidrio con cerradura de oro y personas que se acercan por caminos de luz (quién accede a los datos)."""
    obj, cerrar = _escena(img, semilla)
    w, h = 420, 760
    p, d = _vidrio(w, h, radio=30, alfa=(74, 24))
    for i in range(3):                                               # filas de datos dentro de la puerta
        _cy = 470 + i * 70
        d.rounded_rectangle([60 * S, _cy * S, (w - 60) * S, (_cy + 10) * S], radius=4 * S, fill=BLANCO + (60,))
    quad = [(360, 560), (760, 600), (760, 1400), (360, 1420)]
    obj.alpha_composite(_proyectar(p, quad))
    caminos = capa()
    dl = ImageDraw.Draw(caminos)
    gente = [(150, 980, 0.85), (230, 1250, 1.0), (900, 900, 0.75), (930, 1210, 0.95), (120, 700, 0.6)]
    for x, y, e in gente:
        for t in np.linspace(0, 1, 26)[::2]:
            px, py = x + (560 - x) * t, y + (1010 - y) * t
            punto(dl, px, py, 2.4, BLANCO, int(150 * (1 - t) + 40))
    obj.alpha_composite(caminos)
    for x, y, e in gente:
        _persona(obj, x, y, e)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    cx, cy = 560, 900
    dm.ellipse([(cx - 70) * S, (cy - 70) * S, (cx + 70) * S, (cy + 70) * S], fill=255)
    dm.ellipse([(cx - 96) * S, (cy - 96) * S, (cx + 96) * S, (cy + 96) * S], outline=255, width=int(5 * S))
    dm.rounded_rectangle([(710) * S, (980) * S, (742) * S, (1080) * S], radius=12 * S, fill=255)   # manilla
    obj.alpha_composite(_oro(m, 40))
    v = capa()
    dv = ImageDraw.Draw(v)
    dv.ellipse([(cx - 20) * S, (cy - 34) * S, (cx + 20) * S, (cy + 6) * S], fill=(36, 26, 8, 235))
    dv.polygon([((cx - 13) * S, (cy - 6) * S), ((cx + 13) * S, (cy - 6) * S), ((cx + 22) * S, (cy + 44) * S),
                ((cx - 22) * S, (cy + 44) * S)], fill=(36, 26, 8, 235))
    obj.alpha_composite(v)
    cerrar()


def niveles(img, semilla):
    """Tres capas de vidrio escalonadas (niveles de acceso): cada una con su candado, solo la superior en oro."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for k, (y, ancho) in enumerate(((1120, 760), (880, 620), (650, 480))):
        w, h = ancho, 300
        p, d = _vidrio(w, h, radio=26, alfa=(70 - k * 4, 22))
        _texto(d, w, 3, r, y0=150, paso=48, oro=(0 if k == 2 else None))
        x0 = 540 - ancho / 2
        quad = [(x0 + 60, y), (x0 + ancho - 60, y), (x0 + ancho, y + 190), (x0, y + 190)]
        obj.alpha_composite(_proyectar(p, quad))
        lx = x0 + ancho - 70
        if k == 2:
            _candado(dm, lx - 10, y + 80, 0.9)
        else:                                                       # candados de vidrio en los niveles bajos
            cand = Image.new("L", (W, H), 0)
            _candado(ImageDraw.Draw(cand), lx - 10, y + 80, 0.75)
            capa_c = Image.new("RGBA", (W, H), BLANCO + (0,))
            capa_c.putalpha(cand.point(lambda v: int(v * 0.6)))
            obj.alpha_composite(capa_c)
    for t in np.linspace(0, 1, 22):                                   # eje dorado que une los niveles
        y = 1320 - t * 760
        dm.ellipse([(536) * S, (y - 4) * S, (544) * S, (y + 4) * S], fill=int(120 + 135 * t))
    obj.alpha_composite(_oro(m, 35))
    cerrar()


def roles(img, semilla):
    """Organigrama de vidrio arriba: un responsable de oro y tres funciones, cada una con su llave (deja libre el texto)."""
    obj, cerrar = _escena(img, semilla)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    raiz = (540, 400)
    hijos = [(230, 720), (540, 740), (850, 720)]
    nietos = []
    lin = capa()
    dl = ImageDraw.Draw(lin)
    for hx, hy in hijos:
        dm.line([(raiz[0] * S, (raiz[1] + 110) * S), (raiz[0] * S, 590 * S), (hx * S, 590 * S), (hx * S, (hy - 90) * S)],
                fill=200, width=int(4 * S), joint="curve")
    for i, (nx, ny) in enumerate(nietos):
        hx, hy = hijos[min(2, i * 3 // 5)]
        dl.line([(hx * S, (hy + 90) * S), (hx * S, (hy + 150) * S), (nx * S, (hy + 150) * S), (nx * S, (ny - 70) * S)],
                fill=(210, 222, 255, 110), width=int(2 * S))
    obj.alpha_composite(lin)
    for (x, y), (w, h) in [((hx, hy), (230, 180)) for hx, hy in hijos] + [((nx, ny), (150, 130)) for nx, ny in nietos]:
        p, d = _vidrio(w, h, radio=18)
        d.ellipse([(w / 2 - 22) * S, 26 * S, (w / 2 + 22) * S, 70 * S], fill=BLANCO + (200,))
        d.chord([(w / 2 - 40) * S, 76 * S, (w / 2 + 40) * S, 136 * S], 180, 360, fill=BLANCO + (200,))
        if h > 150:
            d.rounded_rectangle([40 * S, 150 * S, (w - 40) * S, 160 * S], radius=4 * S, fill=BLANCO + (70,))
        obj.alpha_composite(p, (int((x - w / 2) * S), int((y - h / 2) * S)))
    for hx, hy in hijos:                                             # llave de acceso de cada función
        kx, ky = hx + 92, hy - 70
        dm.ellipse([(kx - 18) * S, (ky - 18) * S, (kx + 18) * S, (ky + 18) * S], outline=255, width=int(6 * S))
        dm.line([((kx + 14) * S, (ky + 14) * S), ((kx + 46) * S, (ky + 46) * S)], fill=255, width=int(6 * S))
        dm.line([((kx + 34) * S, (ky + 34) * S), ((kx + 44) * S, (ky + 24) * S)], fill=255, width=int(6 * S))
    x, y = raiz
    dm.ellipse([(x - 110) * S, (y - 110) * S, (x + 110) * S, (y + 110) * S], outline=255, width=int(6 * S))
    dm.ellipse([(x - 34) * S, (y - 62) * S, (x + 34) * S, (y + 6) * S], fill=255)
    dm.chord([(x - 66) * S, (y + 10) * S, (x + 66) * S, (y + 100) * S], 180, 360, fill=255)
    obj.alpha_composite(_oro(m, 30))
    cerrar()


def conservar(img, semilla):
    """Archivo de vidrio con cajones de datos y un reloj de arena de oro (cuánto tiempo se conservan)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 460, 800
    p, d = _vidrio(w, h, radio=24, alfa=(66, 22))
    for i in range(4):
        y0 = 40 + i * 190
        d.rounded_rectangle([30 * S, y0 * S, (w - 30) * S, (y0 + 165) * S], radius=14 * S, fill=(214, 226, 255, 22),
                            outline=BLANCO + (150,), width=int(1.6 * S))
        d.rounded_rectangle([(w / 2 - 50) * S, (y0 + 70) * S, (w / 2 + 50) * S, (y0 + 86) * S], radius=8 * S,
                            fill=BLANCO + (170,))
        for k in range(int(r.integers(3, 6))):
            d.rounded_rectangle([60 * S, (y0 + 24 + k * 0) * S, (60 + 60 + k * 50) * S, (y0 + 30) * S], radius=3 * S,
                                fill=BLANCO + (40,))
    quad = [(110, 560), (530, 600), (530, 1410), (110, 1420)]
    obj.alpha_composite(_proyectar(p, quad))
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    cx, top, bot = 780, 640, 1240
    dm.rounded_rectangle([(cx - 150) * S, (top - 30) * S, (cx + 150) * S, top * S], radius=10 * S, fill=255)
    dm.rounded_rectangle([(cx - 150) * S, bot * S, (cx + 150) * S, (bot + 30) * S], radius=10 * S, fill=255)
    for x in (cx - 128, cx + 128):
        dm.line([(x * S, top * S), (x * S, bot * S)], fill=255, width=int(9 * S))
    vidrio = capa()
    dv = ImageDraw.Draw(vidrio)
    mid = (top + bot) / 2
    forma = [(cx - 110, top + 10), (cx + 110, top + 10), (cx + 14, mid), (cx + 110, bot - 10), (cx - 110, bot - 10),
             (cx - 14, mid)]
    dv.polygon([(x * S, y * S) for x, y in forma], fill=(214, 226, 255, 46), outline=BLANCO + (210,))
    obj.alpha_composite(vidrio)
    dm.polygon([((cx - 70) * S, (top + 60) * S), ((cx + 70) * S, (top + 60) * S), ((cx + 8) * S, (mid - 6) * S),
                ((cx - 8) * S, (mid - 6) * S)], fill=255)
    dm.polygon([((cx - 100) * S, (bot - 12) * S), ((cx + 100) * S, (bot - 12) * S), (cx * S, (bot - 120) * S)], fill=255)
    dm.line([(cx * S, mid * S), (cx * S, (bot - 120) * S)], fill=200, width=int(3 * S))
    for k in range(18):                                              # datos que pasan del archivo al reloj
        t = k / 17
        x = 540 + t * 100
        y = 980 - math.sin(t * math.pi) * 60
        dm.rectangle([(x - 5) * S, (y - 5) * S, (x + 5) * S, (y + 5) * S], fill=int(80 + 160 * t))
    obj.alpha_composite(_oro(m, 35))
    cerrar()


def preparada(img, semilla):
    """Lista de verificación de vidrio con tres controles en oro y un escudo pequeño (empresa preparada)."""
    r = np.random.default_rng(semilla)
    obj, cerrar = _escena(img, semilla)
    w, h = 620, 780
    p, d = _vidrio(w, h, radio=30, alfa=(72, 24))
    d.rounded_rectangle([60 * S, 70 * S, 330 * S, 84 * S], radius=5 * S, fill=BLANCO + (200,))
    filas = []
    for i in range(3):
        y = 200 + i * 170
        d.rounded_rectangle([60 * S, (y - 40) * S, (w - 60) * S, (y + 90) * S], radius=18 * S, fill=(214, 226, 255, 20),
                            outline=BLANCO + (120,), width=int(1.4 * S))
        d.rounded_rectangle([170 * S, (y + 4) * S, (int(r.uniform(420, 520))) * S, (y + 16) * S], radius=5 * S,
                            fill=BLANCO + (110,))
        d.rounded_rectangle([170 * S, (y + 40) * S, (int(r.uniform(300, 420))) * S, (y + 50) * S], radius=5 * S,
                            fill=BLANCO + (55,))
        filas.append(y)
    quad = [(230, 520), (850, 560), (880, 1380), (200, 1400)]
    obj.alpha_composite(_proyectar(p, quad))
    f = _mapa(quad, w, h)
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for y in filas:
        cx, cy = f(105, y + 25)
        dm.ellipse([(cx - 36) * S, (cy - 36) * S, (cx + 36) * S, (cy + 36) * S], fill=255)
    obj.alpha_composite(_oro(m, 35))
    v = capa()
    dv = ImageDraw.Draw(v)
    for y in filas:
        cx, cy = f(105, y + 25)
        dv.line([((cx - 16) * S, cy * S), ((cx - 4) * S, (cy + 13) * S), ((cx + 18) * S, (cy - 14) * S)],
                fill=(36, 26, 8, 240), width=int(6 * S), joint="curve")
    obj.alpha_composite(v)
    m2 = Image.new("L", (W, H), 0)
    d2 = ImageDraw.Draw(m2)
    sx, sy = 860, 470
    sh = [(sx, sy - 110), (sx + 90, sy - 75), (sx + 80, sy + 40), (sx, sy + 115), (sx - 80, sy + 40), (sx - 90, sy - 75)]
    d2.polygon([(x * S, y * S) for x, y in sh], fill=255)
    obj.alpha_composite(_oro(m2, 50))
    _candado_v = capa()
    _candado(ImageDraw.Draw(_candado_v), sx, sy + 5, 0.55)
    arr = np.asarray(_candado_v).copy()
    arr[..., :3] = (36, 26, 8)
    obj.alpha_composite(Image.fromarray(arr))
    cerrar()

AZULF = (50, 66, 120)
CALIDO = (120, 95, 50)
FONDOS = [
    ("red-global-1.jpg", globo, 1, [(0.75, 0.25, 0.55, AZULF, 0.9), (0.2, 0.8, 0.4, CALIDO, 0.25)],
     "Globo de puntos con arcos de conexión desde un origen dorado (internacionalización, expansión, clientes extranjeros)"),
    ("red-global-2.jpg", globo, 7, [(0.25, 0.3, 0.55, AZULF, 0.9), (0.85, 0.75, 0.35, CALIDO, 0.2)],
     "Red de ciudades conectadas sobre un globo, punto dorado de origen (operar en otro país, contratos internacionales)"),
    ("documentos-1.jpg", documentos, 2, [(0.7, 0.3, 0.5, AZULF, 0.85), (0.2, 0.75, 0.35, CALIDO, 0.2)],
     "Hojas de contrato de vidrio en profundidad con líneas de texto (contratos, bases de licitación, documentos)"),
    ("documentos-2.jpg", documentos, 9, [(0.3, 0.25, 0.5, AZULF, 0.85), (0.8, 0.7, 0.35, CALIDO, 0.2)],
     "Documentos legales en perspectiva con firma dorada (revisión de contratos, cumplimiento, políticas)"),
    ("columnas.jpg", columnas, 3, [(0.5, 0.15, 0.5, AZULF, 1.0), (0.5, 0.85, 0.4, CALIDO, 0.15)],
     "Fachada clásica de un edificio judicial en líneas finas con luz cenital (derecho, Estado, compras públicas)"),
    ("datos-escudo.jpg", escudo, 4, [(0.5, 0.4, 0.45, AZULF, 0.9), (0.15, 0.85, 0.3, CALIDO, 0.15)],
     "Escudo con candado dorado y anillos de datos (protección de datos personales, Ley 21.719, seguridad)"),
    ("cuadricula-crecimiento.jpg", crecimiento, 5, [(0.8, 0.2, 0.5, AZULF, 0.9), (0.3, 0.6, 0.35, CALIDO, 0.15)],
     "Cuadrícula en perspectiva con barras de vidrio y línea dorada ascendente (empresas, crecimiento, decisiones)"),
    ("balanza.jpg", balanza, 6, [(0.5, 0.22, 0.5, AZULF, 0.9), (0.5, 0.8, 0.35, CALIDO, 0.15)],
     "Balanza de la justicia en línea fina con eje dorado (conflictos, controversias, resolución de disputas)"),
    ("lupa-bases.jpg", lupa, 11, [(0.7, 0.3, 0.5, AZULF, 0.9), (0.25, 0.8, 0.35, CALIDO, 0.2)],
     "Lupa sobre las bases que revela una línea dorada (revisar una licitación, sospecha de irregularidad, auditoría)"),
    ("comparar-documentos.jpg", comparar, 12, [(0.5, 0.2, 0.55, AZULF, 0.9), (0.8, 0.8, 0.3, CALIDO, 0.2)],
     "Dos documentos lado a lado con guías y una diferencia marcada en dorado (comparar bases con lo ocurrido, requisitos)"),
    ("carpeta-antecedentes.jpg", carpeta, 13, [(0.3, 0.25, 0.5, AZULF, 0.9), (0.75, 0.8, 0.35, CALIDO, 0.2)],
     "Carpeta con documentos y pestaña dorada (conservar antecedentes, respaldos, expediente)"),
    ("reloj-plazos.jpg", reloj, 14, [(0.5, 0.35, 0.5, AZULF, 0.9), (0.2, 0.85, 0.3, CALIDO, 0.2)],
     "Reloj en línea fina con arco dorado que avanza (plazos, actuar a tiempo, vencimientos)"),
    ("sello-resolucion.jpg", sello, 15, [(0.75, 0.25, 0.5, AZULF, 0.9), (0.3, 0.75, 0.35, CALIDO, 0.2)],
     "Resolución con sello dorado (adjudicación, decisión de la autoridad, acto administrativo)"),
    ("filtracion-datos.jpg", filtracion, 16, [(0.7, 0.3, 0.5, AZULF, 0.9), (0.25, 0.8, 0.35, CALIDO, 0.2)],
     "Base de datos de vidrio con fuga de partículas doradas (filtración, vulneración de datos personales, Ley 21.719)"),
    ("evaluar-incidente.jpg", incidente, 17, [(0.4, 0.25, 0.55, AZULF, 0.9), (0.8, 0.8, 0.3, CALIDO, 0.2)],
     "Panel de análisis con triángulo de alerta de oro (evaluar un incidente, riesgos, auditoría)"),
    ("reporte-agencia.jpg", reporte, 18, [(0.65, 0.2, 0.5, AZULF, 0.9), (0.2, 0.75, 0.35, CALIDO, 0.2)],
     "Informe que viaja por una ruta dorada hasta una institución (reportar a la Agencia, autoridad, fiscalización)"),
    ("notificar-titulares.jpg", titulares, 19, [(0.5, 0.3, 0.55, AZULF, 0.9), (0.5, 0.85, 0.3, CALIDO, 0.2)],
     "Personas conectadas a un nodo de oro, algunas con aviso (comunicar a titulares, clientes, trabajadores)"),
    ("escudo-protocolo.jpg", escudo_premium, 20, [(0.5, 0.3, 0.5, AZULF, 0.95), (0.3, 0.85, 0.3, CALIDO, 0.2)],
     "Escudo de vidrio con candado de oro sobre anillos de datos (seguridad, protocolos, cumplimiento)"),
    ("acceso-datos.jpg", acceso, 21, [(0.55, 0.3, 0.55, AZULF, 0.9), (0.2, 0.85, 0.3, CALIDO, 0.2)],
     "Puerta de vidrio con cerradura de oro y personas que se acercan (quién accede a los datos, control de accesos)"),
    ("niveles-acceso.jpg", niveles, 22, [(0.5, 0.25, 0.55, AZULF, 0.9), (0.8, 0.85, 0.3, CALIDO, 0.2)],
     "Tres capas de vidrio escalonadas con candados, la superior en oro (niveles de acceso, permisos, información sensible)"),
    ("roles-responsables.jpg", roles, 23, [(0.5, 0.2, 0.55, AZULF, 0.9), (0.25, 0.85, 0.3, CALIDO, 0.2)],
     "Organigrama de vidrio con un responsable de oro y llaves por función (responsabilidades internas, permisos por cargo)"),
    ("conservar-datos.jpg", conservar, 24, [(0.35, 0.3, 0.55, AZULF, 0.9), (0.8, 0.8, 0.3, CALIDO, 0.2)],
     "Archivo de vidrio con cajones y un reloj de arena de oro (conservación de datos, plazos, retención)"),
    ("empresa-preparada.jpg", preparada, 25, [(0.5, 0.3, 0.55, AZULF, 0.95), (0.3, 0.85, 0.3, CALIDO, 0.2)],
     "Lista de verificación de vidrio con controles de oro y escudo (empresa preparada, cumplimiento, Ley 21.719)"),
]


def main():
    DIR.mkdir(exist_ok=True)
    meta = []
    grano = np.random.default_rng(0).normal(0, 2.0, (1920, 1080, 1))
    for archivo, fn, semilla, luces, desc in FONDOS:
        img = base(luces, semilla)
        fn(img, semilla)
        final = img.convert("RGB").resize((1080, 1920), Image.LANCZOS)
        arr = np.clip(np.asarray(final, np.float32) + grano, 0, 255).astype(np.uint8)
        Image.fromarray(arr).save(DIR / archivo, quality=95)
        meta.append({"archivo": archivo, "descripcion": desc, "orientacion": "vertical"})
    (DIR / "fotos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(meta)} fondos en {DIR}")


if __name__ == "__main__":
    main()
