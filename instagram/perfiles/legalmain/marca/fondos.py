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


def _hoja(d, x0, y0, w, h, r, n=12, alfa=12, paso=44, resaltar=None):
    """Hoja de vidrio con líneas de texto; resaltar = índice de una línea que va en dorado."""
    d.rounded_rectangle([x0 * S, y0 * S, (x0 + w) * S, (y0 + h) * S], radius=16 * S,
                        fill=(200, 212, 245, alfa), outline=BLANCO + (110,), width=int(1.5 * S))
    d.rectangle([(x0 + 44) * S, (y0 + 56) * S, (x0 + 44 + w * 0.4) * S, (y0 + 66) * S], fill=BLANCO + (120,))
    filas = []
    for i in range(n):
        ly = y0 + 116 + i * paso
        if ly + 10 > y0 + h - 40:
            break
        largo = w - 100 - int(r.uniform(0, w * 0.3))
        col, a = (DORADO, 230) if i == resaltar else (BLANCO, 45)
        d.rounded_rectangle([(x0 + 44) * S, ly * S, (x0 + 44 + largo) * S, (ly + 7) * S], radius=3 * S, fill=col + (a,))
        filas.append((ly, largo))
    return filas


def lupa(img, semilla):
    """Hoja de bases con una lupa de vidrio que revela una línea dorada (revisar, detectar irregularidades)."""
    r = np.random.default_rng(semilla)
    c = capa()
    d = ImageDraw.Draw(c)
    _hoja(d, 170, 380, 620, 900, r, n=17, alfa=14)
    c = c.rotate(-6, resample=Image.BICUBIC, center=(W / 2, H / 2))
    con_brillo(img, c, glow=8, fuerza=0.3, desenfoque=2)
    cx, cy, R = 600, 860, 200
    l = capa()
    d = ImageDraw.Draw(l)
    d.ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], fill=(210, 222, 250, 30))
    for i in range(5):                                  # texto ampliado dentro del lente
        ly = cy - 120 + i * 58
        mitad = math.sqrt(max(0, R * R - (ly - cy) ** 2)) - 30
        col, a = (DORADO, 245) if i == 2 else (BLANCO, 90)
        d.rounded_rectangle([(cx - mitad) * S, ly * S, (cx + mitad * (0.9 if i == 2 else 0.6)) * S, (ly + 14) * S],
                            radius=6 * S, fill=col + (a,))
    d.ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], outline=BLANCO + (220,), width=int(5 * S))
    d.ellipse([(cx - R + 16) * S, (cy - R + 16) * S, (cx + R - 16) * S, (cy + R - 16) * S], outline=BLANCO + (50,),
              width=int(1.2 * S))
    a = math.radians(45)
    x1, y1 = cx + R * math.cos(a), cy + R * math.sin(a)
    linea(d, [(x1 + 8, y1 + 8), (x1 + 190, y1 + 190)], DORADO, 255, 16)
    d.arc([(cx - R + 30) * S, (cy - R + 30) * S, (cx + R - 30) * S, (cy + R - 30) * S], 200, 250,
          fill=BLANCO + (160,), width=int(3 * S))
    con_brillo(img, l, glow=12, fuerza=0.55)


def comparar(img, semilla):
    """Dos hojas lado a lado unidas por guías: bases vs. lo ocurrido; una diferencia marcada en dorado."""
    r = np.random.default_rng(semilla)
    c = capa()
    d = ImageDraw.Draw(c)
    f1 = _hoja(d, 110, 480, 400, 820, r, n=14, alfa=16)
    f2 = _hoja(d, 570, 480, 400, 820, r, n=14, alfa=16, resaltar=6)
    for i, (ly, largo) in enumerate(f1):
        if i % 2 == 0 or i == 6:
            col, a = (DORADO, 230) if i == 6 else (BLANCO, 70)
            for x in range(110 + 44 + largo + 12, 570 + 30, 18):   # guía punteada entre hojas
                linea(d, [(x, ly + 3), (x + 8, ly + 3)], col, a, 1.4)
    for i in (1, 3, 9, 11):                              # visto bueno en filas que coinciden
        ly = f2[i][0]
        linea(d, [(930, ly + 2), (942, ly + 14), (962, ly - 10)], BLANCO, 170, 2.2)
    ly = f2[6][0]
    d.ellipse([(946 - 16) * S, (ly + 3 - 16) * S, (946 + 16) * S, (ly + 3 + 16) * S], outline=DORADO + (255,),
              width=int(3 * S))
    con_brillo(img, c, glow=8, fuerza=0.45)


