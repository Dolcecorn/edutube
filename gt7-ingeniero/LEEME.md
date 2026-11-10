# Ingeniero GT7

App para tablet Android (4.1 o superior) que lee la telemetría de Gran Turismo 7 desde la PS5
por wifi, muestra un dashboard del auto y tiene un ingeniero de carreras que habla.

## Qué muestra
- Luces de cambio (RPM) arriba; parpadean en azul al llegar al corte.
- Marcha, velocidad, RPM, acelerador y freno.
- Vuelta actual/total, tiempo de vuelta actual, última, mejor y **delta en vivo** contra tu mejor vuelta.
- Combustible: %, consumo por vuelta, vueltas que alcanza y vueltas que faltan.
- Temperatura de los 4 neumáticos (azul frío, verde bien, amarillo tibio, rojo caliente), agua, aceite y turbo.

## Qué dice el ingeniero
- Al cerrar cada vuelta: tiempo, si fue tu mejor o cuánto más lento, y si te alcanza el combustible
  (o cuánto ahorrar por vuelta / que planifiques parada).
- A mitad de vuelta: cuántas décimas vas arriba o abajo.
- Combustible crítico, neumáticos muy calientes, motor caliente, carga de combustible en boxes.
- Consejos por curva: compara cada frenada con tu mejor vuelta (punto de frenada, velocidad en el vértice, cuándo aceleras a fondo y marcha de salida). Las curvas se detectan por la forma de la pista (cambio de rumbo), así las chicanas y las enlazadas cuentan por separado; se numeran desde la meta.
- "Quedan dos vueltas", "Última vuelta" y bandera a cuadros.
- Tocando la barra de abajo te dice el estado completo cuando quieras.

GT7 no manda el desgaste de neumáticos ni la posición en carrera, así que eso no aparece.

## Comandos de voz (botón RAD)
Preguntas nuevas (v1.8): "cómo estuvo la curva 2 en esta vuelta", "cómo voy en el sector dos", "dónde pierdo
más tiempo", "cuál es la vuelta ideal", "cuál es la estrategia", "en qué circuito estamos".
- "Desactiva/activa los consejos", "los tiempos", "el combustible", "los neumáticos", "el delta".
- "No me digas nada" (sólo plan de combustible, lo crítico y la bandera) / "Activa todo".
- "Ayuda" repite la lista. Lo que prendes o apagas queda guardado.

## En la parrilla y durante la carrera
- Al largar (vuelta 0 a 1): saludo, TCS y balance de frenos guardados para ese auto (SET, por código de auto) y un consejo de primera vuelta.
- Plan de combustible (1 o más paradas; si con un poco de ahorro alcanza con una sola, te dice cuánto) al cerrar la 1ª vuelta y cuando cambia (sin parar / parar en la vuelta N y cuánto cargar).
- Neumáticos en momentos clave: tras la 1ª vuelta, a mitad de carrera, a 3 del final y en la vuelta de parada.

## Boxes (v1.7)
GT7 no avisa cuándo entras a boxes; la app lo deduce: cerca de la meta, a más de 12 m de la línea de tu
mejor vuelta y lento por 2,5 s, o detenido cerca de la meta, o cuando sube el combustible. Al entrar te dice
tu mejor y tu promedio, cuánto tienes con tus mejores sectores, las 2 curvas donde más pierdes, tendencias
de sobre/subviraje y cuánto combustible cargar. Al salir avisa neumáticos fríos y el combustible.
Las vueltas con boxes salen con "P" en VUELTAS y no cuentan para la constancia ni las curvas.
Al entrar, lo primero es cuánto combustible cargar. Cuenta las paradas hechas: al salir dice "parada N lista"
y el plan siguiente parte de lo que cargaste. Mide cuánto te costó la parada y la velocidad de carga.

