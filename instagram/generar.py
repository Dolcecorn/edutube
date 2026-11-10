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
import locucion
import diseno
import musica
import video

import perfil

RAIZ = perfil.BASE
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
    locucion: str = Field(description="Solo en reels: lo que dice la voz en off en esta escena, 1 o 2 frases "
                                      "naturales, máximo 22 palabras. Vacío en posts y carruseles")


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


def siguiente_tipo(estado, m=None, hora=""):
    forzado = os.environ.get("TIPO")
    if forzado:
        return forzado
    opciones = (m or {}).get("tipos_por_horario", {}).get(hora)
    if opciones:  # ej. 18:30 siempre reel; 9:00 alterna carrusel y post
        previos = [h["tipo"] for h in estado["historial"] if h.get("fecha", "").endswith(hora) and h["tipo"] in opciones]
        return opciones[(opciones.index(previos[-1]) + 1) % len(opciones)] if previos else opciones[0]
    if estado["ultimo_tipo"] not in ORDEN:
        return ORDEN[0]
    return ORDEN[(ORDEN.index(estado["ultimo_tipo"]) + 1) % len(ORDEN)]


def sistema_marca(m):
    """Instrucciones de sistema de un perfil definido por marca.json (rubro, reglas, etc.)."""
    contacto = "; ".join(x for x in (f"teléfono {m['telefono']}" if m.get("telefono") else "",
                                      f"sitio web {m['web']}" if m.get("web") else "",
                                      f"Instagram {m['usuario']}") if x)
    reglas = "\n".join(f"- {r}" for r in m.get("reglas", []))
    return f"""Eres el community manager de {m['nombre']} ({m['usuario']}), {m['rubro']} en {m['pais']}.
Servicios: {', '.join(m['servicios'])}.
Público: {m.get('publico', 'clientes de la empresa')}.
Contacto: {contacto}.
Tono: {m['tono']}

Reglas de contenido:
{reglas}
- No inventes datos de la empresa (precios, cifras, nombres, clientes, casos) que no estén aquí.
- Español neutro de Chile, con tildes correctas. Sin emojis en las láminas; en la descripción, pocos y sobrios."""


def toca_zona(m, historial):
    """AHP: 1 de cada 6 piezas menciona la zona (Quinta Región y RM). Pedido de Eleva, 2026-11-06."""
    return not m.get("rubro") and not any(h.get("zona") for h in historial[-5:])


