"""Locución (voz en off) para los reels con una voz chilena clonada.

Usa Chatterbox Multilingual (Resemble AI, licencia MIT), que habla español y clona una voz a partir de una
grabación corta de referencia: marca/voz/referencia.wav (20-30 s, una sola persona, con su autorización).
Corre en CPU (GitHub Actions). Si no hay referencia o el motor no está instalado, los reels salen sin voz.

Uso de prueba: python3 instagram/locucion.py "Texto a decir" salida.wav
"""
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

import diseno

REFERENCIA = diseno.MARCA_DIR / "voz" / "referencia.wav"
SR = 44100
_modelo = None


def disponible():
    if not REFERENCIA.exists():
        return False
    try:
        import chatterbox  # noqa: F401
    except ImportError:
        return False
    return True


def _cargar():
    global _modelo
    if _modelo is None:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        torch.set_num_threads(max(1, torch.get_num_threads()))
        # algunos pesos se guardaron en GPU: en CPU hay que mapearlos al cargar
        cargar_original = torch.load
        torch.load = lambda *a, **k: cargar_original(*a, **{**k, "map_location": torch.device("cpu")})
        try:
            _modelo = ChatterboxMultilingualTTS.from_pretrained(device=torch.device("cpu"))
        finally:
            torch.load = cargar_original
    return _modelo


def _leer_wav(ruta):
    """Lee cualquier audio como mono float32 a 44.1 kHz (vía ffmpeg)."""
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-ac", "1", "-ar", str(SR),
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(datos, np.float32)


def decir(texto, destino):
    """Sintetiza un texto con la voz de referencia y lo guarda en destino (wav 44.1 kHz). Devuelve la duración."""
    import torchaudio
    m = _cargar()
    # el nombre de la empresa se deletrea: A, H, P (si no, el modelo lo lee "ap")
    texto = re.sub(r"\bAHP\b", "A, hache, pe", texto)
    # pronunciaciones propias de la marca (marca.json "pronunciacion": {"LegalMain": "Ligalmein"})
    for palabra, dicha in (diseno.marca().get("pronunciacion") or {}).items():
        texto = re.sub(re.escape(palabra).replace("\\ ", "\\s*"), dicha, texto, flags=re.IGNORECASE)
    wav = m.generate(texto, language_id="es", audio_prompt_path=str(REFERENCIA),
                     exaggeration=0.45, cfg_weight=0.5, temperature=0.7)
    with tempfile.TemporaryDirectory() as tmp:
        crudo = Path(tmp) / "v.wav"
        torchaudio.save(str(crudo), wav, m.sr)
        # limpieza suave: quita graves de ruido, compresión leve y volumen parejo de locutor
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(crudo), "-af",
                        "highpass=f=80,silenceremove=start_periods=1:start_threshold=-45dB,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "acompressor=threshold=-20dB:ratio=2.5:attack=5:release=120,loudnorm=I=-16:TP=-1.5",
                        "-ar", str(SR), "-ac", "1", str(destino)], check=True)
    with wave.open(str(destino)) as w:
        return w.getnframes() / w.getframerate()


def pista(clips, total, destino):
    """Une las locuciones de cada escena en una sola pista. clips: [(inicio_s, ruta_wav)]."""
    voz = np.zeros(int(total * SR), np.float32)
    for inicio, ruta in clips:
        a = _leer_wav(ruta)
        i = int(inicio * SR)
        f = min(len(voz), i + len(a))
        if f > i:
            voz[i:f] += a[: f - i]
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(voz, -1, 1) * 32767).astype("<i2").tobytes())
    return destino


if __name__ == "__main__":
    print(decir(sys.argv[1], sys.argv[2]))
