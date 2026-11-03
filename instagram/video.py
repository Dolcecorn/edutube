"""Reels con estilo de motion graphics (cuadro a cuadro con Pillow, codificado con ffmpeg).

- La foto de fondo se mueve (zoom y paneo suaves); el texto NO hace zoom: entra animado.
- Título palabra por palabra, cuerpo línea por línea, números y cifras destacados en cyan.
- Transición con barrido rojo de la marca entre escenas, barra de progreso y cierre con logo y teléfono.
- Música si existe marca/musica.mp3; voz en off si se pasa un archivo de audio.
"""
import math
import re
import subprocess
from pathlib import Path

import numpy as np

from PIL import Image, ImageDraw, ImageFilter, ImageOps

import diseno

W, H = diseno.REEL
FPS = 30
MARGEN = 84            # margen izquierdo
ANCHO_TEXTO = 860      # deja libre la columna de íconos de Instagram a la derecha
ZONA_SUP = 250         # zona segura superior
ZONA_INF = 1920 - 330  # zona segura inferior (descripción y botones de Instagram)
TRANS = 0.45           # duración del barrido entre escenas (s)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _ease(t):  # ease-out cúbico
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _ease_io(t):
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _con_alfa(im, a):
    if a >= 0.999:
        return im
    r, g, b, al = im.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


def _destacar(palabra):
    return bool(re.search(r"\d", palabra))


def _render_linea(texto, fuente, color, acento, sombra=True):
    """Dibuja una línea como imagen RGBA; las palabras con cifras van sobre una píldora cyan."""
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    asc, desc = fuente.getmetrics()
    alto = asc + desc + 16
    esp = d.textlength(" ", font=fuente)
    palabras = texto.split()
    ancho = int(sum(d.textlength(p, font=fuente) for p in palabras) + esp * (len(palabras) - 1)) + 40
    im = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    if sombra:
        sm = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    x = 8
    for p in palabras:
        lp = d.textlength(p, font=fuente)
        if _destacar(p):
            nucleo = p.rstrip(".,;:!?)")
            ln = d.textlength(nucleo, font=fuente)
            dr.rounded_rectangle([x - 8, 4, x + ln + 8, alto - 6], radius=10, fill=acento + (255,))
        if sombra:
            ImageDraw.Draw(sm).text((x + 2, 10), p, font=fuente, fill=(0, 0, 0, 170))
        dr.text((x, 8), p, font=fuente, fill=color + (255,))
        x += lp + esp
    if sombra:
        sm = sm.filter(ImageFilter.GaussianBlur(5))
        sm.alpha_composite(im)
        im = sm
    return im


def _render_palabras(texto, fuente, ancho_max, color):
    """Título: lista de líneas, cada una lista de (imagen_palabra, x)."""
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lineas = diseno._envolver(d, texto, fuente, ancho_max)
    esp = d.textlength(" ", font=fuente)
    asc, desc = fuente.getmetrics()
    res = []
    for ln in lineas:
        fila, x = [], 0
        for p in ln.split():
            lp = d.textlength(p, font=fuente)
            im = Image.new("RGBA", (int(lp) + 24, asc + desc + 24), (0, 0, 0, 0))
            sm = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(sm).text((14, 14), p, font=fuente, fill=(0, 0, 0, 190))
            sm = sm.filter(ImageFilter.GaussianBlur(6))
            ImageDraw.Draw(sm).text((10, 10), p, font=fuente, fill=color + (255,))
            fila.append((sm, x))
            x += lp + esp
        res.append(fila)
    return res


class Fondo:
    """Foto con zoom/paneo lento (Ken Burns). Pre-escala una vez; cada cuadro es un recorte."""

    def __init__(self, ruta, oscuro, desenfoque=False, dir_paneo=1):
        base = diseno._cubrir(ruta, int(W * 1.16), int(H * 1.16))
        if desenfoque:
            base = base.filter(ImageFilter.GaussianBlur(14))
        self.base = base
        self.dir = dir_paneo
        capa = Image.new("RGBA", base.size, (0, 0, 0, oscuro))
        b = base.convert("RGBA")
        b.alpha_composite(capa)
        self.base = b.convert("RGB")

    def cuadro(self, t):  # t en 0..1
        e = _ease_io(t)
        z = 1.16 - 0.12 * e                      # se acerca suavemente
        cw, ch = int(W * z), int(H * z)
        bw, bh = self.base.size
        x = (bw - cw) / 2 + self.dir * (bw - cw) * 0.35 * (e - 0.5)
        y = (bh - ch) / 2
        rec = self.base.crop((int(x), int(y), int(x) + cw, int(y) + ch))
        return rec.resize((W, H), Image.BILINEAR)


