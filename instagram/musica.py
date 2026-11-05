#!/usr/bin/env python3
"""Compone una pista original y libre de derechos para historias y reels: deep house suave y sobrio.

121 BPM, La menor. Acordes tipo Rhodes (FM) Lam9 - Rem9 - Fa maj7 - Mim7 en segundo plano, con filtro
cálido y "bombeo" suave de sidechain; bajo sub sincopado; bombo claro en negras y caja en 2 y 4;
hi-hat a contratiempo, sin siseo de fondo. Termina con un remate y un golpe final (bombo, platillo suave
y acorde de tónica) que se alinea con el logo del cierre. Sin samples externos: todo se sintetiza aquí.

Estilo "corporativo" (marca.json "estilo_musica", ej. LegalMain): misma base pero más lenta (100-106 BPM),
batería mucho más tenue (sin palmas, caja suave tipo aro), bombeo casi imperceptible, bajo largo y acordes
más presentes: sobrio, para rubros profesionales.

Cada publicación usa una variante distinta (tonalidad, tempo, progresión, ritmo de acordes y bajo),
elegida a partir del nombre de su carpeta; sin semilla se obtiene la pista base aprobada.

Uso: python3 instagram/musica.py [salida.mp3] [segundos] [semilla]
"""
import hashlib
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 121
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(11)

# voicings (MIDI, en La menor): raíz para el bajo + acorde en registro medio
LAm9 = (45, [57, 60, 64, 67, 71])
REm9 = (50, [57, 60, 62, 65, 69])
FAmaj7 = (41, [57, 60, 64, 65, 69])
MIm7 = (40, [55, 59, 62, 64, 67])
DOmaj9 = (48, [55, 59, 62, 64, 67])
SOL69 = (43, [55, 57, 59, 62, 64])
FAmaj9 = (41, [57, 60, 64, 67])
REm9b = (38, [57, 60, 62, 65, 69])
PROGRESIONES = [
    [LAm9, REm9, FAmaj7, MIm7],      # la aprobada por Eleva (variante 0)
    [LAm9, FAmaj7, DOmaj9, SOL69],
    [LAm9, REm9, LAm9, MIm7],
    [FAmaj9, MIm7, REm9b, LAm9],
    [REm9, LAm9, FAmaj7, SOL69],
]
ACORDES = PROGRESIONES[0]
# ritmo de acordes por compás: (inicio en tiempos, duración en tiempos, volumen)
RITMOS_ACORDES = [
    [(0, 3.8, 0.9), (1.5, 1.4, 0.45)],
    [(0, 1.4, 0.8), (1.5, 1.0, 0.5), (2.5, 1.4, 0.6)],
    [(0, 7.6, 0.85)],                       # acorde largo (dura dos compases si se repite)
    [(0.5, 1.2, 0.6), (2.5, 1.2, 0.6), (3.5, 0.45, 0.4)],
]
# bajo en semicorcheas: (posición, duración, octava)
PATRONES_BAJO = [
    [(0, 3, 0), (3, 1, 0), (6, 2, 12), (10, 2, 0), (14, 2, 0)],
    [(2, 2, 0), (6, 2, 0), (10, 2, 0), (14, 2, 12)],          # bajo a contratiempo, muy house
    [(0, 2, 0), (4, 1, 0), (7, 2, 0), (11, 1, 12), (12, 3, 0)],
]
PATRONES_BAJO_CORP = [
    [(0, 6, 0), (8, 6, 0)],                                   # notas largas, sin síncopa
    [(0, 3, 0), (6, 2, 0), (8, 6, 0)],
]
# mezcla por estilo: bombo, caja, hi-hat, profundidad del bombeo, acordes, percusión
MEZCLA = {
    "deep_house": dict(bombo=1.0, caja=0.42, hat=0.22, bombeo=0.32, acordes=0.26, perc=0.45),
    "corporativo": dict(bombo=0.55, caja=0.16, hat=0.13, bombeo=0.12, acordes=0.36, perc=0.3),
}