def pedir_contenido(m, tipo, historial, dia=None, hora="", pub=None, zona=False):
    recientes = "\n".join(f"- {h['fecha']}: {h['tema']}" for h in historial[-30:]) or "(ninguna todavía)"
    if m.get("rubro"):
        return _pedir(m, tipo, historial, recientes, sistema_marca(m), dia, hora, pub)
    sistema = f"""Eres el community manager de {m['nombre']} ({m['usuario']}), empresa de ambulancias en {m['pais']}.
Servicios: {', '.join(m['servicios'])}.
Contacto: teléfono {m['telefono']}; sitio web {m.get('web') or '(no tiene)'}.
Tono: {m['tono']}
Zona: somos de la provincia de San Antonio, Litoral Central, Quinta Región (Región de Valparaíso) y trabajamos
en la Quinta Región y la Región Metropolitana; otras regiones solo a pedido.
Datos reales de la empresa (confirmados por la empresa; úsalos cuando aporten, sin inventar más):
- Empresa familiar fundada en 2005: más de 20 años de experiencia. Fundador: Augusto Henríquez Pacheco (de ahí
  la sigla AHP), junto a su esposa Teresa Olivares Álvarez. Nombres solo de vez en cuando y con naturalidad.
- Cifras aproximadas: más de 1.700 traslados de pacientes particulares y más de 500 coberturas de eventos
  (siempre como "más de"; no des otras cifras).
- Atención 24/7. Salida inmediata según disponibilidad de ambulancias (nunca prometas un tiempo de llegada);
  también traslados programados y reservas para eventos con anticipación.
- En cada traslado van un conductor y un TENS (técnico en enfermería). No digas que van médicos ni enfermeros.
- Ambulancias equipadas con oxígeno, DEA (desfibrilador externo automático), saturómetro, toma presión,
  silla de ruedas y camilla. No menciones otro equipamiento ni la cantidad de ambulancias.
- Todos los permisos sanitarios para operar al día (se puede decir "con todos los permisos sanitarios al día").
- Traslados a hospitales, clínicas y domicilios; viajes a Santiago y a otras regiones; ida y vuelta con espera;
  traslados frecuentes (diálisis, controles, exámenes). Puede ir un acompañante.
- Pago en efectivo o transferencia. Entregamos boleta o factura, que sirve para pedir reembolso a la Isapre o
  al seguro (según el plan de cada persona).
- Servicios para eventos: cobertura médica de eventos deportivos y masivos, y arriendo de ambulancia para
  automovilismo, motocross, fútbol, conciertos y festivales. No nombres clientes ni eventos específicos.
- Reseña real en Google (puedes citarla o resumirla, siempre como reseña de un cliente): "Tuve que trasladar a
  mi madre desde el Hospital de San Antonio al Hospital Clínico U. de Chile, Santiago, excelente atención por
  parte del conductor de la ambulancia y la TENS. El mejor precio que encontré (hice varias cotizaciones).
  Don Augusto Henríquez, conductor muy atento, preocupado y muy empático. Lo recomiendo 100 %".
{"- En ESTA publicación menciona de forma natural que somos de la provincia de San Antonio, Litoral Central, Quinta Región, y que trabajamos en la Quinta Región y la Región Metropolitana (en el texto o la descripción)." if zona else "- En esta publicación NO menciones la zona ni las regiones en que trabajamos."}
- Hashtags: además de los temáticos, incluye 3 a 5 locales de la zona, variando entre publicaciones (ej. #Valparaiso
  #VinaDelMar #QuintaRegion #Quilpue #VillaAlemana #SanAntonio #Santiago #RegionMetropolitana).

Reglas de contenido:
- La información de salud debe ser correcta, prudente y alineada con recomendaciones oficiales vigentes
  (MINSAL, Cruz Roja, AHA/ERC). Ante la duda, sé conservador y no des dosis de medicamentos ni diagnósticos.
- El objetivo es que la gente llame y contrate a {m['nombre']}: el llamado principal es siempre contactarnos
  (teléfono {m['telefono']} o sitio web) para traslados, cobertura de eventos o atención de urgencias.
- El {m['numero_emergencia']} se menciona SOLO cuando el tema trata una situación de riesgo vital (paro, pérdida de
  conciencia, dificultad grave para respirar, convulsiones, hemorragia grave), como máximo una vez y sin hacerlo
  el centro del mensaje. Fuera de eso, no lo nombres.
- Mensajes concretos y útiles, nada vago ni genérico: di qué hacemos, para quién, en qué situación y qué gana la
  persona (ej. "¿Alta médica y tu familiar no puede ir en auto? Lo trasladamos en camilla con paramédico").
  Evita frases de relleno como "estamos para apoyarte", "tu bienestar es lo primero" o "apoyo seguro".
- Nada obvio: no digas lo que cualquiera da por hecho (ej. "la camilla va asegurada", "llegamos a tiempo",
  "cuidamos a tu familiar"). Cada pieza aporta algo que la persona no sabía o no había pensado: un dato práctico,
  un detalle de cómo se hace, una situación concreta o qué preguntar antes de contratar.
- Si el día tiene una fecha especial, intégrala con naturalidad en el tema; no la pegues como frase suelta al final.
- Llamados propios de una fecha (ej. "dona a la Teletón"): solo si la pieza COMPLETA trata de esa fecha (ej. "Planifica
  tu traslado a los puntos de donación"). Nunca los mezcles con otro tema (ej. consejos de cómo ayudar o mover a
  una persona y al final "dona"). No des consejos de cómo mover, levantar o empujar a una persona.
- En la descripción, cuando invites a contactar o a conocer los servicios, menciona el sitio web y el teléfono.
- No inventes datos de la empresa (precios, cifras, nombres, convenios) que no estén aquí.
- No afirmes procesos ni coordinaciones que no estén descritos aquí: por ejemplo, NO digas que confirmamos o
  coordinamos ingresos, camas o recepción con clínicas, hospitales o centros de salud. Habla de lo que hace el
  equipo de la ambulancia (traslado, personal de salud, equipamiento) o de consejos para la familia.
- Español neutro de Chile, con tildes correctas. Sin emojis en las láminas; en la descripción, pocos y sobrios."""
    return _pedir(m, tipo, historial, recientes, sistema, dia, hora, pub)


