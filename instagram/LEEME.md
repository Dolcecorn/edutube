# Publicar en Instagram automáticamente (@ambulanciasahp)

Pipeline completo, sin intervención humana una vez afinado:

1. **Generar** (todos los días ~10:00, `instagram-generar.yml`, las **dos publicaciones del día siguiente**): la IA (OpenAI o Claude) escribe el contenido del día con la marca y los temas de `marca/marca.json`, sin repetir temas recientes. `diseno.py` dibuja las láminas (Pillow) o arma el reel 9:16 con zoom suave y fundidos (ffmpeg). Alterna **post → reel → carrusel**.
2. **Revisar** (mientras se afina): la generación abre un PR con las imágenes y el texto. **Merge** = se publica al día siguiente a las 9:00 (o en la próxima hora si se aprueba tarde); **Close** = se descarta. Cuando el resultado ya sea confiable, crea la variable `AUTO_PUBLICAR` = `true` y la publicación entra directo a la cola.
3. **Publicar** (cada media hora, `instagram.yml`): sube a Instagram lo que esté en la cola y ya haya llegado a su hora (publicaciones a las **9:00 y 18:30** e historias a las **12:00 y 20:30**, todos los días, fines de semana y feriados incluidos; se cambian en `horarios` y `horarios_historias` de `marca.json`), con la **API oficial de Meta**, así que no hay riesgo de bloqueo como con los bots.

## Afinar las gráficas y el contenido
- `marca/marca.json`: nombre, colores, teléfono, web, tono, servicios, lista de temas, hashtags fijos, hora de publicación.
- `marca/logo.png` y `marca/logo-blanco.png` (fondo transparente): el logo en rojo para las láminas blancas y en blanco para las portadas rojas. `logo-original.png` es el archivo entregado.
- `marca/fuentes/` (opcional): pon ahí la tipografía de la marca (`.ttf`; la primera en orden alfabético es la negrita, la segunda la normal). Sin ella se usa DejaVu Sans.
- `marca/fotos/`: fotos reales de la empresa y `fotos.json` con una descripción de cada una; la IA elige la foto de cada lámina. Para agregar fotos, súbelas a esa carpeta y añade su línea en `fotos.json`.
- `marca/musica.mp3` (opcional, música libre de derechos): fondo de los reels. Sin ella, los reels van sin sonido.
- `diseno.py`: el diseño de las láminas en sí (márgenes, tamaños, franjas).
- Probar sin publicar: *Actions → Generar publicación de Instagram → Run workflow* (puedes forzar el tipo y pedir un tema). Abre un PR que puedes cerrar.

### Probar el diseño en Ubuntu
```
sudo apt install ffmpeg
pip install -r instagram/requirements.txt
export OPENAI_API_KEY=...   # o ANTHROPIC_API_KEY
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
1. **Cuenta profesional** (@ambulanciasahp ya lo es) **vinculada a una página de Facebook** de la empresa. Se revisa en Instagram → Perfil → Editar perfil → Página.
2. **App de Meta:** en https://developers.facebook.com/apps → *Crear app* → caso de uso *"Administrar mensajes y contenido en Instagram"*, sin portfolio comercial. Dentro del caso de uso, usar *"Configuración de la API con inicio de sesión con Facebook"* (Meta ya no ofrece el inicio de sesión de Instagram en apps nuevas).
3. **Token corto:** abre el [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/), elige la app, en *Permisos* agrega `instagram_basic`, `instagram_content_publishing`, `pages_show_list`, `pages_read_engagement` y `business_management`, y toca *Generate Access Token*. En la ventana, elige la página de AHP y la cuenta de Instagram.
4. **Token que no vence:** en tu computador corre `python3 instagram/obtener_token.py`. Pide el identificador y la clave secreta de la app (*Configuración de la app → Básica*) y el token corto, y muestra `IG_USER_ID` e `IG_ACCESS_TOKEN`.
5. **Clave de IA:** una de OpenAI (https://platform.openai.com/api-keys) o de Claude (https://console.anthropic.com, *API Keys*), con saldo. Cada publicación cuesta centavos de dólar. El modelo de OpenAI se cambia en `marca.json` (`modelo_openai`, hoy `gpt-5.6-luna`) o con la variable de GitHub `LLM_MODEL`; el de Claude, en `modelo`.
6. En este repo de GitHub: *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_USER_ID`
   - `IG_ACCESS_TOKEN`
   - `OPENAI_API_KEY` (o `ANTHROPIC_API_KEY` para usar Claude; si están las dos, se usa OpenAI)
