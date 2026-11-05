"""Lee calendario.json y arma la planificación de un día para generar.py."""
import datetime as dt
import json
from pathlib import Path

import perfil

RAIZ = perfil.BASE
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def cargar():
    f = RAIZ / "calendario.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _rango(ev):
    d = dt.date.fromisoformat(ev["desde"])
    h = dt.date.fromisoformat(ev.get("hasta", ev["desde"]))
    return d, h


def plan(dia, cal=None):
    """dia: 'AAAA-MM-DD'. Devuelve {'hoy': [...], 'proximas': [(evento, dias_que_faltan)], 'mes': {...},
    'foco': str}. 'hoy' son las fechas especiales vigentes ese día (las de temporada van al final)."""
    cal = cal if cal is not None else cargar()
    d = dt.date.fromisoformat(dia)
    hoy, proximas = [], []
    for ev in cal.get("fechas", []):
        desde, hasta = _rango(ev)
        if desde <= d <= hasta:
            hoy.append(ev)
        elif d < desde and (desde - d).days <= ev.get("anticipar", 0):
            proximas.append((ev, (desde - d).days))
    hoy.sort(key=lambda e: e.get("tipo") == "temporada")  # lo puntual primero
    return {"hoy": hoy, "proximas": proximas, "mes": cal.get("meses", {}).get(dia[:7], {}),
            "foco": cal.get("foco_semanal", {}).get(DIAS[d.weekday()], ""), "region": cal.get("region", "")}


def publicaciones(dia, cal=None):
    """Publicaciones del feed fijadas para ese día en "publicaciones" del calendario:
    [{"fecha", "formato" (post|reel|carrusel), "tema", "objetivo"?, "linea"?, "enfoque"?}]."""
    cal = cal if cal is not None else cargar()
    return [p for p in cal.get("publicaciones", []) if p.get("fecha") == dia]


def texto_para_prompt(dia, hora, tipo, cal=None):
    """Instrucciones de planificación para el modelo, según el calendario."""
    p = plan(dia, cal)
    lineas = [f"PLANIFICACIÓN DEL CALENDARIO para el {dia} ({DIAS[dt.date.fromisoformat(dia).weekday()]}) a las {hora}."]
    if p["region"]:
        lineas.append(f"Zona de trabajo de la empresa: {p['region']}.")
    puntuales = [e for e in p["hoy"] if e.get("tipo") != "temporada"]
    temporada = [e for e in p["hoy"] if e.get("tipo") == "temporada"]
    if puntuales:
        lineas.append("HOY es una fecha especial del calendario. TODO el contenido debe relacionarse con ella:")
        for e in puntuales:
            lineas.append(f"- {e['nombre']}: {e['enfoque']}")
        lineas.append("Si hay más de una publicación ese día, aborda un ángulo distinto de la fecha en cada una "
                      "(por ejemplo: saludo o mensaje de comunidad, consejo práctico de seguridad, servicio relacionado).")
    elif p["proximas"]:
        # se anticipa en las historias y, el día anterior, también en el feed; si no, queda como contexto
        anticipar = tipo == "historia" or min(n for _, n in p["proximas"]) <= 1
        lineas.append("Se acerca una fecha especial: " + (
            "esta publicación debe anticiparla y preparar a la audiencia:" if anticipar else
            "tenla en cuenta como contexto, pero esta publicación sigue el tema del mes y el foco del día:"))
        for e, n in p["proximas"]:
            lineas.append(f"- En {n} día(s): {e['nombre']}: {e['enfoque']}")
    for e in temporada:
        lineas.append(f"Temporada vigente: {e['nombre']} ({e['enfoque']}).")
    if p["mes"]:
        lineas.append(f"Tema del mes: {p['mes'].get('tema', '')} ({p['mes'].get('enfoque', '')}).")
    if p["foco"] and not puntuales:
        lineas.append(f"Foco del día de la semana: {p['foco']}.")
    lineas.append("Elige el tema concreto dentro de esta planificación, sin repetir temas recientes.")
    return "\n".join(lineas)