def estilo_marca():
    """Estilo de música del perfil activo (marca.json "estilo_musica"); por defecto deep house."""
    try:
        import perfil
        import json
        m = json.loads((perfil.BASE / "marca" / "marca.json").read_text(encoding="utf-8"))
        return m.get("estilo_musica") or "deep_house"
    except Exception:
        return "deep_house"


def hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def filtro(x, bajo=None, alto=None):
    """Filtro por FFT (rápido para pistas largas)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if bajo:   # pasa bajos suave (2º orden aprox.)
        g *= 1 / np.sqrt(1 + (f / bajo) ** 4)
    if alto:   # pasa altos suave
        g *= 1 / np.sqrt(1 + (alto / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X * g, len(x))


def rhodes(freq, dur):
    """Piano eléctrico por FM: cuerpo cálido + un leve 'tine' al ataque."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    ind = 1.6 * np.exp(-t / 0.35) + 0.25
    cuerpo = np.sin(2 * np.pi * freq * t + ind * np.sin(2 * np.pi * freq * t))
    tine = 0.12 * np.sin(2 * np.pi * freq * 14 * t) * np.exp(-t / 0.05)
    trem = 1 + 0.06 * np.sin(2 * np.pi * 4.5 * t)
    env = np.minimum(1, t / 0.008) * np.exp(-t / 1.4) * np.clip((dur - t) / 0.06, 0, 1)
    return (cuerpo + tine) * env * trem


def bombo():
    """Bombo redondo y claro: cuerpo grave con caída de tono y un ataque limpio (sin ruido)."""
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 52 + 95 * np.exp(-t / 0.025)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    ataque = np.sin(2 * np.pi * 1600 * t) * np.exp(-t / 0.0025) * 0.25   # "clic" tonal, sin ruido
    return np.tanh(1.4 * (s + ataque)) / np.tanh(1.4)


def caja():
    """Caja suave pero definida (tipo house): tono corto + ruido de banda media que se apaga rápido."""
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    tono = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.045)
    r = filtro(rng.uniform(-1, 1, n), bajo=6500, alto=1400)
    r = r / (np.max(np.abs(r)) + 1e-9) * np.exp(-t / 0.075)
    return 0.55 * tono + 0.7 * r