def _pedir(m, tipo, historial, recientes, sistema, dia, hora, pub):
    generico = bool(m.get("rubro"))
    tema = os.environ.get("TEMA", "").strip()
    if pub:  # publicación fijada en el calendario para ese día
        tema = pub["tema"] + (f" (objetivo: {pub['objetivo']})" if pub.get("objetivo") else "") + \
            (f" Línea de contenido: {pub['linea']}." if pub.get("linea") else "") + \
            (f" Enfoque: {pub['enfoque']}" if pub.get("enfoque") else "")
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
Varía las fotos dentro de la misma publicación. {m.get('nota_fotos', 'Las fotos muestran ambulancias y clínicas: no las uses como si mostraran algo que no muestran.')}{aviso_fotos}""" if lista_fotos else 'No hay fotos: deja el campo "foto" vacío.')
    voz = ""
    abierto = (", de forma abierta y SIN nombrar ningún canal (ni sitio web, ni mensaje directo, ni teléfono, "
               "ni correo)") if m.get("cta_abierto") else \
        ' (el sitio web aparece en pantalla; en la voz di "escríbenos a través de nuestro sitio web" o similar)'
    if tipo == "reel" and generico:
        voz = f"""
Locución (campo "locucion" de cada escena): {m.get('voz', 'voz en off profesional, español neutro de Chile')}.
Complementa el texto de pantalla sin leerlo palabra por palabra; frases cortas y fáciles de decir. No dictes
números de teléfono ni direcciones web (aparecen en pantalla). Evita repetir la misma palabra en frases
seguidas; usa sinónimos.
La ÚLTIMA escena es el llamado a la acción, en el texto y en la locución: invita concretamente a contactar a
{m['nombre']} para revisar el caso de la empresa{abierto}. Después de esa escena el video cierra solo con el logo."""
    elif tipo == "reel":
        voz = """
Locución (campo "locucion" de cada escena): la voz en off de un locutor chileno, tono cercano, sereno y
profesional (español neutro de Chile, sin modismos ni garabatos). Complementa el texto de pantalla sin leerlo
palabra por palabra; frases cortas y fáciles de decir. No dictes números de teléfono ni direcciones web
(aparecen en pantalla); en la última escena invita a seguir la cuenta o a contactar. Cuando corresponda,
si (y solo si) hay riesgo vital, nombra el 131 como se dice en Chile: "uno tres uno" (nunca "ciento treinta y uno"). Evita repetir la misma
palabra en una frase o entre frases seguidas (por ejemplo, no "con este calor, un golpe de calor"); usa
sinónimos."""
    if not generico and tipo == "reel":
        voz += """
Gancho: la PRIMERA escena debe detener el scroll en los primeros 2 segundos, con una pregunta o un dato
sorprendente y concreto de máximo 7 palabras en pantalla (los reels los ven sobre todo personas que aún no nos
siguen).
Cierre: la ÚLTIMA escena (llamado a la acción), en pantalla y en la locución, dice que somos de San Antonio, en la
Quinta Región, y que también trabajamos en la Región Metropolitana, e invita a contactarnos.
En la locución nunca empieces una frase con "AHP": di "Ambulancias AHP" o "en AHP"."""
    if not generico and tipo == "carrusel":
        voz += """
Formato para GUARDAR: el carrusel es una guía práctica que la persona querrá guardar o compartir (checklist,
pasos, qué llevar, qué preguntar antes de contratar). Cada lámina interior trae un punto concreto. La última
lámina invita a guardar el carrusel y compartirlo con quien lo necesite, y a contactarnos."""
    pedido = f"""Crea la publicación: un {tipo.upper()} con {LAMINAS[tipo]}.{voz}
{eleccion}
{guia_fotos}
No repitas los temas de estas publicaciones recientes:
{recientes}"""
    formato = Contenido
    if tipo == "historia":
        formato = Historia
        ideas = m.get("ideas_historias") or [
            'dato útil o "¿sabías que?" de primeros auxilios que invite a seguir la cuenta para aprender más',
            f"servicio de la empresa ({', '.join(m['servicios'])}) con un beneficio claro y un llamado a cotizar o llamar",
            "recordatorio práctico de la temporada o del día a día en Chile"]
        ideas = "\n".join(f"- {x}," for x in ideas)
        pedido = f"""Crea una HISTORIA de Instagram (formato vertical 9:16, una sola imagen, dura 24 horas).