RETRASO_VOZ = 0.35  # la voz entra un poco después del corte de escena


def _duracion(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True)
    return float(r.stdout or 0)


class _Fuente:
    """Lee un clip cuadro a cuadro a su velocidad original (sin interpolar ni ralentizar)."""

    def __init__(self, ruta, recorte=None):
        self.ruta, self.largo = ruta, _duracion(ruta)
        corte = f"crop={recorte}," if recorte else ""
        vf = f"{corte}fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-an", "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.i, self.ultimo = -1, None

    def cuadro(self, n):  # n = número de cuadro, siempre hacia adelante
        while self.i < n:
            datos = self.proc.stdout.read(W * H * 3)
            if len(datos) < W * H * 3:
                break
            self.ultimo, self.i = datos, self.i + 1
        return None if self.ultimo is None else np.frombuffer(self.ultimo, np.uint8).reshape(H, W, 3)

    def cerrar(self):
        self.proc.stdout.close()
        self.proc.kill()
        self.proc.wait()


class Clip:
    """Uno o más clips de video reales como fondo de una escena. Cada clip se reproduce tal cual, a su
    velocidad original (solo se recorta a 9:16 y se oscurece igual que las fotos). Si la escena dura más
    que el clip, se encadena el siguiente con un fundido corto en vez de estirarlo."""

    FUNDIDO = 0.4

    def __init__(self, rutas, oscuro, dur):
        rutas = rutas if isinstance(rutas, (list, tuple)) else [rutas]
        info = {v["archivo"]: v for v in diseno.videos()}
        self.items = [(Path(r), info.get(Path(r).name, {}).get("recorte")) for r in rutas]
        self.dur, self.factor = dur, 1 - oscuro / 255
        self.fuentes, self.inicios = [], []

    def _fuente(self, k):
        while len(self.fuentes) <= k:
            ruta, recorte = self.items[len(self.fuentes)]
            ini = 0.0 if not self.fuentes else \
                self.inicios[-1] + max(1.0, self.fuentes[-1].largo - 0.15 - self.FUNDIDO)
            self.fuentes.append(_Fuente(ruta, recorte))
            self.inicios.append(ini)
        return self.fuentes[k]

    def cuadro(self, t):  # t en 0..1, siempre hacia adelante
        s = t * self.dur
        self._fuente(0)
        # ¿hay que sumar el siguiente clip?
        while len(self.fuentes) < len(self.items) and \
                s >= self.inicios[-1] + self.fuentes[-1].largo - 0.15 - self.FUNDIDO:
            self._fuente(len(self.fuentes))
        k = len(self.fuentes) - 1
        a = self.fuentes[k].cuadro(int((s - self.inicios[k]) * FPS))
        if k > 0:
            mezcla = (s - self.inicios[k]) / self.FUNDIDO
            if mezcla < 1:
                b = self.fuentes[k - 1].cuadro(int((s - self.inicios[k - 1]) * FPS))
                if a is None:
                    a = b
                elif b is not None:
                    m = _ease_io(max(0.0, mezcla))
                    a = a * m + b * (1 - m)
        if a is None:
            return Image.new("RGB", (W, H), (20, 20, 20))
        return Image.fromarray((a * self.factor).astype(np.uint8))

    def cerrar(self):
        for f in self.fuentes:
            f.cerrar()
        self.fuentes = []


def _degradados():
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for y in range(0, 520):                       # arriba, para el logo
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * (1 - y / 520))))
    for y in range(700, H):                        # abajo, para el texto
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(225 * min(1, (y - 700) / 650))))
    return g