7. Para que la generación pueda abrir los PR de revisión: *Settings → Actions → General → Workflow permissions* → marca **"Allow GitHub Actions to create and approve pull requests"**.
8. Prueba: *Actions → Publicar en Instagram → Run workflow* con "Solo probar" marcado.

La app puede quedarse en modo desarrollo: así funciona para tus propias cuentas sin revisión de Meta.

## Cosas a tener en cuenta
- **El token de página no vence**, salvo que cambies la contraseña de Facebook, quites la app o pierdas el acceso a la página. En ese caso, repite los pasos 3 y 4.
- **Fotos y repo público:** Instagram descarga las imágenes desde una URL pública; como este repo es público, se usa la de GitHub automáticamente (y todo lo generado queda visible en GitHub). Si algún día se hace privado, hay que definir la variable `MEDIA_BASE_URL` con otro lugar público. Los reels no tienen este problema: se suben directo desde el archivo.
- Videos pesados: GitHub acepta archivos de hasta 100 MB por archivo.
- Instagram permite hasta 100 publicaciones por API cada 24 horas.
- Si una publicación falla, la carpeta queda en la cola, la ejecución sale en rojo en *Actions* con el motivo, y se reintenta a la hora siguiente.

## Probar desde Ubuntu
```
DRY_RUN=1 python3 instagram/publicar.py          # muestra qué publicaría
IG_USER_ID=... IG_ACCESS_TOKEN=... python3 instagram/publicar.py   # publica de verdad
```
Solo usa Python 3.9+ (viene con Ubuntu 24), sin instalar nada más.

## Música

`marca/musica.mp3` es la pista base (aprobada); cada publicación lleva su propia variante del mismo estilo (tonalidad, tempo, progresión y ritmo distintos, elegidos a partir del nombre de la carpeta). Es una pista original (sin derechos de autor) compuesta por `musica.py`: deep house suave y sobrio a 121 BPM, con el piano en segundo plano, bombo y caja claros, sin siseo de fondo y con un final (remate, bombo, platillo suave y acorde) que cae justo cuando aparece el logo del cierre. Se usa en los reels y en las historias, que se publican como video de 15 s con animación (`historias_video` en `marca.json`; con `false` vuelven a ser imagen). Para cambiarla, reemplaza `marca/musica.mp3` por otra pista libre de derechos (por ejemplo, de la biblioteca de audio de YouTube) o vuelve a generarla con `python3 instagram/musica.py`. La API de Instagram no permite usar la biblioteca de música de la app.

## Calendario de contenidos

`calendario.json` define la planificación: fechas especiales de Chile y de la Región de Valparaíso (feriados, Teletón, Lo Vásquez, Navidad, Año Nuevo, Fiestas Patrias, días mundiales de salud, temporadas), un tema por mes y un foco por día de la semana. `generar.py` lo consulta para cada publicación: en una fecha especial todo el contenido del día se relaciona con ella; los días previos, las historias (y el día anterior también el feed) la anticipan; el resto sigue el tema del mes y el foco del día. Para agregar o corregir fechas (por ejemplo, una votación), edita `calendario.json`; las marcadas `confirmar` dependen de un decreto o anuncio oficial.

Las fotos de portada e historias rotan: `estado.json` guarda la foto usada en cada publicación y se evita repetir las más recientes.

