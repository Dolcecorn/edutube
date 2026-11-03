#!/usr/bin/env python3
"""Genera la publicación del día: un modelo de IA (OpenAI o Claude) escribe el contenido y diseno.py dibuja las gráficas o el reel.

Alterna post -> reel -> carrusel. Deja la carpeta lista en instagram/cola/ (o en la carpeta que se indique
con --salida) con fecha.txt para la hora de publicación de marca.json.

Variables: OPENAI_API_KEY (usa OpenAI) o ANTHROPIC_API_KEY (usa Claude); si están las dos, se usa OpenAI.
Opcional: TIPO=post|reel|carrusel para forzar el tipo; TEMA=... para pedir un tema. Los modelos se eligen en marca.json.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

import calendario
import diseno
import musica
import video

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / "estado.json"
ZONA = ZoneInfo("America/Santiago")
ORDEN = ["post", "reel", "carrusel"]
LAMINAS = {"post": "exactamente 1 lámina", "carrusel": "entre 5 y 7 láminas (la primera es la portada)",
           "historia": "1 imagen vertical",
           "reel": "entre 4 y 6 escenas (la primera es el gancho; la última invita a seguir la cuenta o a contactar)"}


class Lamina(BaseModel):
    titulo: str = Field(description="Frase corta e impactante, máximo 9 palabras")
    texto: str = Field(description="Texto de apoyo, máximo 35 palabras. Vacío en la portada si no hace falta")
    foto: str = Field(description="Nombre exacto de una foto de la lista disponible que calce con la lámina, "
                                  "o vacío para una lámina sin foto")


class Contenido(BaseModel):
    tema: str
    laminas: List[Lamina]
    descripcion: str = Field(description="Caption de Instagram: gancho en la primera línea, 3-6 párrafos cortos, "
                                         "llamado a la acción. Sin hashtags")
    hashtags: List[str] = Field(description="Entre 8 y 15 hashtags relevantes, con #")


class Historia(BaseModel):
    tema: str
    etiqueta: str = Field(description="Categoría corta en mayúsculas, 1 a 3 palabras (ej. ¿SABÍAS QUE?, TIP, SERVICIO)")
    gancho: str = Field(description="Frase principal que detiene el scroll, máximo 8 palabras")
    texto: str = Field(description="Texto de apoyo, máximo 28 palabras")
    llamado: str = Field(description="Llamado a la acción, máximo 6 palabras (ej. Cotiza tu traslado)")
    foto: str = Field(description="Nombre exacto de una foto vertical de la lista disponible, o vacío")


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"ultimo_tipo": None, "historial": []}


def siguiente_tipo(estado):
    forzado = os.environ.get("TIPO")
    if forzado:
        return forzado
    if estado["ultimo_tipo"] not in ORDEN:
        return ORDEN[0]
    return ORDEN[(ORDEN.index(estado["ultimo_tipo"]) + 1) % len(ORDEN)]


def pedir_contenido(m, tipo, historial, dia=None, hora=""):
    recientes = "\n".join(f"- {h['fecha']}: {h['tema']}" for h in historial[-30:]) or "(ninguna todavía)"
    sistema = f"""Eres el community manager de {m['nombre']} ({m['usuario']}), empresa de ambulancias en {m['pais']}.
Servicios: {', '.join(m['servicios'])}.
Contacto: teléfono {m['telefono']}; sitio web {m.get('web') or '(no tiene)'}.
Tono: {m['tono']}

Reglas de contenido:
- La información de salud debe ser correcta, prudente y alineada con recomendaciones oficiales vigentes
  (MINSAL, Cruz Roja, AHA/ERC). Ante la duda, sé conservador y no des dosis de medicamentos ni diagnósticos.
- Cuando sea una emergencia, indica llamar al {m['numero_emergencia']}.
- En la descripción, cuando invites a contactar o a conocer los servicios, menciona el sitio web y el teléfono.
- No inventes datos de la empresa (precios, cifras, nombres, convenios) que no estén aquí.
- Español neutro de Chile, con tildes correctas. Sin emojis en las láminas; en la descripción, pocos y sobrios."""
    tema = os.environ.get("TEMA", "").strip()
    planificacion = calendario.texto_para_prompt(dia, hora, tipo) if dia else ""
    eleccion = (f"Tema pedido: {tema}." if tema else
                f"{planificacion}\nTemas de referencia de la cuenta: {'; '.join(m['temas'])}.")
    usadas = fotos_recientes(historial)[:4]
    aviso_fotos = (f"\nPara variar, NO uses en la portada ni en la historia estas fotos usadas recientemente: "
                   f"{', '.join(usadas)}." if usadas else "")
    lista_fotos = "\n".join(f"- {f['archivo']}: {f['descripcion']} ({f['orientacion']})" for f in diseno.fotos())
    guia_fotos = (f"""Fotos reales de la empresa disponibles (campo "foto" de cada lámina):
{lista_fotos}
Usa foto en la portada, en el post y en las escenas del reel (prefiere las verticales en el reel); en las láminas
interiores del carrusel, usa foto solo en algunas (las de datos o pasos van mejor sin foto, con "foto" vacío).
Varía las fotos dentro de la misma publicación. Las fotos muestran ambulancias y clínicas: no las uses como si
mostraran algo que no muestran.{aviso_fotos}""" if lista_fotos else 'No hay fotos: deja el campo "foto" vacío.')
    pedido = f"""Crea la publicación: un {tipo.upper()} con {LAMINAS[tipo]}.
{eleccion}
{guia_fotos}
No repitas los temas de estas publicaciones recientes:
{recientes}"""
    formato = Contenido
    if tipo == "historia":
        formato = Historia
        pedido = f"""Crea una HISTORIA de Instagram (formato vertical 9:16, una sola imagen, dura 24 horas).
