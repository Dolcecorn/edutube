# edutube para iPhone: YouTube sin anuncios

La misma idea que la app de la TV, pero para iPhone (y iPad): abre YouTube a pantalla completa, bloquea anuncios y recuerda tu sesión.

## Qué hace
- Abre **m.youtube.com** (la versión para teléfonos) al iniciar, con la misma animación de la TV (anillo rojo que gira alrededor de un botón de play).
- Bloquea ~76.000 dominios de anuncios y rastreo (lista StevenBlack) más las redes de anuncios de video (Google IMA/DoubleClick, etc.). La primera vez que se abre, el iPhone tarda unos segundos en preparar la lista completa; después queda guardada.
- **YouTube:** quita los anuncios de las respuestas de YouTube antes de que el reproductor los lea (antes, durante y después del video, y los promocionados de la portada y la búsqueda). Si alguno se cuela, lo adelanta y presiona "Omitir".
- **Sigue sonando con la pantalla bloqueada** o al cambiar de app (se puede apagar en el menú). Si iOS lo pausa, se reanuda desde el centro de control.
- **Transmitir a la TV / Chromecast (v1.3):** botón rojo con una TV abajo a la derecha cuando hay un video abierto. Muestra los Chromecast de tu Wi-Fi (los encuentra solos; la primera vez iOS pide permiso de "Red local", hay que aceptarlo) y envía el video en el mismo segundo. También se puede vincular una TV con "Vincular con código de TV" (YouTube de la TV → Configuración).
- **Anuncios en el Chromecast (v1.4):** el Chromecast pide sus propios anuncios, así que los bloqueos del iPhone no le llegan. Mientras edutube siga abierto (o en segundo plano), escucha a la TV: si empieza un anuncio lo silencia y lo omite apenas YouTube lo permite.
- **Saltar anuncios a mitad del video (v1.5):** si en el Chromecast aparece un anuncio en medio del video, edutube vuelve a cargar el mismo video un segundo después de donde iba. Si YouTube insiste con el anuncio, se silencia y se omite como en la v1.4.
- **Cualquier página en la TV (v1.6):** en el menú, "Ir a una página…" abre cualquier link o búsqueda (con el mismo bloqueo de anuncios). Si la página tiene un video, aparece el botón rojo: envía solo el video al Chromecast, a pantalla completa y en el mismo segundo. No sirve con sitios con protección anticopia (Netflix, Disney+, etc.) ni con los que solo dejan ver el video dentro de su página.
- **Espejo de pantalla (v1.7, experimental):** menú → "Espejo de pantalla en la TV" → "Iniciar transmisión" → elegir el Chromecast. Muestra toda la pantalla del iPhone en la TV (con unos segundos de retraso). Para terminar: punto rojo arriba o Centro de control → Detener.
- **Espejo y videos de X (v1.8):** el espejo ya no sale de cabeza con el iPhone de lado, no se corta cuando la pantalla queda quieta y tiene menos retraso (unos 2 a 3 segundos). En un post de X (Twitter) con video, el botón rojo envía ese video al Chromecast.
- **TV gratis (v1.9):** menú → "📺 TV gratis" (o mantener el ícono de edutube → "TV gratis"). Catálogo de fuentes **solo oficiales, legales y gratuitas**: señales en vivo de 24 Horas, T13, CHV y Meganoticias, páginas en vivo de Canal 13/TVN/Mega/CHV, Pluto TV, Plex, Red Bull TV, FIFA+, automovilismo (GT World Challenge e IMSA con carreras completas gratis; WEC, Fórmula E, F1, IndyCar, NASCAR, MotoGP, WRC con resúmenes oficiales), fútbol (chileno, CONMEBOL, MLS, LaLiga, Premier, Serie A, Bundesliga, Champions: resúmenes oficiales), películas y series (Pluto, Ondamedia, CNTV Play, Plex, ViX gratis, Tubi, clásicos de dominio público) y cortometrajes. Todo va al Chromecast con el botón rojo; si una página no deja enviar su video, el mismo botón ofrece el espejo de pantalla. En los servicios que viven de la publicidad (Pluto, Plex, canales chilenos, etc.) no se bloquean anuncios, para que sus reproductores funcionen. Los partidos y carreras completos en vivo de las ligas grandes (F1, Campeonato chileno, Libertadores, MLS, Europa) son de pago y no están. En el menú se puede elegir "Abrir TV gratis al iniciar".
- **Barra de carga (v1.4):** cuando un video carga aparece una barra roja delgada abajo, en vez del ícono grande.
- Imagen en imagen (PiP) desde el botón del reproductor en pantalla completa.
- **Video fluido:** revisa qué formatos decodifica tu iPhone por hardware y le oculta a YouTube los demás (AV1 en casi todos los modelos), con tope de 1080p. "Máxima fluidez" fuerza H.264 a 30 fps para iPhones antiguos.
- Bloquea ventanas emergentes y los saltos a la app oficial de YouTube o a la App Store.
- La sesión de Google queda guardada aunque cierres la app.

## Gestos
| Gesto | Acción |
|---|---|
| Deslizar desde el borde izquierdo | Página anterior |
| Tirar hacia abajo | Recargar |
| Mantener con **dos dedos**, o agitar el iPhone | Menú: ir al inicio, ir a una página, recargar, cambiar página fija, segundo plano, máxima fluidez |

## Instalar sin Mac (desde Ubuntu)
Apple no deja instalar apps fuera de la App Store sin firmarlas. Con un Apple ID gratis la firma dura **7 días**; luego hay que volver a instalarla (se conservan la sesión y los ajustes). Con la cuenta de desarrollador pagada (USD 99/año) dura un año.

1. **Compilar:** sube esta carpeta a un repositorio tuyo en GitHub. GitHub compila la app sola en un Mac de ellos (pestaña *Actions*) y deja `edutube.ipa` en *Releases → ultima*.
2. **Instalar Impactor** en Ubuntu (instalador gratuito para firmar e instalar apps en el iPhone): descarga el `.AppImage` de https://github.com/claration/Impactor/releases y dale permiso de ejecución (`chmod +x`). Necesita `usbmuxd` (`sudo apt install usbmuxd`).
3. Conecta el iPhone por cable, desbloquéalo y toca **Confiar en este computador**.
4. En Impactor: inicia sesión con tu Apple ID, arrastra `edutube.ipa` e instala.
5. En el iPhone:
   - **Ajustes → Privacidad y seguridad → Modo de desarrollador → Activar** (pide reiniciar).
   - **Ajustes → General → VPN y gestión de dispositivos →** tu Apple ID **→ Confiar**.
6. Abre **edutube**.

Con Windows se puede usar Sideloadly en vez de Impactor; con un Mac, `xcodegen generate` y abrir `TVWeb.xcodeproj` en Xcode.

## Compilar en un Mac
```
brew install xcodegen
xcodegen generate
open TVWeb.xcodeproj
```

## Archivos
- `Sources/WebViewController.swift`: navegador, menú, segundo plano.
- `Sources/AdBlocker.swift`: convierte las listas en reglas de bloqueo de WebKit.
- `Sources/Scripts.swift`: código que quita anuncios de YouTube, formatos de video y segundo plano.
- `Sources/LoadingView.swift`: la animación de carga.
- `Resources/adhosts.txt`, `Resources/extra_hosts.txt`: las mismas listas que la app de la TV.

## Otras herramientas en este repo
- [`instagram/`](instagram/LEEME.md): publicación automática de posts y reels en Instagram.
