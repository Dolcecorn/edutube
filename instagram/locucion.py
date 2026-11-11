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


def _preparar(texto):
    # el nombre de la empresa se deletrea: A, H, P (si no, el modelo lo lee "ap")
    texto = re.sub(r"\bAHP\b", "A, Hache, Pe", texto)
    # pronunciaciones propias de la marca (marca.json "pronunciacion": {"LegalMain": "Ligalmein"})
    for palabra, dicha in (diseno.marca().get("pronunciacion") or {}).items():
        texto = re.sub(re.escape(palabra).replace("\\ ", "\\s*"), dicha, texto, flags=re.IGNORECASE)
    texto = texto.strip()
    if texto and texto[-1] not in ".!?…":
        texto += "."   # sin punto final el modelo tiende a seguir "murmurando"
    return texto


_oido = None


def _normalizar(t):
    """Texto comparable: minúsculas, sin tildes ni signos; las formas de decir la sigla quedan como "ahp"."""
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\ba\s*(hache|h|ache)\s*(pe|p)\b", " ahp ", t)
    t = re.sub(r"\bahache\s*pe\b|\ba\s+h\s+p\b|\bahachepe\b", " ahp ", t)
    return t.split()


def _verificar(ruta, esperado):
    """Escucha el audio con un reconocedor de voz (faster-whisper) y lo compara con el texto pedido.
    Devuelve (ok, puntaje, lo_que_se_oyó). Si el reconocedor no está instalado, acepta el audio."""
    global _oido
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return True, 1.0, ""
    if _oido is None:
        _oido = WhisperModel("small", device="cpu", compute_type="int8")
    # el audio se decodifica con ffmpeg (no con PyAV, cuya versión choca con la que fija chatterbox)
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-ac", "1", "-ar", "16000",
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(datos, np.float32)
    segmentos, _ = _oido.transcribe(audio, language="es", beam_size=5, vad_filter=False)
    oido = " ".join(s.text for s in segmentos).strip()
    import difflib
    a, b = _normalizar(esperado), _normalizar(oido)
    puntaje = difflib.SequenceMatcher(None, a, b).ratio()
    sigla_ok = a.count("ahp") == b.count("ahp")
    return sigla_ok and puntaje >= 0.8, puntaje + (0.5 if sigla_ok else 0), oido


def decir(texto, destino, intentos=6):
    """Sintetiza un texto con la voz de referencia y lo guarda en destino (wav 44.1 kHz). Devuelve la duración.
    Cada toma se escucha con un reconocedor de voz: si no dice lo pedido (por ejemplo "Ambulancias Hache" en vez
    de "A, Hache, Pe", o un ruido raro), se genera otra toma. Se queda con la mejor."""
    import shutil
    esperado = _preparar(texto)
    mejor = None
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(intentos):
            toma = Path(tmp) / f"t{k}.wav"
            dur = _sintetizar(esperado, toma, semilla=1000 + k * 97)
            ok, puntaje, oido = _verificar(toma, esperado)
            print(f"  voz toma {k + 1}: {'OK' if ok else 'repetir'} ({puntaje:.2f}) «{oido}»", flush=True)
            if mejor is None or puntaje > mejor[0]:
                mejor = (puntaje, toma, dur)
            if ok:
                break
        else:
            if "AHP" in texto:
                # el modelo no logra decir la sigla en esta frase: se dice sin ella antes de dejar un error
                alt = re.sub(r"\bAmbulancias AHP\b", "nuestro equipo", texto)
                alt = re.sub(r"\bAHP\b", "nuestro equipo", alt)
                print(f"  sin sigla: «{alt}»", flush=True)
                return decir(alt, destino, intentos)
            print(f"  AVISO: ninguna toma salió perfecta para «{texto}»; se usa la mejor", flush=True)
        shutil.copy(mejor[1], destino)
        return mejor[2]


