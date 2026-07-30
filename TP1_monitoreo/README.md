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

- **Procesos y GIL:** los analizadores son procesos independientes, por lo que
  no comparten el intérprete ni su GIL.
- **`/proc`:** `stat`, `status`, `maps`, `fd` y `task` exponen estado del
  proceso, memoria, FDs y LWPs. Un zombie se reconoce por estado `Z`: terminó,
  pero su padre todavía no llamó a `wait()`.
- **IPC:** Queue y Pipe transmiten mensajes; Manager, Value y Array comparten
  estado. Cada mecanismo se elige según forma y cardinalidad del dato.
- **Sincronización:** locks protegen operaciones compuestas y un escritor único
  elimina competencia entre analizadores sobre el snapshot.
- **Threads:** `/proc/PID/task/TID` muestra los LWPs y sus context switches.
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
