# Publicar en Instagram automáticamente (@ambulanciasahp)

Pipeline completo, sin intervención humana una vez afinado:

1. **Generar** (todos los días ~09:00, `instagram-generar.yml`): Claude escribe el contenido del día con la marca y los temas de `marca/marca.json`, sin repetir temas recientes. `diseno.py` dibuja las láminas (Pillow) o arma el reel 9:16 con zoom suave y fundidos (ffmpeg). Alterna **post → reel → carrusel**.
2. **Revisar** (mientras se afina): la generación abre un PR con las imágenes y el texto. **Merge** = se publica; **Close** = se descarta. Cuando el resultado ya sea confiable, crea la variable `AUTO_PUBLICAR` = `true` y la publicación entra directo a la cola.
3. **Publicar** (cada hora, `instagram.yml`): sube a Instagram lo que esté en la cola y ya haya llegado a su hora (19:00 por defecto), con la **API oficial de Meta**, así que no hay riesgo de bloqueo como con los bots.

## Afinar las gráficas y el contenido
- `marca/marca.json`: nombre, colores, teléfono, web, tono, servicios, lista de temas, hashtags fijos, hora de publicación.
- `marca/logo.png` (opcional, fondo transparente): aparece en la franja superior.
- `marca/fuentes/` (opcional): pon ahí la tipografía de la marca (`.ttf`; la primera en orden alfabético es la negrita, la segunda la normal). Sin ella se usa DejaVu Sans.
- `marca/musica.mp3` (opcional, música libre de derechos): fondo de los reels. Sin ella, los reels van sin sonido.
- `diseno.py`: el diseño de las láminas en sí (márgenes, tamaños, franjas).
- Probar sin publicar: *Actions → Generar publicación de Instagram → Run workflow* (puedes forzar el tipo). Abre un PR que puedes cerrar.

### Probar el diseño en Ubuntu
```
sudo apt install ffmpeg
pip install -r instagram/requirements.txt
export ANTHROPIC_API_KEY=...
python3 instagram/generar.py --salida /tmp/prueba   # deja la publicación en /tmp/prueba
```
Ojo: también avanza `estado.json` (el turno y el historial de temas); descarta ese cambio si solo era una prueba (`git checkout instagram/estado.json`).

## Agregar una publicación a mano
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
1. **Cuenta profesional:** en la app de Instagram, *Configuración → Tipo de cuenta y herramientas → Cambiar a cuenta profesional* **Empresa** (es lo que corresponde para @ambulanciasahp). Gratis y reversible.
2. **App de Meta:** en https://developers.facebook.com/apps crea una app → caso de uso *"Administrar mensajes y contenido en Instagram"* (API de Instagram con inicio de sesión de Instagram). No hace falta página de Facebook.
3. En la app: *Roles → Evaluadores de Instagram*, agrega tu cuenta y acepta la invitación en Instagram (*Configuración → Apps y sitios web → Invitaciones de evaluador*).
4. En *Configuración de la API con inicio de sesión de Instagram → Generar tokens de acceso*, conecta la cuenta con los permisos `instagram_business_basic` e `instagram_business_content_publish`. Copia el **token** y el **id de usuario** que muestra.
5. **Clave de Claude:** crea una en https://console.anthropic.com (*API Keys*) y carga saldo (cada publicación cuesta centavos de dólar).
6. En este repo de GitHub: *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_USER_ID` = el id
   - `IG_ACCESS_TOKEN` = el token
   - `ANTHROPIC_API_KEY` = la clave de Claude
7. Para que la generación pueda abrir los PR de revisión: *Settings → Actions → General → Workflow permissions* → marca **"Allow GitHub Actions to create and approve pull requests"**.
8. Prueba: *Actions → Publicar en Instagram → Run workflow* con "Solo probar" marcado.

La app puede quedarse en modo desarrollo: así funciona para tus propias cuentas sin revisión de Meta.

## Cosas a tener en cuenta
- **El token dura 60 días.** Hay que generarlo de nuevo (paso 4) y reemplazar el secreto antes de que venza. Se puede automatizar más adelante.
- **Fotos y repo público:** Instagram descarga las imágenes desde una URL pública; como este repo es público, se usa la de GitHub automáticamente (y todo lo generado queda visible en GitHub). Si algún día se hace privado, hay que definir la variable `MEDIA_BASE_URL` con otro lugar público. Los reels no tienen este problema: se suben directo desde el archivo.
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
