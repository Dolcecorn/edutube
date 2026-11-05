"""Genera los fondos abstractos de LegalMain (azul #171b30, grises y un acento dorado sutil).

LegalMain no tiene banco de fotos propio: estos fondos cumplen ese rol (fotos/ + fotos.json) y siguen la
línea gráfica de su feed: azul marino profundo, líneas finas, mapas de conexiones, documentos y columnas.
Uso: python3 instagram/perfiles/legalmain/marca/fondos.py
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
AZUL = np.array([23, 27, 48], float)       # #171b30
AZUL_CLARO = np.array([44, 52, 88], float)
DORADO = (201, 164, 76)
GRIS = (150, 158, 178)
DIR = Path(__file__).resolve().parent / "fotos"


def base(cx=0.75, cy=0.25, radio=0.9):
    """Degradado radial: luz suave azul en (cx, cy) sobre el azul de la marca."""
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x / W - cx) * 1.0) ** 2 + ((y / H - cy) * 0.56) ** 2) / radio
    t = np.clip(1 - d, 0, 1) ** 1.6
    img = AZUL[None, None, :] * (1 - t[..., None]) + AZUL_CLARO[None, None, :] * t[..., None]
    ruido = np.random.default_rng(3).normal(0, 1.4, (H, W, 1))   # grano muy leve, evita bandas
    return Image.fromarray(np.clip(img + ruido, 0, 255).astype(np.uint8)).convert("RGBA")


def capa():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def pegar(img, c, desenfoque=0):
    if desenfoque:
        c = c.filter(ImageFilter.GaussianBlur(desenfoque))
    img.alpha_composite(c)


def red_global(img, semilla):
    """Mapa de conexiones: puntos de ciudades unidos por arcos (internacionalización)."""
    r = np.random.default_rng(semilla)
    c = capa()
    d = ImageDraw.Draw(c)
    # malla de puntos tenue (sugiere un mapa)
    for yy in range(300, 1300, 22):
        for xx in range(40, W - 40, 22):
            v = math.sin(xx / 140 + semilla) * math.cos(yy / 170) + r.normal(0, 0.35)
            if v > 0.35:
                d.ellipse([xx - 2, yy - 2, xx + 2, yy + 2], fill=GRIS + (55,))
    nodos = [(int(r.uniform(120, W - 120)), int(r.uniform(380, 1200))) for _ in range(7)]
    for i, (x1, y1) in enumerate(nodos):
        for x2, y2 in nodos[i + 1:i + 3]:
            mx, my = (x1 + x2) / 2, min(y1, y2) - abs(x2 - x1) * 0.35
            pts = [((1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t ** 2 * x2,
                    (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t ** 2 * y2) for t in np.linspace(0, 1, 60)]
            d.line(pts, fill=(220, 225, 240, 70), width=2)
    for x, y in nodos:
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(235, 238, 245, 200))
    x, y = nodos[0]
    d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=DORADO + (255,))
    pegar(img, c)


def documentos(img, semilla):
    """Hojas de contrato apiladas en perspectiva suave, con líneas de texto (contratos, bases, licitaciones)."""
    r = np.random.default_rng(semilla)
    for k in range(3):
        c = capa()
        d = ImageDraw.Draw(c)
        x0, y0 = 260 + k * 40, 420 + k * 50
        w, h = 620, 820
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=10, fill=(235, 238, 245, 26 + k * 10),
                            outline=(235, 238, 245, 70), width=2)
        for i in range(14):
            ly = y0 + 90 + i * 48
            largo = w - 120 - int(r.uniform(0, 220))
            d.line([x0 + 60, ly, x0 + 60 + largo, ly], fill=(235, 238, 245, 60), width=4)
        if k == 2:
            d.line([x0 + 60, y0 + h - 110, x0 + 300, y0 + h - 110], fill=DORADO + (200,), width=4)
        c = c.rotate(-6 + k * 4, resample=Image.BICUBIC, center=(W / 2, H / 2))
        pegar(img, c)


def columnas(img, semilla):
    """Columnas clásicas estilizadas (justicia) en líneas finas."""
    c = capa()
    d = ImageDraw.Draw(c)
    x0, y0, y1 = 170, 520, 1260
    d.polygon([(x0 - 60, y0), (W / 2, y0 - 230), (W - x0 + 60, y0)], outline=(235, 238, 245, 90), width=3)
    d.line([x0 - 70, y0 + 18, W - x0 + 70, y0 + 18], fill=(235, 238, 245, 90), width=3)
    for i in range(5):
        x = x0 + i * (W - 2 * x0) / 4
        for dx in (-34, 34):
            d.line([x + dx, y0 + 40, x + dx, y1], fill=(235, 238, 245, 70), width=3)
        for dx in (-12, 12):
            d.line([x + dx, y0 + 60, x + dx, y1 - 20], fill=(235, 238, 245, 30), width=2)
    d.line([x0 - 90, y1 + 10, W - x0 + 90, y1 + 10], fill=(235, 238, 245, 90), width=3)
    d.line([x0 - 120, y1 + 40, W - x0 + 120, y1 + 40], fill=DORADO + (160,), width=3)
    pegar(img, c)


def lineas_dato(img, semilla):
    """Candado y escudo de datos con red de nodos (protección de datos personales)."""
    r = np.random.default_rng(semilla)
    c = capa()
    d = ImageDraw.Draw(c)
    cx, cy = W / 2, 820
    pts = [(cx + 380 * math.cos(a), cy + 380 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)[:-1]]
    for p in pts:
        d.line([cx, cy, *p], fill=(235, 238, 245, 35), width=2)
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(235, 238, 245, 120))
    d.ellipse([cx - 380, cy - 380, cx + 380, cy + 380], outline=(235, 238, 245, 40), width=2)
    # escudo
    s = [(cx, cy - 210), (cx + 170, cy - 140), (cx + 150, cy + 90), (cx, cy + 220), (cx - 150, cy + 90), (cx - 170, cy - 140)]
    d.polygon(s, fill=(23, 27, 48, 230), outline=(235, 238, 245, 160))
    d.rounded_rectangle([cx - 62, cy - 20, cx + 62, cy + 85], radius=12, outline=DORADO + (230,), width=6)
    d.arc([cx - 45, cy - 95, cx + 45, cy + 5], 180, 360, fill=DORADO + (230,), width=6)
    pegar(img, c)


def cuadricula(img, semilla):
    """Cuadrícula técnica y gráfico de barras sutil (empresa, crecimiento, decisiones)."""
    c = capa()
    d = ImageDraw.Draw(c)
    for x in range(0, W, 90):
        d.line([x, 0, x, H], fill=(235, 238, 245, 14), width=1)
    for y in range(0, H, 90):
        d.line([0, y, W, y], fill=(235, 238, 245, 14), width=1)
    alturas = [180, 260, 230, 340, 420, 520]
    for i, a in enumerate(alturas):
        x = 200 + i * 120
        d.rectangle([x, 1200 - a, x + 70, 1200], fill=(235, 238, 245, 30 + i * 8))
    d.line([(235, 1200 - 200), (355, 1200 - 280), (475, 1200 - 250), (595, 1200 - 360), (715, 1200 - 440),
            (835, 1200 - 540)], fill=DORADO + (220,), width=5)
    d.line([160, 1200, 920, 1200], fill=(235, 238, 245, 90), width=2)
    pegar(img, c)


def balanza(img, semilla):
    """Balanza de la justicia en línea fina."""
    c = capa()
    d = ImageDraw.Draw(c)
    cx = W / 2
    d.line([cx, 420, cx, 1180], fill=(235, 238, 245, 120), width=5)
    d.line([cx - 300, 520, cx + 300, 520], fill=(235, 238, 245, 120), width=5)
    for sx in (-300, 300):
        d.line([cx + sx, 520, cx + sx - 110, 820], fill=(235, 238, 245, 70), width=2)
        d.line([cx + sx, 520, cx + sx + 110, 820], fill=(235, 238, 245, 70), width=2)
        d.arc([cx + sx - 130, 740, cx + sx + 130, 900], 0, 180, fill=(235, 238, 245, 140), width=5)
    d.polygon([(cx - 120, 1180), (cx + 120, 1180), (cx + 160, 1230), (cx - 160, 1230)], outline=(235, 238, 245, 120))
    d.ellipse([cx - 14, 406, cx + 14, 434], fill=DORADO + (230,))
    pegar(img, c)


FONDOS = [
    ("red-global-1.jpg", red_global, 1, (0.8, 0.2),
     "Mapa de conexiones internacionales: puntos unidos por arcos sobre azul (internacionalización, expansión, clientes extranjeros)"),
    ("red-global-2.jpg", red_global, 7, (0.2, 0.3),
     "Red de ciudades conectadas en el mundo, punto dorado de origen (operar en otro país, contratos internacionales)"),
    ("documentos-1.jpg", documentos, 2, (0.7, 0.3),
     "Hojas de contrato apiladas con líneas de texto (contratos, bases de licitación, documentos, antecedentes)"),
    ("documentos-2.jpg", documentos, 9, (0.3, 0.2),
     "Documentos legales en perspectiva con firma dorada (revisión de contratos, cumplimiento, políticas)"),
    ("columnas.jpg", columnas, 3, (0.5, 0.15),
     "Columnas clásicas de un edificio judicial en líneas finas (derecho, institucionalidad, Estado, compras públicas)"),
    ("datos-escudo.jpg", lineas_dato, 4, (0.5, 0.35),
     "Escudo con candado dorado y red de datos (protección de datos personales, Ley 21.719, seguridad de la información)"),
    ("cuadricula-crecimiento.jpg", cuadricula, 5, (0.85, 0.15),
     "Cuadrícula técnica con gráfico de barras y línea dorada ascendente (empresas, crecimiento, decisiones, riesgos)"),
    ("balanza.jpg", balanza, 6, (0.5, 0.2),
     "Balanza de la justicia en línea fina (conflictos, controversias, resolución de disputas, jurisdicción)"),
]


def main():
    DIR.mkdir(exist_ok=True)
    meta = []
    for archivo, fn, semilla, (cx, cy), desc in FONDOS:
        img = base(cx, cy)
        fn(img, semilla)
        img.convert("RGB").save(DIR / archivo, quality=92)
        meta.append({"archivo": archivo, "descripcion": desc, "orientacion": "vertical"})
    (DIR / "fotos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(meta)} fondos en {DIR}")


if __name__ == "__main__":
    main()
