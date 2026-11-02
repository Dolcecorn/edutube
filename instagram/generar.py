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
import unicodedata
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

import diseno
import video

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / "estado.json"
ZONA = ZoneInfo("America/Santiago")
ORDEN = ["post", "reel", "carrusel"]
LAMINAS = {"post": "exactamente 1 lámina", "carrusel": "entre 5 y 7 láminas (la primera es la portada)",
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


def pedir_contenido(m, tipo, historial):
    recientes = "\n".join(f"- {h['fecha']}: {h['tema']}" for h in historial[-30:]) or "(ninguna todavía)"
    sistema = f"""Eres el community manager de {m['nombre']} ({m['usuario']}), empresa de ambulancias en {m['pais']}.
Servicios: {', '.join(m['servicios'])}.
Tono: {m['tono']}

Reglas de contenido:
- La información de salud debe ser correcta, prudente y alineada con recomendaciones oficiales vigentes
  (MINSAL, Cruz Roja, AHA/ERC). Ante la duda, sé conservador y no des dosis de medicamentos ni diagnósticos.
- Cuando sea una emergencia, indica llamar al {m['numero_emergencia']}.
- No inventes datos de la empresa (precios, cifras, nombres, convenios) que no estén aquí.
- Español neutro de Chile, con tildes correctas. Sin emojis en las láminas; en la descripción, pocos y sobrios."""
    tema = os.environ.get("TEMA", "").strip()
    eleccion = (f"Tema pedido: {tema}." if tema else
                f"Temas posibles (elige uno o un ángulo nuevo dentro de ellos): {'; '.join(m['temas'])}.")
    lista_fotos = "\n".join(f"- {f['archivo']}: {f['descripcion']} ({f['orientacion']})" for f in diseno.fotos())
    guia_fotos = (f"""Fotos reales de la empresa disponibles (campo "foto" de cada lámina):
{lista_fotos}
Usa foto en la portada, en el post y en las escenas del reel (prefiere las verticales en el reel); en las láminas
interiores del carrusel, usa foto solo en algunas (las de datos o pasos van mejor sin foto, con "foto" vacío).
Varía las fotos dentro de la misma publicación. Las fotos muestran ambulancias y clínicas: no las uses como si
mostraran algo que no muestran.""" if lista_fotos else 'No hay fotos: deja el campo "foto" vacío.')
    pedido = f"""Crea la publicación: un {tipo.upper()} con {LAMINAS[tipo]}.
{eleccion}
{guia_fotos}
No repitas los temas de estas publicaciones recientes:
{recientes}"""

    if os.environ.get("OPENAI_API_KEY"):
        from openai import OpenAI
        r = OpenAI().responses.parse(
            model=os.environ.get("LLM_MODEL") or m.get("modelo_openai", "gpt-5.6-luna"),
            instructions=sistema,
            input=pedido,
            text_format=Contenido,
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
        output_format=Contenido,
    )
    if r.stop_reason == "refusal" or r.parsed_output is None:
        sys.exit(f"Claude no generó contenido (stop_reason={r.stop_reason})")
    return r.parsed_output


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def crear(m, estado, tipo, dia, hora, salida):
    """Genera una publicación y la deja en salida/<dia>-<hora>-<tipo>-<tema>/."""
    c = pedir_contenido(m, tipo, estado["historial"])
    validas = {f["archivo"] for f in diseno.fotos()}
    for l in c.laminas:
        if l.foto not in validas:
            l.foto = ""
    carpeta = Path(salida) / f"{dia}-{hora.replace(':', '')}-{tipo}-{slug(c.tema)}"
    carpeta.mkdir(parents=True, exist_ok=False)
    print(f"{dia} {hora} {tipo}: {c.tema} -> {carpeta}")

    if tipo == "reel":
        video.reel([(l.titulo, l.texto, l.foto or None) for l in c.laminas], carpeta / "video.mp4")
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
    (carpeta / "texto.txt").write_text(f"{c.descripcion.strip()}\n\n{' '.join(fijos + c.hashtags)}\n", encoding="utf-8")
    (carpeta / "fecha.txt").write_text(f"{dia} {hora}\n")
    (carpeta / "contenido.json").write_text(c.model_dump_json(indent=2), encoding="utf-8")

    estado["ultimo_tipo"] = tipo
    estado["historial"].append({"fecha": f"{dia} {hora}", "tipo": tipo, "tema": c.tema})
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

    hechas = []
    for hora in horarios:
        tipo = siguiente_tipo(estado)
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
