"""Reels con estilo "premium" (rubros profesionales, ej. LegalMain): sobrio, editorial y lento.

Se activa con "estilo_video": "premium" en marca.json (video.reel lo deriva aquí). Diferencias con el estilo
de AHP:
- Fondo con velo del color principal (no negro), viñeta suave y decoración fija de la marca: grilla de puntos
  arriba a la derecha con una línea fina y arcos concéntricos dorados abajo a la izquierda.
- Título que sube línea por línea desde una máscara (sin rebote), filete dorado que se dibuja bajo el título
  y cuerpo que aparece con un fundido lento; las cifras van en dorado (sin píldoras).
- Transición con fundido al azul de la marca y una línea dorada que cruza el centro (sin barridos).
- Barra de progreso dorada de 3 px y sitio web discreto con subrayado dorado, sin píldora.
- La última escena es el llamado a la acción (texto y locución) con un marco dorado con el sitio web.
- Cierre solo con el logo: dos líneas doradas se abren desde el centro, el logo aparece con una máscara
  que se abre en vertical y un brillo diagonal lo recorre; la grilla de puntos se enciende de fondo.
"""
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import diseno
from video import (FPS, H, RETRASO_VOZ, W, Clip, Fondo, _audio, _con_alfa, _destacar, _duracion, _ease,
                   _ease_io, _hex)

MARGEN = 96
ANCHO_TEXTO = 840          # deja libre la columna de íconos de Instagram a la derecha
ZONA_SUP = 250
ZONA_INF = 1920 - 330
TRANS = 0.7                # fundido entre escenas (s)
DUR_CIERRE = 3.4


# ---------- piezas gráficas ----------

