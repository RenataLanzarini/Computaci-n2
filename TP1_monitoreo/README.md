# Monitor de Procesos y Threads

## Descripción general

Trabajo Práctico Nº 1 de Computación II (Universidad de Mendoza, 2026).
Inspecciona directamente `/proc` y presenta en tiempo real la anatomía de los
procesos Linux, sin `psutil` ni comandos externos.

## Cómo usarlo

Se necesita Docker con Compose:

```bash
docker compose up --build
```

En Docker Desktop para Windows, `docker compose up` puede mostrar la TUI sin
reenviar las teclas al contenedor. Para una sesión interactiva se usa:

```bash
docker compose run --build --rm monitor
```

Este comando utiliza el mismo servicio y la misma imagen, pero conecta el
teclado directamente. En Linux se puede usar normalmente el comando obligatorio
`docker compose up --build`.

La TUI permite cambiar de vista con `1`–`7` o `r/m/f/t/s/p/g`, navegar con
flechas, fijar un PID con Enter, cambiar orden con `c`, ajustar el intervalo con
`+`/`-`, mostrar ayuda con `h`/`?` y salir con `q`. `/` filtra por comando y
`u` filtra por usuario. Para quitar cualquiera de esos filtros hay que usar su
tecla otra vez y confirmar una entrada vacía.

## Arquitectura

```text
                        Manager.dict + Lock
                     ┌───────────────────────┐
                     │    snapshot global    │──► Display curses
                     └──────────▲────────────┘       │
                                │                    │ Pipe control
                         Agregador único             ▼
                                ▲                 Supervisor
                                │ Queue resultados   │
       ┌────────┬────────┬──────┴───┬────────┬──────┴───┬────────┐
       │Resumen │Memoria │   FDs    │Threads │ Señales  │Sched.  │Sistema
       └────▲───┴───▲────┴────▲─────┴───▲────┴────▲─────┴───▲────┴──▲────┘
            └───────┴─────────┴─────────┴─────────┴─────────┴───────┘
                         Queue propia por analizador
                                      ▲
                                  Recolector
                                      │
                                    /proc
```

Hay siete analizadores persistentes, cada uno en un proceso y con su propio
`multiprocessing.Value` de intervalo. Un `Array` guarda sus ciclos. El
recolector evita bloquearse si un consumidor se retrasa conservando el lote de
PID más reciente.

## Decisiones de diseño

`Queue` transporta lotes y resultados porque representa naturalmente mensajes
productor–consumidor. Cada analizador tiene una cola: una única cola repartiría
los PID entre ellos en lugar de enviar el lote a los siete.

El snapshot usa `Manager.dict` porque sus secciones son diccionarios dinámicos.
`Value` y `Array` son más eficientes para valores fijos, pero no pueden
representar cómodamente la información variable de cientos de procesos. El
agregador es el único escritor y reemplaza una sección bajo `Lock`; el display
copia el snapshot bajo el mismo lock. Así no observa una actualización parcial.

Los intervalos por defecto equilibran costo y volatilidad: CPU y threads
cambian rápido; señales y scheduling suelen ser estables; enumerar FDs puede
ser costoso. Los mínimos impuestos evitan una carga accidental excesiva.

Las señales usan `signal.set_wakeup_fd` con un socketpair. El handler no
serializa JSON, no imprime y no adquiere locks; el loop supervisor efectúa
shutdown, reload, dump o verbose fuera del contexto asíncrono.

## Decisiones sobre la TUI

Se eligió `curses` porque forma parte de la biblioteca estándar, controla el
repintado de una terminal interactiva sin agregar dependencias y permite leer
teclas especiales como las flechas. La pantalla se divide aproximadamente por
la mitad: arriba permanece la lista resumida de procesos y abajo cambia el
detalle de la vista activa. Esta distribución conserva el contexto del proceso
seleccionado al alternar entre las siete dimensiones.

El display trabaja con una copia del snapshot tomada bajo lock. Después libera
el lock y recién entonces ordena, filtra y dibuja; de esa forma no bloquea al
agregador durante operaciones relativamente lentas de terminal.

## Conceptos del curso aplicados

- **Clase 3 — Procesos y `/proc`:** `src/procfs.py` lee `stat`, `status`,
  `maps`, `fd` y `task` para obtener estado, memoria, FDs y LWPs directamente
  del kernel.
- **Clase 4 — `fork`, `exec`, `wait` y zombies:** la vista Sistema reconoce un
  zombie por el estado `Z`. Es un proceso terminado cuya entrada permanece
  porque su padre todavía no ejecutó `wait()`. El supervisor usa `join()` para
  esperar a sus hijos y evitar dejarlos en ese estado.
- **Clase 5 — Pipes:** el `Pipe` entre display y supervisor transporta mensajes
  de control, mientras las `Queue` implementan el patrón
  productor–consumidor para lotes de PID y resultados.
