#!/usr/bin/env python3
"""Compone una pista original y libre de derechos para historias y reels: deep house suave y sobrio.

121 BPM, La menor. Acordes tipo Rhodes (FM) Lam9 - Rem9 - Fa maj7 - Mim7 con filtro cálido y "bombeo"
de sidechain, bajo sub sincopado, bombo redondo en negras, hi-hat abierto a contratiempo, shaker
muy bajo y una palma lejana. Sin samples externos: todo se sintetiza aquí.

Uso: python3 instagram/musica.py [salida.mp3] [segundos]
"""
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

# voicings (MIDI): raíz para el bajo + acorde en registro medio
ACORDES = [
    (45, [57, 60, 64, 67, 71]),   # Lam9  (La Do Mi Sol Si)
    (50, [57, 60, 62, 65, 69]),   # Rem9  (La Do Re Fa La) - voicing cerrado
    (41, [57, 60, 64, 65, 69]),   # Fa maj7 (La Do Mi Fa La)
    (40, [55, 59, 62, 64, 67]),   # Mim7 (Sol Si Re Mi Sol)
]


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
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 48 + 60 * np.exp(-t / 0.03)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    clic = rng.uniform(-1, 1, n) * np.exp(-t / 0.002) * 0.08
    return s + clic


def ruido_filtrado(dur, alto, caida, bajo=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    r = filtro(rng.uniform(-1, 1, n), bajo=bajo, alto=alto)
    return r / (np.max(np.abs(r)) + 1e-9) * np.exp(-t / caida)


def poner(pista, sonido, t, vol=1.0):
    i = int(round(t * SR))
    if i >= len(pista):
        return
    f = min(len(pista), i + len(sonido))
    pista[i:f] += sonido[: f - i] * vol


def componer(segundos=60.0):
    compases = int(np.ceil(segundos / BAR)) + 1
    n = int(compases * BAR * SR)
    acordes, bajo, bat, perc = (np.zeros(n) for _ in range(4))
    k = bombo()
    hat = ruido_filtrado(0.22, alto=7000, caida=0.07)
    shk = ruido_filtrado(0.06, alto=5000, caida=0.018, bajo=11000)
    palma = ruido_filtrado(0.35, alto=1200, caida=0.09, bajo=5000)
    # patrón de bajo sincopado (en semicorcheas): (posición, duración en semicorcheas, octava)
    patron_bajo = [(0, 3, 0), (3, 1, 0), (6, 2, 12), (10, 2, 0), (14, 2, 0)]
    semi = BEAT / 4
    for c in range(compases):
        raiz, voces = ACORDES[c % 4]
        t0 = c * BAR
        # acordes: un golpe largo en el 1 y otro corto anticipando el 3 ("y" del 2), muy al estilo deep house
        for tt, dur, vol in ((0.0, BAR * 0.95, 0.9), (BEAT * 1.5, BEAT * 1.4, 0.45)):
            for v in voces:
                poner(acordes, rhodes(hz(v), dur), t0 + tt + rng.uniform(0, 0.006), vol)
        for pos, d, octv in patron_bajo:
            nn = int(d * semi * SR * 0.92)
            tb = np.arange(nn) / SR
            f = hz(raiz - 12 + octv)
            s = (np.sin(2 * np.pi * f * tb) + 0.15 * np.sin(4 * np.pi * f * tb))
            s *= np.minimum(1, tb / 0.004) * np.minimum(1, (nn / SR - tb) / 0.02)
            poner(bajo, s, t0 + pos * semi, 1.0)
        intro = c < 2  # dos compases de intro: solo acordes y shaker
        for b in range(4):
            tb = t0 + b * BEAT
            if not intro:
                poner(bat, k, tb, 1.0)
                poner(perc, hat, tb + BEAT / 2, 0.22)               # hi-hat abierto a contratiempo
                if b in (1, 3):
                    poner(perc, palma, tb, 0.16)                     # palma lejana
            for s16 in range(4):
                poner(perc, shk, tb + s16 * semi + rng.uniform(-0.004, 0.004),
                      0.10 if s16 % 2 else 0.05)                     # shaker con algo de swing humano

    # color: acordes cálidos y oscuros; bajo solo graves; percusión sin graves
    acordes = filtro(acordes, bajo=1800)
    bajo = filtro(bajo, bajo=220)
    perc = filtro(perc, alto=3000)

    # sidechain: los acordes y el bajo "respiran" con el bombo
    t = np.arange(n) / SR
    fase = (t % BEAT) / BEAT
    bombeo = 0.55 + 0.45 * np.minimum(1, fase / 0.45) ** 1.5
    bombeo[: int(2 * BAR * SR)] = 1.0  # sin bombeo en la intro
    acordes *= bombeo
    bajo *= 0.6 + 0.4 * bombeo

    # reverb difusa para los acordes y la palma
    rev = np.zeros(n)
    fuente = acordes * 0.5 + perc * 0.3
    for d, g in ((0.029, .32), (0.041, .3), (0.059, .27), (0.083, .24), (0.127, .2), (0.191, .15), (0.263, .1)):
        i = int(d * SR)
        rev[i:] += fuente[:-i] * g
    rev = filtro(rev, bajo=4000, alto=200)

    mezcla = 0.42 * acordes + 0.55 * bajo + 0.62 * bat + 0.5 * perc + 0.35 * rev
    mezcla = mezcla[: int(segundos * SR)]
    t = np.arange(len(mezcla)) / SR
    mezcla *= np.clip(t / 1.0, 0, 1) * np.clip((segundos - t) / 2.5, 0, 1)
    mezcla = np.tanh(1.3 * mezcla / (np.max(np.abs(mezcla)) + 1e-9)) / np.tanh(1.3)  # saturación suave
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


if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "marca" / "musica.mp3")
    seg = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    print(guardar(componer(seg), salida))
