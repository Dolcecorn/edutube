#!/usr/bin/env python3
"""Compone una pista corta, original y libre de derechos para historias y reels (upbeat sobrio).

96 BPM, Do mayor, progresión Do(add9) - Sol/Si - Lam7 - Fa maj7. Capas: colchón suave, arpegio
pulsado (Karplus-Strong), bajo, bombo suave, palmas tenues y hi-hat muy bajo. Sin samples externos:
todo se sintetiza aquí, así que no hay licencias de por medio.

Uso: python3 instagram/musica.py [salida.mp3] [segundos]
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(7)


def nota(n):  # número MIDI -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


# acordes (MIDI) por compás
ACORDES = [
    [48, 55, 60, 62, 64, 67],      # Do add9
    [47, 55, 59, 62, 67, 71],      # Sol/Si
    [45, 52, 57, 60, 64, 67],      # Lam7
    [41, 53, 57, 60, 64, 65],      # Fa maj7
]


def env(n, ataque, caida):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(ataque, 1e-4)) * np.exp(-t / caida)
    return e


def pasa_bajos(x, corte):
    a = np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # un polo; suficiente para suavizar
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def karplus(freq, dur, brillo=0.5):
    n = int(dur * SR)
    p = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, p)
    buf = pasa_bajos(buf, 2000 + 6000 * brillo)
    out = np.empty(n)
    idx = 0
    for i in range(n):
        out[i] = buf[idx]
        nxt = (idx + 1) % p
        buf[idx] = 0.996 * 0.5 * (buf[idx] + buf[nxt])
        idx = nxt
    return out * env(n, 0.003, dur * 0.6)


def colchon(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.12):
            ff = f * 2 ** (det / 12)
            x += np.sin(2 * np.pi * ff * t) + 0.3 * np.sin(4 * np.pi * ff * t) + 0.12 * np.sin(6 * np.pi * ff * t)
    x /= len(freqs) * 2
    ataque = np.minimum(1, t / 0.6)
    salida = np.minimum(1, (dur - t) / 0.5)
    return x * ataque * np.clip(salida, 0, 1)


def bombo(dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 45 + 75 * np.exp(-t / 0.04)
    fase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(fase) * np.exp(-t / 0.12)


def palma(dur=0.2):
    n = int(dur * SR)
    ruido = rng.uniform(-1, 1, n)
    ruido = ruido - pasa_bajos(ruido, 900)  # quita graves
    e = np.zeros(n)
    for d in (0, 0.011, 0.022):  # tres golpecitos muy juntos, como una palma
        i = int(d * SR)
        e[i:] += np.exp(-np.arange(n - i) / SR / 0.03)
    return ruido * e / 3


def hihat(dur=0.05):
    n = int(dur * SR)
    ruido = rng.uniform(-1, 1, n)
    ruido = ruido - pasa_bajos(ruido, 6000)
    return ruido * np.exp(-np.arange(n) / SR / 0.015)


def poner(pista, sonido, t, vol):
    i = int(t * SR)
    if i >= len(pista):
        return
    f = min(len(pista), i + len(sonido))
    pista[i:f] += sonido[: f - i] * vol


def componer(segundos=24.0):
    compases = int(np.ceil(segundos / BAR))
    n = int(compases * BAR * SR)
    pad, arp, bajo, bat = (np.zeros(n) for _ in range(4))
    k, p, h = bombo(), palma(), hihat()
    patron = [0, 2, 4, 3, 5, 4, 2, 3]  # índices del acorde para el arpegio en corcheas
    for c in range(compases):
        ac = ACORDES[c % 4]
        t0 = c * BAR
        poner(pad, colchon([nota(x) for x in ac[1:5]], BAR + 0.4), t0, 1.0)
        for j, ix in enumerate(patron):  # arpegio en corcheas, una octava arriba
            poner(arp, karplus(nota(ac[ix] + 12), BEAT * 1.2, brillo=0.4), t0 + j * BEAT / 2,
                  0.9 if j % 2 == 0 else 0.6)
        for j in range(8):  # bajo en corcheas, acentuado en el tiempo
            nb = int(BEAT / 2 * SR * 0.9)
            tb = np.arange(nb) / SR
            s = np.sin(2 * np.pi * nota(ac[0] - 12) * tb) * np.exp(-tb / 0.18) * np.minimum(1, tb / 0.005)
            poner(bajo, s, t0 + j * BEAT / 2, 1.0 if j % 2 == 0 else 0.55)
        if c >= 1:  # la batería entra en el segundo compás
            for b in range(4):
                poner(bat, k, t0 + b * BEAT, 0.9 if b in (0, 2) else 0.55)
                if b in (1, 3):
                    poner(bat, p, t0 + b * BEAT, 0.35)
            for j in range(8):
                poner(bat, h, t0 + j * BEAT / 2 + BEAT / 4, 0.12)
    mezcla = 0.30 * pad + 0.32 * arp + 0.38 * bajo + 0.45 * bat
    # reverb sencilla para el colchón y el arpegio (ecos difusos)
    rev = np.zeros_like(mezcla)
    fuente = 0.3 * pad + 0.32 * arp
    for d, g in ((0.031, 0.35), (0.047, 0.3), (0.071, 0.25), (0.113, 0.2), (0.173, 0.15)):
        i = int(d * SR)
        rev[i:] += fuente[:-i] * g
    mezcla += 0.5 * rev
    mezcla = mezcla[: int(segundos * SR)]
    t = np.arange(len(mezcla)) / SR
    mezcla *= np.clip((segundos - t) / 1.5, 0, 1) * np.clip(t / 0.3, 0, 1)  # entrada y salida
    mezcla /= np.max(np.abs(mezcla)) + 1e-9
    return np.stack([mezcla, np.roll(mezcla, 220) * 0.98], axis=1)  # leve apertura estéreo


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
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5",
                        "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "192k", str(destino)], check=True)
    return destino


if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "marca" / "musica.mp3")
    seg = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    print(guardar(componer(seg), salida))
