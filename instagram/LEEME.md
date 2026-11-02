# Publicar en Instagram automáticamente

Pones el video o las fotos en una carpeta, con su texto y (si quieres) la hora. GitHub revisa la cola cada hora y publica con la **API oficial de Meta**, así que no hay riesgo de bloqueo como con los bots que simulan a una persona.

## Cómo agregar una publicación
Crea una carpeta dentro de `instagram/cola/` (el nombre que quieras; se publican en orden alfabético) con:

| Archivo | Para qué |
|---|---|
| `video.mp4` | **Reel** (un solo video) |
| `foto.jpg` | **Post** (una sola imagen) |
| `1.jpg`, `2.jpg`, ... | **Carrusel** (2 a 10 imágenes, en orden alfabético) |
| `texto.txt` | La descripción, con hashtags (máx. 2.200 caracteres) |
| `fecha.txt` | Opcional: `2026-11-05 18:00` (hora de Chile). Sin él, sale en la próxima pasada |

Ejemplo:
```
instagram/cola/2026-11-05-receta/
├── video.mp4
├── texto.txt
└── fecha.txt
```
Súbela a la rama `main` (desde la web de GitHub: *Add file → Upload files*, o con `git push`). Cuando se publica, la carpeta pasa sola a `instagram/publicados/` con el id del post. Se publica **una por hora** como máximo (cambiable con `MAX_POR_PASADA`).

Requisitos de Instagram: imágenes **JPG**, proporción entre 4:5 y 1,91:1, hasta 8 MB. Reels en **MP4 (H.264 + AAC)**, vertical 9:16 recomendado, de 3 s a 15 min.

## Configuración (una vez)
1. **Cuenta profesional:** en la app de Instagram, *Configuración → Tipo de cuenta y herramientas → Cambiar a cuenta profesional* (Creador o Empresa). Gratis y reversible.
2. **App de Meta:** en https://developers.facebook.com/apps crea una app → caso de uso *"Administrar mensajes y contenido en Instagram"* (API de Instagram con inicio de sesión de Instagram). No hace falta página de Facebook.
3. En la app: *Roles → Evaluadores de Instagram*, agrega tu cuenta y acepta la invitación en Instagram (*Configuración → Apps y sitios web → Invitaciones de evaluador*).
4. En *Configuración de la API con inicio de sesión de Instagram → Generar tokens de acceso*, conecta la cuenta con los permisos `instagram_business_basic` e `instagram_business_content_publish`. Copia el **token** y el **id de usuario** que muestra.
5. En este repo de GitHub: *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_USER_ID` = el id
   - `IG_ACCESS_TOKEN` = el token
6. Prueba: *Actions → Publicar en Instagram → Run workflow* con "Solo probar" marcado.

La app puede quedarse en modo desarrollo: así funciona para tus propias cuentas sin revisión de Meta.

## Cosas a tener en cuenta
- **El token dura 60 días.** Hay que generarlo de nuevo (paso 4) y reemplazar el secreto antes de que venza. Se puede automatizar más adelante.
- **Fotos y repo privado:** para las imágenes Instagram necesita descargarlas de una URL pública. Si el repo es público se usa la de GitHub automáticamente; si es privado, hay que definir la variable `MEDIA_BASE_URL` apuntando a otro lugar público. Los **reels no tienen este problema**: se suben directo desde el archivo.
- Videos pesados: GitHub acepta archivos de hasta 100 MB por archivo.
- Instagram permite hasta 100 publicaciones por API cada 24 horas.
- Si una publicación falla, la carpeta queda en la cola, la ejecución sale en rojo en *Actions* con el motivo, y se reintenta a la hora siguiente.
- Si usas una cuenta de Empresa vinculada a una página de Facebook y un token de Facebook, crea la variable `IG_API_HOST` = `graph.facebook.com`.

## Probar desde Ubuntu
```
DRY_RUN=1 python3 instagram/publicar.py          # muestra qué publicaría
IG_USER_ID=... IG_ACCESS_TOKEN=... python3 instagram/publicar.py   # publica de verdad
```
Solo usa Python 3.9+ (viene con Ubuntu 24), sin instalar nada más.