def carpeta(img, semilla):
    """Carpeta de antecedentes con hojas asomando en profundidad y pestaña dorada (conservar documentos)."""
    r = np.random.default_rng(semilla)
    for k, (dx, dy, desen) in enumerate([(-40, -150, 4), (10, -110, 2), (60, -70, 0)]):
        c = capa()
        d = ImageDraw.Draw(c)
        _hoja(d, 230 + dx, 560 + dy, 560, 700, r, n=11, alfa=14 + 5 * k)
        con_brillo(img, c, glow=6, fuerza=0.3, desenfoque=desen)
    c = capa()
    d = ImageDraw.Draw(c)
    x0, y0, x1, y1 = 170, 860, 910, 1360
    d.polygon([(x0 * S, y0 * S), ((x0 + 230) * S, y0 * S), ((x0 + 270) * S, (y0 - 50) * S),
               ((x0 + 470) * S, (y0 - 50) * S), ((x0 + 500) * S, y0 * S), (x1 * S, y0 * S), (x1 * S, y1 * S),
               (x0 * S, y1 * S)], fill=(34, 42, 78, 235), outline=BLANCO + (190,))
    d.rounded_rectangle([(x0 + 290) * S, (y0 - 34) * S, (x0 + 450) * S, (y0 - 14) * S], radius=6 * S,
                        fill=DORADO + (235,))
    linea(d, [(x0 + 40, y0 + 60), (x1 - 40, y0 + 60)], BLANCO, 60, 1.2)
    for i in range(3):
        linea(d, [(x0 + 70, y0 + 150 + i * 70), (x0 + 70 + [420, 340, 260][i], y0 + 150 + i * 70)], BLANCO, 70, 3)
    linea(d, [(x0 - 60, y1 + 40), (x1 + 60, y1 + 40)], DORADO, 200, 2)
    con_brillo(img, c, glow=10, fuerza=0.6)


def reloj(img, semilla):
    """Reloj en línea fina con un arco dorado que avanza (plazos, actuar a tiempo)."""
    cx, cy, R = 540, 860, 340
    g = capa()
    d = ImageDraw.Draw(g)
    for k, rad in enumerate((R + 70, R + 130)):
        for i in range(90):
            a = 2 * math.pi * i / 90 + k * 0.03
            punto(d, cx + rad * math.cos(a), cy + rad * math.sin(a), 2.2, BLANCO, 70 - k * 25)
    con_brillo(img, g, glow=4, fuerza=0.4, desenfoque=1)
    c = capa()
    d = ImageDraw.Draw(c)
    d.ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], fill=(200, 212, 245, 14),
              outline=BLANCO + (200,), width=int(2.4 * S))
    for i in range(60):
        a = 2 * math.pi * i / 60 - math.pi / 2
        l0 = R - (40 if i % 5 == 0 else 20)
        linea(d, [(cx + l0 * math.cos(a), cy + l0 * math.sin(a)), (cx + (R - 8) * math.cos(a), cy + (R - 8) * math.sin(a))],
              BLANCO, 190 if i % 5 == 0 else 80, 2.2 if i % 5 == 0 else 1.2)
    d.arc([(cx - R - 26) * S, (cy - R - 26) * S, (cx + R + 26) * S, (cy + R + 26) * S], -90, 160,
          fill=DORADO + (255,), width=int(5 * S))
    a = math.radians(160)
    punto(d, cx + (R + 26) * math.cos(a), cy + (R + 26) * math.sin(a), 11, DORADO, 255)
    for ang, largo, ancho in ((-90 + 300, R * 0.52, 6), (-90 + 160 + 90, R * 0.78, 3.5)):
        a = math.radians(ang)
        linea(d, [(cx, cy), (cx + largo * math.cos(a), cy + largo * math.sin(a))], BLANCO, 230, ancho)
    punto(d, cx, cy, 14, DORADO, 255)
    con_brillo(img, c, glow=10, fuerza=0.6)


def sello(img, semilla):
    """Resolución con sello circular dorado en relieve (adjudicación, decisión de la autoridad)."""
    r = np.random.default_rng(semilla)
    c = capa()
    d = ImageDraw.Draw(c)
    _hoja(d, 200, 360, 680, 960, r, n=15, alfa=14)
    c = c.rotate(4, resample=Image.BICUBIC, center=(W / 2, H / 2))
    con_brillo(img, c, glow=8, fuerza=0.3, desenfoque=3)
    cx, cy = 640, 1080
    s = capa()
    d = ImageDraw.Draw(s)
    for rad, wd, a in ((190, 5, 255), (166, 1.6, 200), (110, 1.6, 160)):
        d.ellipse([(cx - rad) * S, (cy - rad) * S, (cx + rad) * S, (cy + rad) * S], outline=DORADO + (a,),
                  width=int(wd * S))
    for i in range(48):
        a = 2 * math.pi * i / 48
        punto(d, cx + 138 * math.cos(a), cy + 138 * math.sin(a), 3, DORADO, 200)
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = 70 if i % 2 == 0 else 30
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon([(x * S, y * S) for x, y in pts], fill=DORADO + (230,))
    con_brillo(img, s, glow=12, fuerza=0.55)


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
