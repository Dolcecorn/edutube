# Perfiles (varias empresas en el mismo pipeline)

El código de `instagram/` es compartido. Cada empresa tiene su carpeta con marca, calendario, estado y colas:

- **Ambulancias AHP** (perfil `ahp`, el original): `instagram/` directamente.
- **Otras empresas**: `instagram/perfiles/<perfil>/` (ej. `legalmain`).

Se elige con la variable `PERFIL` (por defecto `ahp`):

```bash
PERFIL=legalmain python3 instagram/generar.py --fecha 2026-11-10
PERFIL=legalmain python3 instagram/publicar.py
```

## Agregar una empresa nueva

1. Copiar `perfiles/legalmain/` como `perfiles/<nuevo>/` (nombre corto en minúsculas, sin espacios) y vaciar `cola/`, `publicados/` y `estado.json` (`{"ultimo_tipo": null, "historial": []}`).
2. Editar `marca/marca.json`:
   - `nombre`, `usuario`, `pais`, `rubro`, `telefono` (puede ir vacío: se muestra el sitio web), `web`.
   - `colores` (`principal`, `acento`, `claro`, `oscuro`; opcional `borde_boton`).
   - `tono`, `publico`, `servicios`, `reglas` (reglas de contenido del rubro), `voz`, `temas`, `hashtags_fijos`.
   - `horarios` (feed) y `horarios_historias` (lista vacía si no lleva historias).
   - `estilo_musica`: `deep_house` (como AHP) o `corporativo` (más lento y sobrio).
   - Opcionales: `cta_cierre`, `llamado_defecto`, `ideas_historias`, `nota_fotos`, `degradado_continuo`.
3. Logo: `marca/logo.png` (para fondo claro) y `marca/logo-blanco.png` (para fondo oscuro), PNG con transparencia.
4. Tipografía (opcional): `marca/fuentes/` con dos `.ttf`; el primero en orden alfabético es la negrita.
5. Fotos: `marca/fotos/` + `marca/fotos/fotos.json` (`archivo`, `descripcion`, `orientacion`). Clips de video en `marca/videos/` + `videos.json`. Sin fotos propias, se pueden generar fondos como en `perfiles/legalmain/marca/fondos.py`.
6. Voz en off (opcional): `marca/voz/referencia.wav` (20-30 s de una sola persona, con su autorización). Sin ella, los reels van solo con música.
7. `calendario.json`: `foco_semanal`, `meses`, `fechas` y `publicaciones` (fecha exacta con `formato` y `tema`, que se respetan tal cual).
8. Secrets de GitHub (nunca en el chat): `IG_USER_ID_<PERFIL>` y `IG_ACCESS_TOKEN_<PERFIL>` (ej. `IG_USER_ID_LEGALMAIN`).
9. Tareas programadas: generar con el workflow "Generar publicación de Instagram" (input `perfil`) y publicar con "Publicar en Instagram" (sin input publica todos los perfiles).
