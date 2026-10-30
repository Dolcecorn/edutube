# TV Web para iPhone: YouTube sin anuncios

La misma idea que la app de la TV, pero para iPhone (y iPad): abre YouTube a pantalla completa, bloquea anuncios y recuerda tu sesión.

## Qué hace
- Abre **m.youtube.com** (la versión para teléfonos) al iniciar, con la misma animación de la TV (anillo rojo que gira alrededor de un botón de play).
- Bloquea ~76.000 dominios de anuncios y rastreo (lista StevenBlack) más las redes de anuncios de video (Google IMA/DoubleClick, etc.). La primera vez que se abre, el iPhone tarda unos segundos en preparar la lista completa; después queda guardada.
- **YouTube:** quita los anuncios de las respuestas de YouTube antes de que el reproductor los lea (antes, durante y después del video, y los promocionados de la portada y la búsqueda). Si alguno se cuela, lo adelanta y presiona "Omitir".
- **Sigue sonando con la pantalla bloqueada** o al cambiar de app (se puede apagar en el menú). Si iOS lo pausa, se reanuda desde el centro de control.
- **Transmitir a la TV (v1.2):** botón rojo con una TV abajo a la derecha cuando hay un video abierto. Envía el video a la TV en el mismo segundo. Funciona con TV Web en la TV, con la app de YouTube de la TV o con Chromecast. La primera vez pide vincular: en la TV, YouTube → Configuración → "Vincular con código de TV", y escribes ese código en el iPhone. Mantener presionado el botón: vincular otra TV o desvincular.
- Imagen en imagen (PiP) desde el botón del reproductor en pantalla completa.
- **Video fluido:** revisa qué formatos decodifica tu iPhone por hardware y le oculta a YouTube los demás (AV1 en casi todos los modelos), con tope de 1080p. "Máxima fluidez" fuerza H.264 a 30 fps para iPhones antiguos.
- Bloquea ventanas emergentes y los saltos a la app oficial de YouTube o a la App Store.
- La sesión de Google queda guardada aunque cierres la app.

## Gestos
| Gesto | Acción |
|---|---|
| Deslizar desde el borde izquierdo | Página anterior |
| Tirar hacia abajo | Recargar |
| Mantener con **dos dedos**, o agitar el iPhone | Menú: ir al inicio, recargar, cambiar página fija, segundo plano, máxima fluidez |

## Instalar sin Mac (desde Ubuntu)
Apple no deja instalar apps fuera de la App Store sin firmarlas. Con un Apple ID gratis la firma dura **7 días**; luego hay que volver a instalarla (se conservan la sesión y los ajustes). Con la cuenta de desarrollador pagada (USD 99/año) dura un año.

1. **Compilar:** sube esta carpeta a un repositorio tuyo en GitHub. GitHub compila la app sola en un Mac de ellos (pestaña *Actions*) y deja `TVWeb.ipa` en *Releases → ultima*.
2. **Instalar Impactor** en Ubuntu (instalador gratuito para firmar e instalar apps en el iPhone): descarga el `.AppImage` de https://github.com/claration/Impactor/releases y dale permiso de ejecución (`chmod +x`). Necesita `usbmuxd` (`sudo apt install usbmuxd`).
3. Conecta el iPhone por cable, desbloquéalo y toca **Confiar en este computador**.
4. En Impactor: inicia sesión con tu Apple ID, arrastra `TVWeb.ipa` e instala.
5. En el iPhone:
   - **Ajustes → Privacidad y seguridad → Modo de desarrollador → Activar** (pide reiniciar).
   - **Ajustes → General → VPN y gestión de dispositivos →** tu Apple ID **→ Confiar**.
6. Abre **TV Web**.

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