Objetivo: ganar seguidores y generar clientes para {m['nombre']}. Alterna entre:
{ideas}
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


def uso_fotos(historial):
    """Todas las fotos usadas (portadas e interiores), de la más reciente a la más antigua, sin repetir."""
    vistas = []
    for h in reversed(historial):
        for f in [h.get("foto")] + h.get("fotos", []):
            if f and f not in vistas:
                vistas.append(f)
    return vistas


def refrescar_interiores(laminas, historial, recientes_max=6):
    """Las láminas interiores con una foto muy usada pasan a una foto poco o nunca usada (sin repetir dentro
    de la publicación). Así las fotos nuevas del banco entran rápido en rotación."""
    banco = [f["archivo"] for f in diseno.fotos()]
    uso = uso_fotos(historial)
    recientes = set(uso[:recientes_max])
    en_uso = {l.foto for l in laminas if l.foto}
    libres = sorted((f for f in banco if f not in en_uso),
                    key=lambda a: (a in uso, -uso.index(a) if a in uso else 0))
    for l in laminas[1:]:
        if l.foto and l.foto in recientes and not l.foto.endswith(".mp4") and libres:
            l.foto = libres.pop(0)


def elegir_clips(historial, n):
    """Los n clips de video usados hace más tiempo (primero los nunca usados)."""
    disponibles = [v["archivo"] for v in diseno.videos()]
    usados = []
    for h in reversed(historial):
        for v in h.get("clips", []):
            if v not in usados:
                usados.append(v)
    orden = sorted(disponibles, key=lambda a: (a in usados, -usados.index(a) if a in usados else 0))
    return orden[:n]


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def fondo_del_dia(m, dia, hora, solo_oscuros=False):
    """Fondo de fecha especial que le toca a esta pieza (rotan dentro del día y entre días)."""
    fondos = diseno.fondos_especiales(dia)
    if solo_oscuros:
        fondos = [f for f in fondos if diseno.es_oscuro(f)]
    if not fondos:
        return None
    horas = sorted(set(m.get("horarios", []) + m.get("horarios_historias", [])))
    i = horas.index(hora) if hora in horas else 0
    return fondos[(dt.date.fromisoformat(dia).toordinal() * len(horas) + i) % len(fondos)]