def _velo(color, base=0.55):
    """Velo del color principal: más denso abajo (texto) y en los bordes (viñeta). base menor deja ver más
    el fondo (videos reales)."""
    y, x = np.mgrid[0:H, 0:W]
    vertical = base + (0.93 - base) * np.clip((y / H - 0.25) / 0.6, 0, 1)
    d = np.sqrt(((x / W - 0.5) * 1.2) ** 2 + ((y / H - 0.45) * 0.9) ** 2)
    u = np.clip((d - 0.3) / 0.5, 0, 1)
    vin = u * u * (3 - 2 * u) * 0.35                      # viñeta con borde suave (smoothstep)
    ruido = np.random.default_rng(5).normal(0, 0.006, (H, W))   # tramado: evita bandas
    a = np.clip(vertical + vin + ruido, 0, 0.94)
    img = np.zeros((H, W, 4), np.uint8)
    img[..., :3] = color
    img[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(img, "RGBA")


def _decoracion(dorado, alfa=1.0):
    """Grilla de puntos y línea arriba a la derecha; arcos concéntricos abajo a la izquierda."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    for fila in range(4):
        for col in range(6):
            x, y = W - 250 + col * 30, 150 + fila * 30
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(225, 228, 238, int(150 * alfa)))
    d.line([W - 560, 196, W - 290, 196], fill=(225, 228, 238, int(110 * alfa)), width=2)
    for k in range(5):
        r = 90 + k * 34
        d.ellipse([-r, ZONA_INF + 120 - r, r, ZONA_INF + 120 + r], outline=dorado + (int((70 - k * 10) * alfa),),
                  width=2)
    return c


def _linea_texto(texto, fuente, color, dorado):
    """Una línea como imagen RGBA, con sombra muy suave; las palabras con cifras van en dorado."""
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    asc, desc = fuente.getmetrics()
    alto = asc + desc + 20
    esp = d.textlength(" ", font=fuente)
    palabras = texto.split()
    ancho = int(sum(d.textlength(p, font=fuente) for p in palabras) + esp * max(0, len(palabras) - 1)) + 40
    im = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    sm = Image.new("RGBA", im.size, (0, 0, 0, 0))
    x = 10
    for p in palabras:
        ImageDraw.Draw(sm).text((x + 1, 12), p, font=fuente, fill=(0, 0, 0, 120))
        ImageDraw.Draw(im).text((x, 10), p, font=fuente, fill=(dorado if _destacar(p) else color) + (255,))
        x += d.textlength(p, font=fuente) + esp
    sm = sm.filter(ImageFilter.GaussianBlur(4))
    sm.alpha_composite(im)
    return sm


def _subir(img, linea, x, y, e, a=1.0):
    """Pega la línea "subiendo" desde una máscara en su propia caja (efecto de revelado editorial)."""
    if e <= 0 or a <= 0:
        return
    h = linea.height
    dy = int(h * (1 - e) * 0.9)
    visible = linea.crop((0, 0, linea.width, h - dy))
    img.alpha_composite(_con_alfa(visible, min(1.0, e * 1.4) * a), (int(x), int(y + dy)))


# ---------- reel ----------

def reel(escenas, destino, voz=None, musica=None, locuciones=None):
    """escenas: [(titulo, texto[, foto])]; la última es el llamado a la acción. Misma interfaz que video.reel."""
    m = diseno.marca()
    azul, dorado = _hex(m["colores"]["principal"]), _hex(m["colores"]["acento"])
    blanco, gris = (255, 255, 255), (206, 211, 224)
    fotos = [diseno.FOTOS_DIR / f["archivo"] for f in diseno.fotos()]
    velo = _velo(azul)
    velo_video = _velo(azul, 0.18)
    deco = _decoracion(dorado)
    logo = diseno._logo(True, 300, 120)
    f_num = diseno._fuente(True, 28)
    f_pie = diseno._fuente(False, 32)
    f_web = diseno._fuente(True, 46)
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    web = m.get("web") or m.get("usuario", "")
    retraso = float(m.get("retraso_voz", 0.6))   # la voz entra cuando el título ya empezó a aparecer
    pausa = float(m.get("pausa_voz", 1.4))       # silencio tras cada frase antes de cambiar de escena

    preparadas = []
    for i, esc in enumerate(escenas):
        titulo, texto = esc[0], esc[1]
        foto = esc[2] if len(esc) > 2 and esc[2] else None
        partes = foto.split("+") if foto else []
        es_clip = bool(partes) and all(x.lower().endswith(".mp4") and (diseno.VIDEOS_DIR / x).exists() for x in partes)
        ruta = [diseno.VIDEOS_DIR / x for x in partes] if es_clip else \
            (diseno.FOTOS_DIR / foto if foto and (diseno.FOTOS_DIR / foto).exists() else
             (fotos[i % len(fotos)] if fotos else None))
        portada, cta = i == 0, i == len(escenas) - 1 and len(escenas) > 1
        # última escena sin título ni texto: solo el logo (la animación del cierre dura lo que dura su locución)
        solo_logo = cta and not titulo.strip() and not texto.strip()
        cta = cta and not solo_logo
        f_tit, lin_t, tam_t, _ = diseno._ajustar(d0, titulo, True, 96 if portada else 84, 56, ANCHO_TEXTO, 460, 1.15)
        f_txt, lin_x, tam_c, _ = diseno._ajustar(d0, texto, False, 50, 38, ANCHO_TEXTO, 420, 1.4)
        tit = [_linea_texto(ln, f_tit, blanco, dorado) for ln in lin_t]
        cuerpo = [_linea_texto(ln, f_txt, gris, dorado) for ln in lin_x]
        lh_t, lh_c = int(tam_t * 1.16), int(tam_c * 1.45)
        alto = len(tit) * lh_t + 70 + len(cuerpo) * lh_c + (190 if cta else 0)
        y0 = ZONA_SUP + 200 + max(0, (ZONA_INF - 80 - (ZONA_SUP + 200) - alto) // 2)   # bloque centrado
        palabras = len(f"{titulo} {texto}".split())
        dur = max(4.2, min(8.5, 2.4 + palabras * 0.30))
        loc = locuciones[i] if locuciones and i < len(locuciones) else None
        if loc:
            dur = max(dur, _duracion(loc) + retraso + pausa)
        fondo = None
        if ruta:
            fondo = Clip(ruta, 0, dur, reparto=True) if es_clip else Fondo(ruta, 0, desenfoque=False, dir_paneo=1 if i % 2 == 0 else -1)
        preparadas.append(dict(fondo=fondo, video=es_clip, tit=tit, cuerpo=cuerpo, lh_t=lh_t, lh_c=lh_c, y0=y0, dur=dur, cta=cta, logo=solo_logo))

    if preparadas[-1]["logo"]:
        total = sum(p["dur"] for p in preparadas)
        fin_escenas = total - preparadas[-1]["dur"]
    else:
        total = sum(p["dur"] for p in preparadas) + DUR_CIERRE
        fin_escenas = total - DUR_CIERRE
    n_num = sum(1 for p in preparadas if not p["logo"])

    def escena(p, tl, num):
        dur = p["dur"]
        img = (p["fondo"].cuadro(tl / dur) if p["fondo"] else Image.new("RGB", (W, H), azul)).convert("RGBA")
        img.alpha_composite(velo_video if p["video"] else velo)
        img.alpha_composite(deco)
        sal = _ease_io((tl - (dur - 0.5)) / 0.5)      # todo se desvanece y sube un poco al final
        a = 1 - sal
        up = int(-24 * sal)
        if logo:
            img.alpha_composite(_con_alfa(logo, _ease(tl / 0.6) if num == 0 else 1.0), (MARGEN, ZONA_SUP - 120))
        y = p["y0"] + up
        # numeración: "01 — 06" con una línea fina dorada
        e = _ease((tl - 0.15) / 0.6) * a
        if e > 0:
            capa = Image.new("RGBA", (420, 40), (0, 0, 0, 0))
            dc = ImageDraw.Draw(capa)
            dc.text((0, 0), f"{num + 1:02d}", font=f_num, fill=dorado + (255,))
            dc.line([62, 18, 62 + int(80 * e), 18], fill=dorado + (255,), width=2)
            dc.text((158, 0), f"{n_num:02d}", font=f_num, fill=(200, 205, 220, 255))
            img.alpha_composite(_con_alfa(capa, e), (MARGEN, y - 70))
        # título: cada línea sube desde su máscara
        for li, ln in enumerate(p["tit"]):
            _subir(img, ln, MARGEN - 10, y + li * p["lh_t"] - 10, _ease_io((tl - 0.25 - 0.18 * li) / 0.75), a)
        y += len(p["tit"]) * p["lh_t"] + 22
        # filete dorado que se dibuja
        t_fil = 0.35 + 0.18 * len(p["tit"])
        e = _ease_io((tl - t_fil) / 0.7)
        if e > 0:
            ImageDraw.Draw(img).rectangle([MARGEN, y, MARGEN + int(140 * e), y + 3], fill=dorado + (int(255 * a),))
        y += 48
        # cuerpo: fundido lento línea por línea
        for li, ln in enumerate(p["cuerpo"]):
            e = _ease((tl - t_fil - 0.35 - 0.2 * li) / 0.8)
            if e > 0:
                img.alpha_composite(_con_alfa(ln, e * a), (MARGEN - 10, int(y + li * p["lh_c"] - 10 + 14 * (1 - e))))
        y += len(p["cuerpo"]) * p["lh_c"] + 40
        # llamado a la acción: marco dorado con el sitio web que se dibuja
        if p["cta"] and (web or m.get("cta_abierto")):
            e = _ease_io((tl - t_fil - 0.6 - 0.2 * len(p["cuerpo"])) / 0.9)
            if e > 0:
                rotulo = (m.get("cta_cierre") or "Conversemos") if m.get("cta_abierto") else web
                tw = d0.textlength(rotulo, font=f_web)
                bw, bh = tw + 90, 104
                capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                dc = ImageDraw.Draw(capa)
                x0, y0 = MARGEN, y
                per = 2 * (bw + bh)
                largo = per * e                     # el marco se traza en sentido horario
                tramos = [((x0, y0), (x0 + bw, y0)), ((x0 + bw, y0), (x0 + bw, y0 + bh)),
                          ((x0 + bw, y0 + bh), (x0, y0 + bh)), ((x0, y0 + bh), (x0, y0))]
                for (xa, ya), (xb, yb) in tramos:
                    seg = math.hypot(xb - xa, yb - ya)
                    if largo <= 0:
                        break
                    f = min(1.0, largo / seg)
                    dc.line([xa, ya, xa + (xb - xa) * f, ya + (yb - ya) * f], fill=dorado + (255,), width=3)
                    largo -= seg
                et = _ease((e - 0.4) / 0.6)
                dc.rectangle([x0 + 3, y0 + 3, x0 + bw - 3, y0 + bh - 3], fill=azul + (int(150 * et),))
                dc.text((x0 + 45, y0 + (bh - 62) / 2), rotulo, font=f_web, fill=(255, 255, 255, int(255 * et)))
                img.alpha_composite(_con_alfa(capa, a))
        return img

    def pie(img, t):
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 3], fill=(255, 255, 255, 40))
        d.rectangle([0, 0, int(W * t / total), 3], fill=dorado + (255,))
        if web:
            yb = ZONA_INF + 40
            d.text((MARGEN + 210, yb), web, font=f_pie, fill=(225, 228, 238, 220))
            tw = d.textlength(web, font=f_pie)
            d.line([MARGEN + 210, yb + 46, MARGEN + 210 + tw, yb + 46], fill=dorado + (200,), width=2)
        return img

    logo_g = diseno._logo(True, 620, 270)
    fondo_cierre = Image.new("RGBA", (W, H), azul + (255,))
    yy, xx = np.mgrid[0:H, 0:W]
    luz = np.exp(-(((xx - W / 2) / W) ** 2 + ((yy - H * 0.47) / H * 0.8) ** 2) / 0.06)
    luz = np.clip(luz + np.random.default_rng(6).normal(0, 0.012, luz.shape), 0, 1)
    luz_im = np.zeros((H, W, 4), np.uint8)
    luz_im[..., :3] = (60, 70, 110)
    luz_im[..., 3] = (luz * 130).astype(np.uint8)
    fondo_cierre.alpha_composite(Image.fromarray(luz_im, "RGBA"))

    def cierre(tl):
        img = fondo_cierre.copy()
        img.alpha_composite(_decoracion(dorado, _ease(tl / 1.2)))
        cy = int(H * 0.47)
        d = ImageDraw.Draw(img)
        # dos líneas doradas que se abren desde el centro
        e = _ease_io(tl / 0.9)
        media = int(330 * e)
        if logo_g:
            gap = logo_g.height // 2 + 70
            for yl in (cy - gap, cy + gap):
                d.line([W / 2 - media, yl, W / 2 + media, yl], fill=dorado + (230,), width=2)
            # logo: máscara que se abre en vertical desde el centro
            e2 = _ease_io((tl - 0.45) / 0.9)
            if e2 > 0:
                lh = logo_g.height
                abierto = int(lh * e2)
                y_ini = (lh - abierto) // 2
                corte = logo_g.crop((0, y_ini, logo_g.width, y_ini + abierto))
                img.alpha_composite(corte, (W // 2 - logo_g.width // 2, cy - lh // 2 + y_ini))
            # brillo diagonal que recorre el logo
            e3 = (tl - 1.5) / 0.9
            if 0 < e3 < 1:
                brillo = Image.new("L", logo_g.size, 0)
                bx = int(-200 + (logo_g.width + 400) * _ease_io(e3))
                ImageDraw.Draw(brillo).polygon([(bx, 0), (bx + 70, 0), (bx - 50, logo_g.height), (bx - 120, logo_g.height)],
                                               fill=170)
                brillo = brillo.filter(ImageFilter.GaussianBlur(18))
                alfa = Image.fromarray((np.array(brillo, np.float32) * np.array(logo_g.split()[3], np.float32) / 255)
                                       .astype(np.uint8))
                capa = Image.new("RGBA", logo_g.size, dorado + (0,))
                capa.putalpha(alfa)
                img.alpha_composite(capa, (W // 2 - logo_g.width // 2, cy - logo_g.height // 2))
        return img

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    entradas, filtros, voz = _audio([p["dur"] for p in preparadas], locuciones, total, fin_escenas, musica, voz,
                                    retraso=retraso)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *entradas, *filtros, "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    inicios, acc = [], 0.0
    for p in preparadas:
        inicios.append(acc)
        acc += p["dur"]
    cortes = inicios[1:] + [acc]
    for f in range(int(total * FPS)):
        t = f / FPS
        if t >= acc:
            img = cierre(t - acc)
        else:
            i = max(j for j, s in enumerate(inicios) if s <= t)
            img = cierre(t - inicios[i]) if preparadas[i]["logo"] else pie(escena(preparadas[i], t - inicios[i], i), t)
        # transición: fundido al azul y una línea dorada que cruza el centro
        for s in cortes:
            if s - TRANS / 2 <= t < s + TRANS / 2:
                u = (t - (s - TRANS / 2)) / TRANS
                k = 1 - abs(u - 0.5) * 2                          # 0 -> 1 -> 0
                img.alpha_composite(Image.new("RGBA", (W, H), azul + (int(255 * _ease_io(k)),)))
                largo = int(W * 0.5 * _ease_io(min(1, u * 1.6)))
                ImageDraw.Draw(img).line([W / 2 - largo, H * 0.47, W / 2 + largo, H * 0.47],
                                         fill=dorado + (int(255 * k),), width=2)
        proc.stdin.write(img.convert("RGB").tobytes())
    for p in preparadas:
        if isinstance(p["fondo"], Clip):
            p["fondo"].cerrar()
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falló al codificar el reel")
    if locuciones and voz and Path(voz).name == "voz.wav":
        Path(voz).unlink(missing_ok=True)
    return destino