def ruido_filtrado(dur, alto, caida, bajo=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    r = filtro(rng.uniform(-1, 1, n), bajo=bajo, alto=alto)
    return r / (np.max(np.abs(r)) + 1e-9) * np.exp(-t / caida)


def poner(pista, sonido, t, vol=1.0):
    i = int(round(t * SR))
    if i < 0:
        sonido, i = sonido[-i:], 0
    if i >= len(pista):
        return
    f = min(len(pista), i + len(sonido))
    pista[i:f] += sonido[: f - i] * vol


def variante(semilla, estilo="deep_house"):
    """Parámetros de una variante. semilla=None da la pista base aprobada; otra semilla da otra
    canción del mismo estilo (tonalidad, tempo, progresión, ritmo de acordes y bajo distintos)."""
    if semilla is None:
        return dict(bpm=121, transp=0, prog=0, ritmo=0, bajo=0, hat=True, palma=True)
    r = np.random.default_rng(int(hashlib.sha256(str(semilla).encode()).hexdigest()[:8], 16))
    if estilo == "corporativo":
        return dict(bpm=int(r.choice([100, 102, 104, 106])), transp=int(r.integers(-4, 4)),
                    prog=int(r.choice([0, 1, 3, 4])), ritmo=int(r.choice([0, 2])),
                    bajo=int(r.integers(0, len(PATRONES_BAJO_CORP))), hat=True, palma=False, estilo=estilo)
    return dict(bpm=int(r.choice([118, 119, 120, 121, 122, 123, 124])), transp=int(r.integers(-4, 4)),
                prog=int(r.integers(0, len(PROGRESIONES))), ritmo=int(r.integers(0, len(RITMOS_ACORDES))),
                bajo=int(r.integers(0, len(PATRONES_BAJO))), hat=bool(r.random() < 0.8),
                palma=bool(r.random() < 0.6))


def componer(segundos=60.0, semilla=None, golpe=None, estilo=None):
    """Compone la pista. golpe = segundo en que cae el final (acorde de cierre + bombo), pensado para que
    coincida con la aparición del logo; la pista se alinea para que ese momento caiga en un compás."""
    global BPM, BEAT, BAR, rng
    estilo = estilo or estilo_marca()
    v = variante(semilla if semilla is not None or estilo == "deep_house" else "base", estilo)
    mz = MEZCLA.get(v.get("estilo", "deep_house"), MEZCLA["deep_house"])
    BPM = v["bpm"]
    BEAT = 60 / BPM
    BAR = 4 * BEAT
    rng = np.random.default_rng(11 if semilla is None else v["bpm"] * 1000 + v["prog"] * 100 + v["ritmo"])
    prog = [(raiz + v["transp"], [x + v["transp"] for x in voces]) for raiz, voces in PROGRESIONES[v["prog"]]]
    tonica = (LAm9[0] + v["transp"], [x + v["transp"] for x in LAm9[1]])
    if golpe is None:
        golpe = max(BAR, segundos - 3.0)
    golpe = min(golpe, segundos - 0.5)
    compases = int(np.floor(golpe / BAR))
    inicio = golpe - compases * BAR        # el primer compás empieza aquí; antes queda un compás de entrada
    n = int(segundos * SR)
    acordes, bajo, bat, perc, cola = (np.zeros(n) for _ in range(5))
    k, sn = bombo(), caja()
    hat_abierto = filtro(ruido_filtrado(0.16, alto=7500, caida=0.045), bajo=11000)
    hat_cerrado = filtro(ruido_filtrado(0.04, alto=8000, caida=0.012), bajo=11000)
    patron_bajo = (PATRONES_BAJO_CORP if v.get("estilo") == "corporativo" else PATRONES_BAJO)[v["bajo"]]
    ritmo = RITMOS_ACORDES[v["ritmo"]]
    semi = BEAT / 4
    for c in range(-1, compases):
        raiz, voces = prog[c % 4]
        t0 = inicio + c * BAR
        ultimo = c == compases - 1
        for tt, dur, vol in ritmo:
            if dur > 4 and c % 2:  # acorde largo: se toca cada dos compases
                continue
            dur = min(dur, (golpe - t0) / BEAT - tt)   # nada se cuela sobre el golpe final
            if dur <= 0.1:
                continue
            for nv in voces:
                poner(acordes, rhodes(hz(nv), dur * BEAT), t0 + tt * BEAT + rng.uniform(0, 0.006), vol)
        for pos, d, octv in patron_bajo:
            if ultimo and pos >= 12:   # el bajo calla en el último tiempo para dar aire al cierre
                continue
            nn = int(d * semi * SR * 0.92)
            tb = np.arange(nn) / SR
            f = hz(raiz - 12 + octv)
            s = (np.sin(2 * np.pi * f * tb) + 0.15 * np.sin(4 * np.pi * f * tb))
            s *= np.minimum(1, tb / 0.004) * np.minimum(1, (nn / SR - tb) / 0.02)
            poner(bajo, s, t0 + pos * semi, 1.0)
        intro = c < 1  # entrada: solo acordes y hi-hat suave
        for b in range(4):
            tb = t0 + b * BEAT
            if not intro and not (ultimo and b == 3):
                poner(bat, k, tb, mz["bombo"])
            if not intro and b in (1, 3):
                poner(bat, sn, tb, mz["caja"])                          # caja marcada en 2 y 4
            if v["hat"] or not intro:
                poner(perc, hat_abierto, tb + BEAT / 2, mz["hat"] if not intro else 0.12)   # contratiempo
            if not intro and v["palma"]:
                poner(perc, hat_cerrado, tb + 3 * semi, 0.10)           # semicorchea suave antes del tiempo
        if ultimo:  # pequeño remate de caja que anuncia el final
            for j, vol in ((13, 0.16), (14, 0.22), (15, 0.3)):
                poner(bat, sn, t0 + j * semi, vol * mz["caja"] / 0.42)

    # subida suave (ruido muy filtrado) en los dos compases previos al golpe
    nr = int(2 * BAR * SR)
    tr = np.arange(nr) / SR
    subida = filtro(rng.uniform(-1, 1, nr), bajo=5000, alto=900) * (tr / tr[-1]) ** 2.5
    poner(perc, subida / (np.max(np.abs(subida)) + 1e-9), golpe - 2 * BAR, 0.10)

    # golpe final: bombo, platillo suave, sub y acorde de tónica que se queda sonando con reverb
    resto = segundos - golpe
    poner(bat, k, golpe, 1.1)
    plat = filtro(ruido_filtrado(min(3.0, resto + 0.5), alto=3500, caida=0.9), bajo=9000)
    poner(cola, plat, golpe, 0.16)
    raiz, voces = tonica
    for j, nv in enumerate(voces + [voces[0] + 12, voces[2] + 12]):
        poner(cola, rhodes(hz(nv), resto + 0.3) * (0.9 if j < len(voces) else 0.45), golpe + 0.012 * j, 1.0)
    nb = int((resto + 0.3) * SR)
    tb = np.arange(nb) / SR
    sub = np.sin(2 * np.pi * hz(raiz - 12) * tb) * np.minimum(1, tb / 0.01) * np.exp(-tb / 1.6)
    poner(bajo, sub, golpe, 1.1)

    # color: acordes cálidos y oscuros; bajo solo graves; percusión sin graves ni siseo
    acordes = filtro(acordes, bajo=1600)
    cola = filtro(cola, bajo=3200)
    bajo = filtro(bajo, bajo=220)
    perc = filtro(perc, alto=3000, bajo=10500)

    # sidechain: los acordes y el bajo "respiran" con el bombo (más suave que antes)
    t = np.arange(n) / SR
    fase = ((t - inicio) % BEAT) / BEAT
    bombeo = 1 - mz["bombeo"] + mz["bombeo"] * np.minimum(1, fase / 0.45) ** 1.5
    bombeo[: int(max(0, inicio + BAR) * SR)] = 1.0   # sin bombeo en la entrada
    bombeo[int(golpe * SR):] = 1.0
    acordes *= bombeo
    bajo *= 0.7 + 0.3 * bombeo

    # reverb difusa solo para acordes y cierre (la batería queda seca y clara)
    rev = np.zeros(n)
    fuente = acordes * 0.5 + cola * 0.7 + bat * 0.04
    for d, g in ((0.029, .32), (0.041, .3), (0.059, .27), (0.083, .24), (0.127, .2), (0.191, .15),
                 (0.263, .1), (0.37, .07), (0.52, .05)):
        i = int(d * SR)
        rev[i:] += fuente[:-i] * g
    rev = filtro(rev, bajo=3500, alto=250)

    mezcla = mz["acordes"] * acordes + 0.34 * cola + 0.55 * bajo + 0.85 * bat + mz["perc"] * perc + 0.3 * rev
    mezcla *= np.clip(t / 0.6, 0, 1) * np.clip((segundos - t) / 0.4, 0, 1)
    mezcla = np.tanh(1.15 * mezcla / (np.max(np.abs(mezcla)) + 1e-9)) / np.tanh(1.15)
    izq = mezcla
    der = np.roll(mezcla, 260) * 0.97 + 0.03 * mezcla
    return np.stack([izq, der], axis=1)


def guardar(audio, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "m.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((audio * 0.9 * 32767).astype("<i2").tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-17:TP=-1.5",
                        "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "192k", str(destino)], check=True)
    return destino


def pista(semilla, segundos, destino, golpe=None, estilo=None):
    """Compone y guarda la variante de una publicación (cada carpeta usa su nombre como semilla).
    golpe: segundo del cierre (por ejemplo, cuando aparece el logo)."""
    return guardar(componer(segundos, semilla, golpe, estilo), destino)


if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "marca" / "musica.mp3")
    seg = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    semilla = sys.argv[3] if len(sys.argv) > 3 else None
    est = sys.argv[4] if len(sys.argv) > 4 else None
    print(semilla, variante(semilla, est or estilo_marca()))
    print(guardar(componer(seg, semilla, estilo=est), salida))