def crear(m, estado, tipo, dia, hora, salida, pub=None):
    """Genera una publicación y la deja en salida/<dia>-<hora>-<tipo>-<tema>/."""
    reuso = os.environ.get("CONTENIDO", "").strip()   # volver a renderizar un contenido.json existente
    if reuso:
        c = (Historia if tipo == "historia" else Contenido).model_validate_json(Path(reuso).read_text(encoding="utf-8"))
    else:
        # los reels de AHP siempre cierran con la zona (Eleva 2026-11-10); el resto, 1 de cada 6
        zona = toca_zona(m, estado["historial"]) or (tipo == "reel" and not m.get("rubro"))
        c = pedir_contenido(m, tipo, estado["historial"], dia, hora, pub, zona)
    validas = {f["archivo"] for f in diseno.fotos()}
    if tipo == "historia":
        if c.foto not in validas:
            c.foto = ""
        # las historias van en vertical y rotan entre todas las fotos verticales
        c.foto = rotar_foto(c.foto, estado["historial"], vertical=True)
        # la tarjeta ya muestra teléfono y web: el llamado no los repite
        if re.search(r"\d{4}|www\.|\.cl", c.llamado):
            c.llamado = m.get("llamado_defecto", "Coordina tu servicio con nosotros")
        carpeta = Path(salida) / f"{dia}-{hora.replace(':', '')}-historia-{slug(c.tema)}"
        carpeta.mkdir(parents=True, exist_ok=False)
        print(f"{dia} {hora} historia: {c.tema} -> {carpeta}")
        especial = fondo_del_dia(m, dia, hora)
        diseno.historia(c.etiqueta, c.gancho, c.texto, c.llamado, carpeta / "01.jpg", foto=c.foto or None,
                        especial=especial)
        if m.get("historias_video", True):  # video de 15 s con animación y música; la imagen queda de respaldo
            with tempfile.TemporaryDirectory() as tmp:
                pista = lambda seg, golpe: musica.pista(carpeta.name, seg, Path(tmp) / "m.mp3", golpe)  # variante propia
                video.historia(c.etiqueta, c.gancho, c.texto, c.llamado, carpeta / "video.mp4",
                               foto=c.foto or None, musica=pista, especial=especial)
        (carpeta / "fecha.txt").write_text(f"{dia} {hora}\n")
        (carpeta / "contenido.json").write_text(c.model_dump_json(indent=2), encoding="utf-8")
        estado["historial"].append({"fecha": f"{dia} {hora}", "tipo": tipo, "tema": c.tema, "foto": c.foto,
                                    **({"zona": True} if not reuso and zona else {})})
        estado["historial"] = estado["historial"][-120:]
        return carpeta, c
    for l in c.laminas:
        if l.foto not in validas and not (reuso and l.foto.endswith(".mp4")):
            l.foto = ""
    if c.laminas and not reuso:  # portada distinta a las de las últimas publicaciones
        # portadas (también de reels, que recortan la foto a 9:16) rotan por todo el banco de fotos
        nueva = rotar_foto(c.laminas[0].foto, estado["historial"])
        if nueva != c.laminas[0].foto:
            for l in c.laminas[1:]:  # si la nueva ya estaba en otra lámina, intercambiarlas
                if l.foto == nueva:
                    l.foto = c.laminas[0].foto
            c.laminas[0].foto = nueva
    if c.laminas and not reuso:  # láminas interiores: cambiar fotos usadas recientemente por las menos usadas del banco
        refrescar_interiores(c.laminas, estado["historial"])
    clips = sorted({v for l in c.laminas for v in l.foto.split("+") if v.endswith(".mp4")}) if reuso else []
    if tipo == "reel" and c.laminas and not reuso:  # escenas con clips de video reales (portada y una escena intermedia)
        n_esc = max(1, int(m.get("escenas_con_video", 2)))   # portada + escenas intermedias con video
        por = max(2, int(m.get("clips_por_escena", 2)))     # clips encadenados en cada escena con video
        destacado = m.get("video_destacado")                 # clip que aparece en todas las escenas con video
        if por == 2 and not destacado:
            clips = elegir_clips(estado["historial"], max(3, 2 * n_esc - 1))
        else:
            clips = [v for v in elegir_clips(estado["historial"], por * n_esc + 1) if v != destacado]
        if clips:
            # cada escena con video encadena clips distintos (se reproducen tal cual, sin ralentizar)
            otro = lambda k: clips[k % len(clips)]
            cadena = lambda *ks: "+".join(dict.fromkeys(otro(k) for k in ks))
            medias = list(range(1, len(c.laminas) - 1))   # nunca en la del llamado final
            if n_esc == 2 and len(c.laminas) >= 3:
                elegidas = [len(c.laminas) // 2]
            elif n_esc > 2 and medias:
                elegidas = sorted({medias[round(j * (len(medias) - 1) / max(1, n_esc - 2))]
                                   for j in range(n_esc - 1)})
            else:
                elegidas = []
            if por == 2 and not destacado:   # comportamiento original (AHP)
                c.laminas[0].foto = cadena(0, 1)
                for j, k in enumerate(elegidas):
                    c.laminas[k].foto = cadena(2, 0) if n_esc == 2 else cadena(2 * j + 2, 2 * j + 3)
            else:
                propios = por - (1 if destacado else 0)
                for j, k in enumerate([0] + elegidas):
                    cad = [otro(j * propios + i) for i in range(propios)]
                    if destacado:   # abre la portada y va segundo en las demás escenas
                        cad.insert(0 if j == 0 else 1, destacado)
                    c.laminas[k].foto = "+".join(dict.fromkeys(cad))
    carpeta = Path(salida) / f"{dia}-{hora.replace(':', '')}-{tipo}-{slug(c.tema)}"
    carpeta.mkdir(parents=True, exist_ok=False)
    print(f"{dia} {hora} {tipo}: {c.tema} -> {carpeta}")

    if tipo == "reel":
        with tempfile.TemporaryDirectory() as tmp:
            pista = lambda seg, golpe: musica.pista(carpeta.name, seg, Path(tmp) / "m.mp3", golpe)  # variante propia
            locs = None
            if locucion.disponible() and any(l.locucion.strip() for l in c.laminas):
                locs = []
                for i, l in enumerate(c.laminas):
                    if l.locucion.strip():
                        ruta = Path(tmp) / f"voz{i}.wav"
                        locucion.decir(l.locucion.strip(), ruta)
                        locs.append(ruta)
                    else:
                        locs.append(None)
            video.reel([(l.titulo, l.texto, l.foto or None) for l in c.laminas], carpeta / "video.mp4",
                       musica=pista, locuciones=locs, especial=fondo_del_dia(m, dia, hora, solo_oscuros=True))
        # Primera escena en PNG para revisar rápido (publicar.py no sube los .png)
        foto_previa = next((l.foto for l in c.laminas if l.foto and not l.foto.endswith(".mp4")), None)
        diseno.lamina(c.laminas[0].titulo, c.laminas[0].texto, carpeta / "vista-previa.png",
                      diseno.REEL, portada=True, foto=foto_previa)
    else:
        laminas = c.laminas[:1] if tipo == "post" else c.laminas[:10]
        total = len(laminas)
        for i, l in enumerate(laminas, 1):
            diseno.lamina(l.titulo, l.texto, carpeta / f"{i:02d}.jpg",
                          numero=i if total > 1 else None, total=total if total > 1 else None,
                          portada=(i == 1 and total > 1), foto=l.foto or None,
                          especial=fondo_del_dia(m, dia, hora) if i in (1, total) else None)

    fijos = [h for h in m.get("hashtags_fijos", []) if h not in c.hashtags]
    descripcion = c.descripcion.strip()
    if m.get("web") and m["web"].lower() not in descripcion.lower() and not m.get("cta_abierto"):
        descripcion += "\n\nContacto: " + " · ".join(x for x in (m.get("telefono"), m["web"]) if x)
    (carpeta / "texto.txt").write_text(f"{descripcion}\n\n{' '.join(fijos + c.hashtags)}\n", encoding="utf-8")
    (carpeta / "fecha.txt").write_text(f"{dia} {hora}\n")
    (carpeta / "contenido.json").write_text(c.model_dump_json(indent=2), encoding="utf-8")

    estado["ultimo_tipo"] = tipo
    estado["historial"].append({"fecha": f"{dia} {hora}", "tipo": tipo, "tema": c.tema,
                                "foto": c.laminas[0].foto if c.laminas else "",
                                "fotos": [l.foto for l in c.laminas[1:] if l.foto and not l.foto.endswith(".mp4")],
                                **({"clips": clips} if clips else {}),
                                **({"zona": True} if not reuso and zona else {})})
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

    # no duplicar: si la cola ya tiene algo para ese día y hora, se salta (REEMPLAZAR=1 para forzar)
    salida = Path(args.salida)
    if not os.environ.get("REEMPLAZAR"):
        ocupadas = {p.name[:15] for p in salida.glob(f"{dia}-*") if p.is_dir()} if salida.exists() else set()
        saltadas = [h for h, _ in plan if f"{dia}-{h.replace(':', '')}" in ocupadas]
        if saltadas:
            print(f"Ya hay contenido en la cola para {dia} a las {', '.join(saltadas)}: no se vuelve a generar.")
        plan = [(h, t) for h, t in plan if f"{dia}-{h.replace(':', '')}" not in ocupadas]

    hechas = []
    fijadas = calendario.publicaciones(dia)  # publicaciones fijadas en el calendario para ese día (tema y formato)
    for hora, tipo in plan:
        pub = None
        if tipo is None and fijadas and not os.environ.get("TEMA"):
            pub = fijadas.pop(0)
            tipo = os.environ.get("TIPO") or pub.get("formato")
        tipo = tipo or siguiente_tipo(estado, m, hora)
        carpeta, c = crear(m, estado, tipo, dia, hora, args.salida, pub)
        hechas.append((carpeta, tipo, c.tema, hora))
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            rels = " ".join(str(Path(c).resolve().relative_to(perfil.CODIGO.parent)) for c, *_ in hechas)
            resumen = " + ".join(f"{h} {t}: {tema}" for _, t, tema, h in hechas)
            f.write(f"carpetas={rels}\ndia={dia}\nresumen={resumen}\n")


if __name__ == "__main__":
    main()
