"""Perfil (empresa) con el que trabaja el pipeline.

Cada empresa tiene su propia carpeta con marca, calendario, estado, cola y publicados:
  - Ambulancias AHP (perfil "ahp", el original): instagram/ directamente.
  - Otras empresas: instagram/perfiles/<perfil>/ (ver instagram/perfiles/LEEME.md para agregar una nueva).
Se elige con la variable de entorno PERFIL (por defecto "ahp").
"""
import os
from pathlib import Path

CODIGO = Path(__file__).resolve().parent          # carpeta instagram/ (código compartido)
NOMBRE = (os.environ.get("PERFIL") or "ahp").strip().lower()
BASE = CODIGO if NOMBRE == "ahp" else CODIGO / "perfiles" / NOMBRE

if not (BASE / "marca" / "marca.json").exists():
    raise SystemExit(f"No existe el perfil '{NOMBRE}' (falta {BASE / 'marca' / 'marca.json'})")
