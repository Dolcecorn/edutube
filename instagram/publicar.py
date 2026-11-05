#!/usr/bin/env python3
"""Publica en Instagram los posts y reels de la cola usando la API oficial de Meta.

Cola: instagram/cola/<carpeta>/ con:
  - texto.txt            -> descripcion (caption) con hashtags
  - fecha.txt (opcional) -> "2026-11-05 18:00" hora de Chile; sin el, se publica en la proxima pasada
  - los archivos:        1 video (.mp4/.mov) = reel | 1 imagen (.jpg) = post | 2 a 10 = carrusel
  Si el nombre de la carpeta contiene "-historia-", el archivo (imagen o video) se publica como historia.
Se publica en orden alfabetico de carpeta. Al publicarse, la carpeta pasa a instagram/publicados/.

Variables de entorno:
  IG_USER_ID       id de la cuenta de Instagram (profesional)
  IG_ACCESS_TOKEN  token de acceso
  IG_API_HOST      graph.facebook.com (inicio de sesión con Facebook, por defecto) o graph.instagram.com
  MEDIA_BASE_URL   URL publica donde se ven los archivos del repo (para imagenes);
                   por defecto https://raw.githubusercontent.com/<repo>/<commit>
  MAX_POR_PASADA   cuantos publicar como maximo en cada ejecucion (por defecto 1)
  DRY_RUN=1        solo muestra lo que haria
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

API_VERSION = "v23.0"
ZONA = ZoneInfo("America/Santiago")
import perfil

RAIZ = perfil.BASE
COLA = RAIZ / "cola"
PUBLICADOS = RAIZ / "publicados"
VIDEO = {".mp4", ".mov"}
IMAGEN = {".jpg", ".jpeg"}

HOST = os.environ.get("IG_API_HOST", "graph.facebook.com")


def _credencial(nombre):
    """AHP usa IG_USER_ID / IG_ACCESS_TOKEN; otro perfil usa <NOMBRE>_<PERFIL> (ej. IG_USER_ID_LEGALMAIN),
    desde el entorno o desde SECRETOS (JSON con los secrets del repositorio, lo pasa el workflow)."""
    clave = nombre if perfil.NOMBRE == "ahp" else f"{nombre}_{perfil.NOMBRE.upper()}"
    if os.environ.get(clave):
        return os.environ[clave]
    try:
        return json.loads(os.environ.get("SECRETOS") or "{}").get(clave, "")
    except ValueError:
        return ""


USER = _credencial("IG_USER_ID")
TOKEN = _credencial("IG_ACCESS_TOKEN")
DRY = os.environ.get("DRY_RUN") == "1"


def api(metodo, ruta, **params):
    params["access_token"] = TOKEN
    url = f"https://{HOST}/{API_VERSION}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{datos.decode()}")
    else:
        req = urllib.request.Request(url, data=datos, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{metodo} {ruta}: {e.code} {e.read().decode(errors='replace')}") from None


def subir_video(ruta_video, caption, media_type="REELS"):
    """Video subido directo desde el archivo (subida reanudable), sin necesitar URL publica."""
    extra = {"caption": caption, "share_to_feed": "true"} if media_type == "REELS" else {}
    cont = api("POST", f"{USER}/media", media_type=media_type, upload_type="resumable", **extra)
    tam = ruta_video.stat().st_size
    req = urllib.request.Request(cont["uri"], data=ruta_video.read_bytes(), method="POST", headers={
        "Authorization": f"OAuth {TOKEN}", "offset": "0", "file_size": str(tam)})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"subida de video: {e.code} {e.read().decode(errors='replace')}") from None
    return cont["id"]


def url_publica(ruta):
    base = os.environ.get("MEDIA_BASE_URL")
    if not base:
        repo = os.environ.get("GITHUB_REPOSITORY")
        try:  # el commit que realmente está descargado (puede ser más nuevo que GITHUB_SHA)
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True,
                                 check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            sha = os.environ.get("GITHUB_SHA")
        if not (repo and sha):
            sys.exit("Falta MEDIA_BASE_URL para publicar imagenes")
        base = f"https://raw.githubusercontent.com/{repo}/{sha}"
    rel = ruta.resolve().relative_to(perfil.CODIGO.parent).as_posix()
    return f"{base.rstrip('/')}/{urllib.parse.quote(rel)}"


def esperar_listo(cont_id):
    for _ in range(60):  # hasta ~10 min
        estado = api("GET", cont_id, fields="status_code,status").get("status_code")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rechazo el archivo ({cont_id}): {estado}")
        time.sleep(10)
    raise RuntimeError(f"El contenedor {cont_id} no termino de procesarse")


def publicar(carpeta):
    caption = (carpeta / "texto.txt").read_text(encoding="utf-8").strip() if (carpeta / "texto.txt").exists() else ""
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in VIDEO | IMAGEN)
    if not archivos:
        raise RuntimeError("no hay imagen (.jpg) ni video (.mp4/.mov)")
    if len(archivos) > 10 and "-historia-" not in carpeta.name:
        raise RuntimeError("un carrusel admite maximo 10 archivos")
    if len(caption) > 2200:
        raise RuntimeError("el texto supera 2200 caracteres")

    tipo = "reel" if len(archivos) == 1 and archivos[0].suffix.lower() in VIDEO else (
        "post" if len(archivos) == 1 else "carrusel")
    if "-historia-" in carpeta.name:
        tipo = "historia"
    print(f"-> {carpeta.name}: {tipo} con {len(archivos)} archivo(s)")
    if DRY:
        return None

    if tipo == "historia":  # las historias van siempre en video con música (sin caer a imagen muda)
        videos = [a for a in archivos if a.suffix.lower() in VIDEO]
        if not videos:
            raise RuntimeError("la historia no tiene video con música")
        intentos = [lambda: subir_video(videos[0], "", media_type="STORIES"),
                    lambda: api("POST", f"{USER}/media", video_url=url_publica(videos[0]),
                                media_type="STORIES")["id"]] * 2
        ultimo = None
        for n, intento in enumerate(intentos):
            try:
                cont = intento()
                esperar_listo(cont)
                break
            except Exception as e:  # reintenta
                ultimo = e
                print(f"   aviso: {e}", file=sys.stderr)
                time.sleep(10 * (n + 1))
        else:
            raise RuntimeError(f"no se pudo subir la historia en video: {ultimo}")
    elif tipo == "reel":  # subida directa y, si falla, por URL pública (con reintentos)
        intentos = [lambda: subir_video(archivos[0], caption),
                    lambda: api("POST", f"{USER}/media", media_type="REELS", video_url=url_publica(archivos[0]),
                                caption=caption, share_to_feed="true")["id"]] * 2
        ultimo = None
        for n, intento in enumerate(intentos):
            try:
                cont = intento()
                esperar_listo(cont)
                break
            except Exception as e:  # reintenta
                ultimo = e
                print(f"   aviso: {e}", file=sys.stderr)
                time.sleep(10 * (n + 1))
        else:
            raise RuntimeError(f"no se pudo subir el reel: {ultimo}")
    elif tipo == "post":
        cont = api("POST", f"{USER}/media", image_url=url_publica(archivos[0]), caption=caption)["id"]
    else:
        hijos = []
        for a in archivos:
            if a.suffix.lower() in VIDEO:
                raise RuntimeError("por ahora el carrusel solo admite imagenes")
            hijos.append(api("POST", f"{USER}/media", image_url=url_publica(a), is_carousel_item="true")["id"])
        for h in hijos:
            esperar_listo(h)
        cont = api("POST", f"{USER}/media", media_type="CAROUSEL", children=",".join(hijos), caption=caption)["id"]

    esperar_listo(cont)
    return api("POST", f"{USER}/media_publish", creation_id=cont)["id"]


def fecha_de(carpeta):
    f = carpeta / "fecha.txt"
    if not f.exists():
        return None
    return dt.datetime.strptime(f.read_text().strip(), "%Y-%m-%d %H:%M").replace(tzinfo=ZONA)


def main():
    ahora = dt.datetime.now(ZONA)
    maximo = int(os.environ.get("MAX_POR_PASADA", "1"))
    pendientes = sorted((c for c in (COLA.iterdir() if COLA.exists() else []) if c.is_dir() and (fecha_de(c) or ahora) <= ahora),
                        key=lambda c: (fecha_de(c) or ahora, c.name))  # primero la de hora más temprana
    if not pendientes:
        print(f"[{perfil.NOMBRE}] Nada que publicar ahora.")
        return
    if not DRY and not (USER and TOKEN):
        sys.exit(f"[{perfil.NOMBRE}] Faltan las credenciales de Instagram (IG_USER_ID / IG_ACCESS_TOKEN"
                 f"{'' if perfil.NOMBRE == 'ahp' else '_' + perfil.NOMBRE.upper()})")
    errores = 0
    for carpeta in pendientes[:maximo]:
        try:
            media_id = publicar(carpeta)
        except Exception as e:  # sigue con la siguiente y deja la carpeta en la cola
            errores += 1
            print(f"ERROR en {carpeta.name}: {e}", file=sys.stderr)
            continue
        if media_id:
            (carpeta / "publicado.txt").write_text(f"{ahora:%Y-%m-%d %H:%M} id={media_id}\n")
            PUBLICADOS.mkdir(exist_ok=True)
            shutil.move(str(carpeta), PUBLICADOS / carpeta.name)
            print(f"   publicado, id {media_id}")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
