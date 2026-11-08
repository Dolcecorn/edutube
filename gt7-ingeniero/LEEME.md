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
- "Quedan dos vueltas", "Última vuelta" y bandera a cuadros.
- Tocando la barra de abajo te dice el estado completo cuando quieras.

GT7 no manda el desgaste de neumáticos ni la posición en carrera, así que eso no aparece.

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
`javac -d /tmp/t src/cl/eleva/gt7/{Salsa20,Telemetry,Engineer,Simulator,Painter,Dashboard}.java test/cl/eleva/gt7/*.java && java -cp /tmp/t cl.eleva.gt7.SimTest`
simula una carrera de 10 vueltas e imprime lo que diría el ingeniero; `Preview <carpeta>` dibuja el dashboard en PNG.

Formato de la telemetría: paquete "A" de 296 bytes cifrado con Salsa20, documentado por la comunidad
(proyectos gt7telemetry y PDTools).