def _sintetizar(texto, destino, semilla=None):
    import torchaudio
    m = _cargar()
    if semilla is not None:
        import torch
        torch.manual_seed(semilla)
    marca = diseno.marca()
    ajuste = {"exaggeration": 0.45, "cfg_weight": 0.5, "temperature": 0.7, **(marca.get("voz_ajustes") or {})}
    if marca.get("voz_por_frases"):
        # cada frase por separado y unidas con una pausa breve: ritmo más natural que una tirada larga
        import torch
        frases = [f.strip() for f in re.findall(r"[^.!?…]+[.!?…]+", texto) if f.strip()] or [texto]
        pausa = torch.zeros(1, int(m.sr * float(marca.get("pausa_frases", 0.3))))
        partes = []
        for f in frases:
            partes += [m.generate(f, language_id="es", audio_prompt_path=str(REFERENCIA), **ajuste), pausa]
        wav = torch.cat(partes[:-1], dim=1)
    else:
        wav = m.generate(texto, language_id="es", audio_prompt_path=str(REFERENCIA), **ajuste)
    vel = float(diseno.marca().get("velocidad_voz", 1.0))   # < 1: habla más pausada (sin cambiar el tono)
    tempo = f"atempo={vel:.3f}," if abs(vel - 1) > 0.005 else ""
    with tempfile.TemporaryDirectory() as tmp:
        crudo = Path(tmp) / "v.wav"
        torchaudio.save(str(crudo), wav, m.sr)
        # limpieza suave: quita graves de ruido, compresión leve y volumen parejo de locutor
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(crudo), "-af",
                        "highpass=f=80,silenceremove=start_periods=1:start_threshold=-45dB,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        f"{tempo}acompressor=threshold=-20dB:ratio=2.5:attack=5:release=120,loudnorm=I=-16:TP=-1.5",
                        "-ar", str(SR), "-ac", "1", str(destino)], check=True)
    limpio = _quitar_ruidos(_leer_wav(destino))
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(limpio, -1, 1) * 32767).astype("<i2").tobytes())
    return len(limpio) / SR


def _quitar_ruidos(a, sr=SR):
    """Quita los ruidos que a veces agrega el modelo de voz: murmullos nasales ("nmm"), respiraciones o
    sílabas sueltas al inicio, al final o aisladas entre frases. Se detectan como tramos de sonido cortos y
    separados del habla por silencio, o tramos con energía casi solo en graves (zumbido nasal). Después se
    recortan los silencios de los extremos dejando 80 ms."""
    if len(a) < sr // 5:
        return a
    a = a.astype(np.float32).copy()
    hop, win = sr // 100, int(sr * 0.025)
    n = max(1, (len(a) - win) // hop)
    db = np.array([10 * np.log10(np.mean(a[i * hop:i * hop + win] ** 2) + 1e-10) for i in range(n)])
    activo = db > db.max() - 32
    # tramos activos, uniendo huecos menores a 120 ms
    tramos, i = [], 0
    while i < n:
        if activo[i]:
            j = i
            while j < n and (activo[j] or (j + 12 < n and activo[j:j + 12].any())):
                j += 1
            tramos.append([i, j])
            i = j
        else:
            i += 1
    if not tramos:
        return a

    def centroide(x):
        X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        f = np.fft.rfftfreq(len(x), 1 / sr)
        return float((X * f).sum() / (X.sum() + 1e-9))

    largo_max = max(j - i for i, j in tramos)
    quitar = []
    for k, (i, j) in enumerate(tramos):
        dur = (j - i) / 100
        gap_ant = (i - tramos[k - 1][1]) / 100 if k else 9
        gap_sig = (tramos[k + 1][0] - j) / 100 if k + 1 < len(tramos) else 9
        x = a[i * hop:j * hop + win]
        borde = k == 0 or k == len(tramos) - 1
        # en los extremos basta una pausa corta; entre frases se exige una pausa larga (no borrar palabras)
        corto_aislado = (j - i) < largo_max and (
            (borde and dur < 0.2 and min(gap_ant, gap_sig) >= 0.2) or
            (not borde and dur < 0.25 and min(gap_ant, gap_sig) >= 0.35))
        zumbido = dur < 0.9 and centroide(x) < 380
        if corto_aislado or zumbido:
            quitar.append((i, j))
    for i, j in quitar:
        ini, fin = max(0, i * hop - win), min(len(a), j * hop + win)
        a[ini:fin] = 0
    # recortar extremos
    vivos = [t for t in tramos if tuple(t) not in quitar]
    if not vivos:
        return a
    ini = max(0, vivos[0][0] * hop - int(0.08 * sr))
    fin = min(len(a), vivos[-1][1] * hop + win + int(0.08 * sr))
    a = a[ini:fin]
    f = min(len(a), int(0.06 * sr))
    a[-f:] *= np.linspace(1, 0, f)                       # cierre suave, sin chasquido
    return a


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