def reel(escenas, destino, voz=None, musica=None, locuciones=None):
    """escenas: [(titulo, texto[, foto])]. locuciones: lista paralela de wav (o None) con la voz en off de
    cada escena; la escena dura lo necesario para que se escuche completa. Devuelve la ruta del MP4."""
    m = diseno.marca()
    rojo, cyan = _hex(m["colores"]["principal"]), _hex(m["colores"]["acento"])
    blanco = (255, 255, 255)
    fotos = [diseno.FOTOS_DIR / f["archivo"] for f in diseno.fotos()]
    grad = _degradados()
    logo = diseno._logo(True, 470, 150)
    f_cifra = diseno._fuente(True, 32)
    f_pie = diseno._fuente(True, 34)
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    # --- preparar escenas ---
    preparadas = []
    for i, esc in enumerate(escenas):
        titulo, texto = esc[0], esc[1]
        foto = esc[2] if len(esc) > 2 and esc[2] else None
        partes = foto.split("+") if foto else []
        es_clip = bool(partes) and all(x.lower().endswith(".mp4") and (diseno.VIDEOS_DIR / x).exists()
                                       for x in partes)
        ruta = [diseno.VIDEOS_DIR / x for x in partes] if es_clip else \
            (diseno.FOTOS_DIR / foto if foto else (fotos[i % len(fotos)] if fotos else None))
        portada = i == 0
        f_tit, _, tam_t, _ = diseno._ajustar(d0, titulo, True, 84 if portada else 72, 52, ANCHO_TEXTO, 420)
        f_txt, lin_txt, tam_c, _ = diseno._ajustar(d0, texto, False, 50, 40, ANCHO_TEXTO, 440, 1.35)
        pal = _render_palabras(titulo, f_tit, ANCHO_TEXTO, blanco)
        cuerpo = [_render_linea(ln, f_txt, blanco, cyan) for ln in lin_txt]
        lh_t, lh_c = int(tam_t * 1.18), int(tam_c * 1.42)
        alto_bloque = len(pal) * lh_t + 40 + len(cuerpo) * lh_c
        y0 = ZONA_INF - 40 - alto_bloque
        y0 = max(y0, ZONA_SUP + 330)
        palabras = len(f"{titulo} {texto}".split())
        dur = max(3.8, min(8.0, 2.0 + palabras * 0.30))
        loc = locuciones[i] if locuciones and i < len(locuciones) else None
        if loc:
            dur = max(dur, _duracion(loc) + RETRASO_VOZ + 0.6)
        preparadas.append(dict(
            fondo=(Clip(ruta, 70, dur) if es_clip else
                   Fondo(ruta, 70, desenfoque=foto is None, dir_paneo=1 if i % 2 == 0 else -1)) if ruta else None,
            pal=pal, cuerpo=cuerpo, lh_t=lh_t, lh_c=lh_c, y0=y0, dur=dur, portada=portada))

    # --- cierre de marca ---
    dur_cierre = 3.6
    total = sum(p["dur"] for p in preparadas) + dur_cierre
    n_cuadros = int(total * FPS)

    logo_grande = diseno._logo(True, 760, 300)
    f_tel = diseno._fuente(True, 74)
    f_cta = diseno._fuente(True, 44)
    f_user = diseno._fuente(False, 40)

    def cierre(tl):
        img = Image.new("RGB", (W, H), rojo)
        d = ImageDraw.Draw(img)
        # círculos suaves que se expanden
        for k in range(3):
            r = int(260 + 420 * _ease((tl - 0.15 * k) / 2.5)) + 120 * k
            a = int(40 * (1 - k / 3))
            capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(capa).ellipse([W / 2 - r, 760 - r, W / 2 + r, 760 + r], outline=(255, 255, 255, a), width=4)
            img.paste(capa, (0, 0), capa)
        if logo_grande:
            e = _ease(tl / 0.7)
            esc = 0.8 + 0.2 * e
            lg = logo_grande.resize((int(logo_grande.width * esc), int(logo_grande.height * esc)), Image.LANCZOS)
            lg = _con_alfa(lg, e)
            img.paste(lg, (W // 2 - lg.width // 2, 760 - lg.height // 2), lg)
        e2 = _ease((tl - 0.5) / 0.6)
        if e2 > 0:
            cta = "Llámanos"
            tw = d.textlength(cta, font=f_cta)
            capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dc = ImageDraw.Draw(capa)
            dc.text((W / 2 - tw / 2, 1010 + 30 * (1 - e2)), cta, font=f_cta, fill=(255, 255, 255, int(255 * e2)))
            tel = m["telefono"]
            tw = d.textlength(tel, font=f_tel)
            pulso = 1 + 0.03 * math.sin(max(0, tl - 1.2) * 6) if tl > 1.2 else 1
            bw, bh = (tw + 90) * pulso, 130 * pulso
            dc.rounded_rectangle([W / 2 - bw / 2, 1080 + 30 * (1 - e2), W / 2 + bw / 2, 1080 + bh + 30 * (1 - e2)],
                                 radius=int(bh / 2), fill=(255, 255, 255, int(255 * e2)))
            dc.text((W / 2 - tw / 2, 1080 + (bh - 86) / 2 + 30 * (1 - e2)), tel, font=f_tel,
                    fill=rojo + (int(255 * e2),))
            us = "   ·   ".join(x for x in (m.get("web"), m.get("usuario")) if x)
            tw = d.textlength(us, font=f_user)
            e3 = _ease((tl - 0.9) / 0.6)
            dc.text((W / 2 - tw / 2, 1270), us, font=f_user, fill=(255, 255, 255, int(230 * e3)))
            img.paste(capa, (0, 0), capa)
        return img

    def escena(p, tl, num):
        dur = p["dur"]
        img = p["fondo"].cuadro(tl / dur) if p["fondo"] else Image.new("RGB", (W, H), (30, 30, 30))
        img = img.convert("RGBA")
        img.alpha_composite(grad)
        salida = _ease((tl - (dur - 0.35)) / 0.35)  # el texto se va justo antes del barrido
        a_sal = 1 - salida
        # logo
        if logo:
            img.alpha_composite(_con_alfa(logo, _ease(tl / 0.4) if num == 0 else 1), (MARGEN - 6, ZONA_SUP - 130))
        y = p["y0"]
        # número de escena (01 / 05)
        n_txt = f"{num + 1:02d} / {len(preparadas):02d}"
        e = _ease((tl - 0.1) / 0.4) * a_sal
        if e > 0:
            capa = Image.new("RGBA", (300, 50), (0, 0, 0, 0))
            ImageDraw.Draw(capa).text((0, 0), n_txt, font=f_cifra, fill=cyan + (255,))
            img.alpha_composite(_con_alfa(capa, e), (MARGEN + 2, y - 70))
        # título palabra por palabra
        k = 0
        for li, fila in enumerate(p["pal"]):
            for im, x in fila:
                t0 = 0.15 + 0.07 * k
                e = _ease((tl - t0) / 0.45)
                if e > 0:
                    dy = int(50 * (1 - e)) - int(30 * salida)
                    img.alpha_composite(_con_alfa(im, e * a_sal), (int(MARGEN + x - 10), y + li * p["lh_t"] + dy - 10))
                k += 1
        y += len(p["pal"]) * p["lh_t"] + 8
        # barra cyan que crece
        t_bar = 0.15 + 0.07 * k
        e = _ease((tl - t_bar) / 0.5)
        if e > 0:
            d = ImageDraw.Draw(img)
            d.rectangle([MARGEN, y, MARGEN + int(110 * e), y + 9], fill=cyan + (int(255 * a_sal),))
        y += 32
        # cuerpo línea por línea
        for li, im in enumerate(p["cuerpo"]):
            t0 = t_bar + 0.25 + 0.16 * li
            e = _ease((tl - t0) / 0.5)
            if e > 0:
                dx = int(-40 * (1 - e))
                img.alpha_composite(_con_alfa(im, e * a_sal), (MARGEN - 8 + dx, y + li * p["lh_c"] - 8))
        return img

    def pie(img, t):
        d = ImageDraw.Draw(img)
        # barra de progreso arriba
        d.rectangle([0, 0, W, 10], fill=(255, 255, 255, 60))
        d.rectangle([0, 0, int(W * t / total), 10], fill=cyan + (255,))
        # pie rojo con teléfono (dentro de la zona segura)
        yb = ZONA_INF + 20
        d.rounded_rectangle([MARGEN - 20, yb, MARGEN + 520, yb + 70], radius=35, fill=rojo + (255,))
        d.text((MARGEN + 10, yb + 15), "☎ " + m["telefono"], font=f_pie, fill=(255, 255, 255, 255))
        return img

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fin_escenas = total - dur_cierre
    if locuciones and any(locuciones):  # una sola pista de voz alineada con el inicio de cada escena
        import locucion
        acc0, partes = 0.0, []
        for p, loc in zip(preparadas, locuciones):
            if loc:
                partes.append((acc0 + RETRASO_VOZ, loc))
            acc0 += p["dur"]
        import tempfile
        voz = locucion.pista(partes, total, Path(tempfile.mkdtemp()) / "voz.wav")
    # musica puede ser una función (segundos, golpe) -> ruta: compone la pista con el golpe final justo
    # cuando aparece el logo del cierre
    musica = Path(musica(total, fin_escenas) if callable(musica) else musica or diseno.MARCA_DIR / "musica.mp3")
    entradas, filtros = [], []
    if voz:
        entradas += ["-i", str(voz)]
    if musica.exists():
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
    if voz and musica.exists():
        # la música baja sola cuando habla la voz (sidechain) y vuelve a subir en las pausas
        filtros = ["-filter_complex",
                   "[1:a]aformat=channel_layouts=stereo,asplit=2[v][sc];"
                   "[2:a]volume=0.8[m];[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[md];"
                   f"[md][v]amix=inputs=2:duration=first:normalize=0,"
                   f"afade=t=out:st={max(0, total - 0.4):.2f}:d=0.4[a]",
                   "-map", "0:v", "-map", "[a]"]
    elif voz or musica.exists():
        filtros = ["-map", "0:v", "-map", "1:a"]
        if musica.exists():
            filtros += ["-af", f"afade=t=out:st={max(0, total - 0.4):.2f}:d=0.4"]
    else:
        entradas += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        filtros = ["-map", "0:v", "-map", "1:a"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *entradas, *filtros, "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    inicios, acc = [], 0.0
    for p in preparadas:
        inicios.append(acc)
        acc += p["dur"]
    for f in range(n_cuadros):
        t = f / FPS
        if t >= acc:
            img = cierre(t - acc).convert("RGBA")
        else:
            i = max(j for j, s in enumerate(inicios) if s <= t)
            img = pie(escena(preparadas[i], t - inicios[i], i), t)
        # barrido rojo entre escenas: entra al final de una escena, sale al inicio de la siguiente
        fin_esc = [s + p["dur"] for s, p in zip(inicios, preparadas)]
        for s in fin_esc:
            if s - TRANS / 2 <= t < s + TRANS / 2:
                u = (t - (s - TRANS / 2)) / TRANS  # 0..1
                d = ImageDraw.Draw(img)
                if u < 0.5:
                    x1 = int(W * 1.3 * _ease_io(u * 2))
                    d.polygon([(0, 0), (x1, 0), (x1 - 300, H), (0, H)], fill=rojo + (255,))
                else:
                    x0 = int(W * 1.3 * _ease_io((u - 0.5) * 2))
                    d.polygon([(x0, 0), (W + 300, 0), (W + 300, H), (x0 - 300, H)], fill=rojo + (255,))
                    # franja cyan fina siguiendo el borde
                    d.polygon([(x0 - 24, 0), (x0, 0), (x0 - 300, H), (x0 - 324, H)], fill=cyan + (255,))
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


def historia(etiqueta, gancho, texto, llamado, destino, foto=None, duracion=15.0, musica=None):
    """Historia en video (9:16): la foto se acerca lentamente y los elementos entran animados;
    lleva la pista de música (marca/musica.mp3 por defecto) con fundido al final."""
    fondo, capas = diseno.historia(etiqueta, gancho, texto, llamado, foto=foto, capas=True)
    base = fondo.resize((int(W * 1.10), int(H * 1.10)), Image.LANCZOS)
    # momento de entrada de cada elemento (s) y desplazamiento inicial (dx, dy)
    orden = {"logo": (0.2, (0, -30)), "etiqueta": (0.6, (-60, 0)), "gancho": (0.85, (0, 50)),
             "barra": (1.6, (-120, 0)), "texto": (1.8, (0, 30)), "tarjeta": (2.6, (0, 140))}
    vistos = {}
    plan = []
    for nombre, im, pos in capas:
        t0, desp = orden.get(nombre, (1.0, (0, 30)))
        k = vistos.get(nombre, 0)
        vistos[nombre] = k + 1
        plan.append((im, pos, t0 + 0.14 * k, desp))
    musica = Path(musica(duracion, duracion - 3.0) if callable(musica) else musica or diseno.MARCA_DIR / "musica.mp3")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    audio = ["-stream_loop", "-1", "-i", str(musica)] if musica.exists() else \
        ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    filtro = ["-af", f"afade=t=out:st={duracion - 0.4:.2f}:d=0.4"] if musica.exists() else []
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *audio, "-map", "0:v", "-map", "1:a", *filtro, "-t", f"{duracion:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    bw, bh = base.size
    for f in range(int(duracion * FPS)):
        t = f / FPS
        z = 1.10 - 0.10 * _ease_io(t / duracion)          # se acerca suavemente
        cw, ch = int(W * z), int(H * z)
        x, y = (bw - cw) // 2, (bh - ch) // 2
        img = base.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR).convert("RGBA")
        for im, (px, py), t0, (dx, dy) in plan:
            e = _ease((t - t0) / 0.6)
            if e <= 0:
                continue
            img.alpha_composite(_con_alfa(im, e), (int(px + dx * (1 - e)), int(py + dy * (1 - e))))
        proc.stdin.write(img.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falló al codificar la historia")
    return destino