- **Clase 6 — Señales:** `src/senales.py` usa `signal.set_wakeup_fd` y un
  socketpair. El handler permanece mínimo y el supervisor ejecuta después las
  acciones de cierre, recarga, dump y modo detallado.
- **Clase 7 — Memoria compartida:** el snapshot y los valores de control son
  accesibles por varios procesos y se protegen con locks cuando una operación
  compuesta debe ser atómica.
- **Clases 8 y 9 — Multiprocessing:** los siete analizadores son procesos
  independientes. `Manager.dict` representa el snapshot dinámico, `Value`
  guarda escalares compartidos y `Array` mantiene los contadores de ciclos.
- **Clase 10 — Threads y GIL:** `/proc/PID/task/TID` permite observar los LWPs
  y sus context switches. Los analizadores son procesos, no threads, por lo que
  cada uno tiene su propio intérprete y su propio GIL.
- **Clase 11 — Sincronización:** los locks protegen operaciones compuestas y el
  agregador actúa como único escritor para impedir actualizaciones parciales
  del snapshot.
- **Scheduler:** nice, prioridad, policy, afinidad y cambios de contexto se
  leen del kernel, no se estiman mediante herramientas externas.

## Señales del monitor

- `SIGINT` y `SIGTERM`: cierre coordinado y espera de hijos.
- `SIGHUP`: relee `config.json` respetando intervalos mínimos.
- `SIGUSR1`: escribe `dump_YYYYMMDD_HHMMSS.json`.
- `SIGUSR2`: alterna detalle verbose (más FDs).
- `SIGWINCH`: el siguiente repintado usa el nuevo tamaño.

`config.json` está montado en modo de solo lectura desde el directorio del
repositorio. Por eso se puede editar en el host y luego enviar SIGHUP sin
reconstruir la imagen. Los valores recargados nunca bajan del intervalo mínimo
de cada vista.

Ejemplo desde otra terminal:

```bash
docker compose kill -s USR1 monitor
```

El dump se genera dentro del contenedor en `/app` con un nombre como
`dump_20260729_231500.json`. Mientras el servicio está activo se puede consultar
su nombre y copiarlo al host con:

```bash
docker compose exec monitor sh -c 'ls /app/dump_*.json'
docker compose cp monitor:/app/dump_20260729_231500.json .
```

## Limitaciones conocidas

El proyecto es Linux-only. Los permisos de `/proc` pueden ocultar información.
Los procesos pueden desaparecer durante una lectura y entonces se omiten hasta
el próximo ciclo. CPU% es cero en la primera muestra. `Manager` prioriza
claridad y flexibilidad pedagógica sobre rendimiento extremo. La TUI requiere
una terminal interactiva.

## Cómo testear

```bash
docker build -t tp1-monitor .
docker run --rm tp1-monitor python -m unittest discover -v
docker run --rm tp1-monitor python -m compileall -q src tests
docker compose up --build
```

Para la prueba manual se recorren las siete vistas, todos los controles y las
cinco señales obligatorias. Este repositorio conserva únicamente la
documentación técnica necesaria para ejecutar, probar y entregar el monitor.

### Prueba manual de las señales

Primero se levanta el monitor:

```bash
docker compose up --build
```

Desde otra terminal se pueden probar las señales que no finalizan el servicio:

```bash
# Editar config.json en el host y recargar intervalos y filtros.
docker compose kill -s HUP monitor

# Crear /app/dump_<timestamp>.json dentro del contenedor.
docker compose kill -s USR1 monitor

# Activar el modo detallado; repetir para volver al modo normal.
docker compose kill -s USR2 monitor
docker compose kill -s USR2 monitor
```

Para comprobar cada señal de cierre hay que levantar nuevamente el servicio
entre una prueba y la siguiente:

```bash
docker compose kill -s INT monitor
docker compose up -d
docker compose kill -s TERM monitor
```

Después de SIGINT o SIGTERM, `docker compose ps` no debe mostrar el servicio en
ejecución. Para terminar una sesión normal desde la TUI se usa `q`.

## Estructura

`src/procfs.py` concentra parsing robusto; `src/analizadores/` contiene las
siete dimensiones; `recolector.py`, `agregador.py`, `display.py`, `senales.py`
y `main.py` implementan los componentes de la arquitectura.

## Lo que aprendí

La principal diferencia respecto de consultar `ps` es observar que los datos
no forman una foto atómica: cada archivo y cada PID puede cambiar durante la
lectura. Diseñar un monitor exige aceptar esa carrera y representar muestras
con timestamp, en vez de fingir una consistencia que el kernel no ofrece.

También resulta concreto que “memoria compartida” no significa “sin costo” ni
“automáticamente segura”. Un Manager serializa datos y toda actualización
compuesta necesita una política de sincronización. Separar transporte,
agregación y presentación hace esas decisiones visibles y defendibles.