## Estrategia de combustible (v1.8)
Cada vuelta recalcula paradas con el consumo real. Si ahorrando hasta 15 % por vuelta te ahorras una parada,
compara lo que pierdes en pista (estimado: 10 % de ahorro ≈ 0,8 % del tiempo de vuelta) con lo que cuesta parar
(medido en tu parada, o 25 s estimados) y te dice si conviene y cómo: lift and coast en las 2 frenadas desde más
velocidad, cambio corto, o bajar el mapa de combustible. En la última parada te dice que cargues sólo lo necesario.
Habla sólo cuando cambia la recomendación; también se puede preguntar ("cuál es la estrategia").

## Circuitos, curvas y sectores (v1.8)
La app trae una base de 78 circuitos/variantes de GT7 (res/raw/pistas_gt7.txt). Tras la 1ª vuelta compara la
forma de tu vuelta con la base (mismo sentido, cualquier punto de partida) y te dice el nombre. Las curvas se
numeran desde la meta: en 6 pistas con vértices oficiales etiquetados (Monza, Spa... ver el archivo) se usan esos;
en el resto se ajusta la detección hasta tener la cantidad oficial de curvas del juego (en prueba: 74 de 78 exactas).
Si la pista no está en la base, la aprende (pistas.txt interno) y le puedes poner nombre en SET.
Sectores = tercios de la vuelta; vuelta ideal = suma de tus mejores sectores.
Datos: github.com/jbhoorasingh/gt7-datalogger-track-data (CC0) y github.com/zetetos/gt-telemetry (MIT).

## Análisis (desliza a la izquierda)
Pestañas RESUMEN, MAPA, CURVAS, VUELTAS y AUTO. 10 s después de la bandera a cuadros se abre solo en
RESUMEN (en puntos), el ingeniero da el resumen hablado (por partes, para que el motor de voz no lo corte) y guarda el historial en /sdcard/IngenieroGT7/carrera-FECHA.csv
(sacarlo con `adb pull /sdcard/IngenieroGT7/`). Desliza a la derecha o toca "< VOLANTE" para volver.

## Dinámica que vigila el ingeniero
- Bloqueo de ruedas al frenar y patinaje al acelerar (velocidad de cada rueda contra la del auto).
- Sobreviraje: la carrocería gira más rápido que la trayectoria.
- Subviraje: mucho volante para poca curva (necesita el paquete "B" de GT7 1.42+, que trae el volante).
- Sobre y subviraje sólo se comentan cuando se repiten en la misma curva (2 de las últimas 3 vueltas).
- Velocidad máxima de cada vuelta contra la de tu mejor vuelta.

## Reloj y batería (v1.8)
Abajo a la derecha: hora y batería de la tablet ("+" y verde = cargando, rojo = 15 % o menos).

## Botones
- Izquierda: RAD (preguntarle por voz: combustible, boxes, neumáticos, tiempos, vueltas que faltan), FUEL (combustible), TYR (neumáticos), LAP (tiempos), VOL-.
- Derecha: PIT (cuánto cargar en boxes), OK (repite el último mensaje), MUTE (silencia la voz), SET (ajustes), VOL+.

## Uso
1. PS5 y tablet en el mismo wifi. En GT7 no hay que activar nada.
2. Abre la app y entra a una carrera. La app busca la PS5 sola; si no la encuentra,
   en SET escribe la IP de la PS5 (PS5: Ajustes > Red > Estado de la conexión).
3. SET también tiene "Modo demostración" para ver la app funcionando sin PS5.

Si la voz no habla en español: Ajustes de Android > Idioma y entrada > Salida de texto a voz >
instalar datos de voz en español.

## Compilar
`./build.sh` (Ubuntu, sin Gradle). Pruebas en el computador:
`javac -d /tmp/t src/cl/eleva/gt7/{Salsa20,Telemetry,Engineer,Coach,Simulator,Painter,Dashboard}.java test/cl/eleva/gt7/*.java && java -cp /tmp/t cl.eleva.gt7.SimTest`
simula una carrera de 10 vueltas e imprime lo que diría el ingeniero; `Preview <carpeta>` dibuja el dashboard en PNG.

Formato de la telemetría: paquete "A" de 296 bytes cifrado con Salsa20, documentado por la comunidad
(proyectos gt7telemetry y PDTools).