Objetivo: ganar seguidores y generar clientes para {m['nombre']}. Alterna entre:
- dato útil o "¿sabías que?" de primeros auxilios que invite a seguir la cuenta para aprender más,
- servicio de la empresa ({', '.join(m['servicios'])}) con un beneficio claro y un llamado a cotizar o llamar,
- recordatorio práctico de la temporada o del día a día en Chile.
El llamado a la acción debe ser concreto (llamar, cotizar, visitar el sitio web o seguir la cuenta).
El teléfono y el sitio web ya aparecen en la tarjeta del diseño: no los repitas en el gancho ni en el texto.
No uses encuestas ni stickers (no se pueden publicar por la API). {('Tema pedido: ' + tema + '.') if tema else planificacion}
{guia_fotos}
Usa siempre una foto vertical si hay.
No repitas los temas de estas publicaciones recientes:
{recientes}"""

    if os.environ.get("OPENAI_API_KEY"):
        from openai import OpenAI
        r = OpenAI().responses.parse(
            model=os.environ.get("LLM_MODEL") or m.get("modelo_openai", "gpt-5.6-luna"),
            instructions=sistema,
            input=pedido,
            text_format=formato,
        )
        if r.output_parsed is None:
            sys.exit(f"OpenAI no generó contenido (estado={r.status})")
        return r.output_parsed

    import anthropic
    r = anthropic.Anthropic().messages.parse(
        model=m.get("modelo", "claude-opus-5-5"),
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=sistema,
        messages=[{"role": "user", "content": pedido}],
        output_format=formato,
    )
    if r.stop_reason == "refusal" or r.parsed_output is None:
        sys.exit(f"Claude no generó contenido (stop_reason={r.stop_reason})")
    return r.parsed_output


def fotos_recientes(historial):
    """Fotos de portada/historia usadas, de la más reciente a la más antigua (sin repetir)."""
    vistas = []
    for h in reversed(historial):
        f = h.get("foto")
        if f and f not in vistas:
            vistas.append(f)
    return vistas


def rotar_foto(elegida, historial, vertical=False, evitar=None):
    """Si la foto elegida para la portada o la historia se usó en las últimas publicaciones (o viene vacía),
    la cambia por la menos usada recientemente (vertical si se pide). Por defecto evita todas las fotos
    usadas recientemente salvo la más antigua, así las portadas rotan por todo el banco de fotos."""
    disponibles = diseno.fotos()
    if not disponibles:
        return elegida
    candidatas = [f["archivo"] for f in disponibles if not vertical or f["orientacion"] == "vertical"] or \
        [f["archivo"] for f in disponibles]
    recientes = fotos_recientes(historial)
    if evitar is None:
        evitar = max(1, len(candidatas) - 1)
    if elegida in candidatas and elegida not in recientes[:evitar]:
        return elegida
    # la menos usada: primero las nunca usadas, luego la que se usó hace más tiempo
    return sorted(candidatas, key=lambda a: (a in recientes, -recientes.index(a) if a in recientes else 0))[0]


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def crear(m, estado, tipo, dia, hora, salida):
    """Genera una publicación y la deja en salida/<dia>-<hora>-<tipo>-<tema>/."""
    c = pedir_contenido(m, tipo, estado["historial"], dia, hora)
    validas = {f["archivo"] for f in diseno.fotos()}
    if tipo == "historia":
        if c.foto not in validas:
            c.foto = ""
        # las historias van en vertical y rotan entre todas las fotos verticales
        c.foto = rotar_foto(c.foto, estado["historial"], vertical=True)
        carpeta = Path(salida) / f"{dia}-{hora.replace(':', '')}-historia-{slug(c.tema)}"
        carpeta.mkdir(parents=True, exist_ok=False)
        print(f"{dia} {hora} historia: {c.tema} -> {carpeta}")
        diseno.historia(c.etiqueta, c.gancho, c.texto, c.llamado, carpeta / "01.jpg", foto=c.foto or None)
        if m.get("historias_video", True):  # video de 15 s con animación y música; la imagen queda de respaldo
            with tempfile.TemporaryDirectory() as tmp:
                pista = lambda seg, golpe: musica.pista(carpeta.name, seg, Path(tmp) / "m.mp3", golpe)  # variante propia
                video.historia(c.etiqueta, c.gancho, c.texto, c.llamado, carpeta / "video.mp4",
                               foto=c.foto or None, musica=pista)
        (carpeta / "fecha.txt").write_text(f"{dia} {hora}\n")
        (carpeta / "contenido.json").write_text(c.model_dump_json(indent=2), encoding="utf-8")
        estado["historial"].append({"fecha": f"{dia} {hora}", "tipo": tipo, "tema": c.tema, "foto": c.foto})
        estado["historial"] = estado["historial"][-120:]
        return carpeta, c
    for l in c.laminas:
        if l.foto not in validas:
            l.foto = ""
    if c.laminas:  # portada distinta a las de las últimas publicaciones
        # portadas (también de reels, que recortan la foto a 9:16) rotan por todo el banco de fotos
        nueva = rotar_foto(c.laminas[0].foto, estado["historial"])
        if nueva != c.laminas[0].foto:
            for l in c.laminas[1:]:  # si la nueva ya estaba en otra lámina, intercambiarlas
                if l.foto == nueva:
                    l.foto = c.laminas[0].foto
            c.laminas[0].foto = nueva
    carpeta = Path(salida) / f"{dia}-{hora.replace(':', '')}-{tipo}-{slug(c.tema)}"
    carpeta.mkdir(parents=True, exist_ok=False)
    print(f"{dia} {hora} {tipo}: {c.tema} -> {carpeta}")

    if tipo == "reel":
        with tempfile.TemporaryDirectory() as tmp:
            pista = lambda seg, golpe: musica.pista(carpeta.name, seg, Path(tmp) / "m.mp3", golpe)  # variante propia
            video.reel([(l.titulo, l.texto, l.foto or None) for l in c.laminas], carpeta / "video.mp4",
                       musica=pista)
        # Primera escena en PNG para revisar rápido (publicar.py no sube los .png)
        diseno.lamina(c.laminas[0].titulo, c.laminas[0].texto, carpeta / "vista-previa.png",
                      diseno.REEL, portada=True, foto=c.laminas[0].foto or None)
    else:
        laminas = c.laminas[:1] if tipo == "post" else c.laminas[:10]
        total = len(laminas)
        for i, l in enumerate(laminas, 1):
            diseno.lamina(l.titulo, l.texto, carpeta / f"{i:02d}.jpg",
                          numero=i if total > 1 else None, total=total if total > 1 else None,
                          portada=(i == 1 and total > 1), foto=l.foto or None)

    fijos = [h for h in m.get("hashtags_fijos", []) if h not in c.hashtags]
    descripcion = c.descripcion.strip()
    if m.get("web") and m["web"].lower() not in descripcion.lower():
        descripcion += f"\n\nContacto: {m['telefono']} · {m['web']}"
    (carpeta / "texto.txt").write_text(f"{descripcion}\n\n{' '.join(fijos + c.hashtags)}\n", encoding="utf-8")
    (carpeta / "fecha.txt").write_text(f"{dia} {hora}\n")
    (carpeta / "contenido.json").write_text(c.model_dump_json(indent=2), encoding="utf-8")

    estado["ultimo_tipo"] = tipo
    estado["historial"].append({"fecha": f"{dia} {hora}", "tipo": tipo, "tema": c.tema,
                                "foto": c.laminas[0].foto if c.laminas else ""})
    estado["historial"] = estado["historial"][-120:]
    return carpeta, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=str(RAIZ / "cola"), help="carpeta donde dejar las publicaciones")
    ap.add_argument("--fecha", help="día de publicación AAAA-MM-DD (por defecto mañana)")
    ap.add_argument("--horarios", help="horas separadas por coma, ej. 09:00,18:30 (por defecto las de marca.json)")
    args = ap.parse_args()

    m = diseno.marca()
    estado = cargar_estado()
    # Se genera el día anterior: así queda tiempo para revisar antes de la hora de publicación
    dia = args.fecha or (dt.datetime.now(ZONA) + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    horarios = [h.strip() for h in args.horarios.split(",")] if args.horarios else \
        m.get("horarios") or [m.get("hora_publicacion", "09:00")]

    forzado = os.environ.get("TIPO", "")
    hist = m.get("horarios_historias", [])
    if forzado == "historia":  # solo historias
        plan = [(h, "historia") for h in (horarios if args.horarios else hist)]
    else:  # publicaciones del feed (alternando tipo) y, si no se pidieron horas específicas, las historias
        plan = [(h, None) for h in horarios] + ([] if args.horarios else [(h, "historia") for h in hist])

    hechas = []
    for hora, tipo in plan:
        tipo = tipo or siguiente_tipo(estado)
        carpeta, c = crear(m, estado, tipo, dia, hora, args.salida)
        hechas.append((carpeta, tipo, c.tema, hora))
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            rels = " ".join(str(c.relative_to(RAIZ.parent)) for c, *_ in hechas)
            resumen = " + ".join(f"{h} {t}: {tema}" for _, t, tema, h in hechas)
            f.write(f"carpetas={rels}\ndia={dia}\nresumen={resumen}\n")


if __name__ == "__main__":
    main()
