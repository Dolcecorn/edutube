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
