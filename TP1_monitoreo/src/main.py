"""Entry point y supervisor de la arquitectura multiproceso."""

from __future__ import annotations

import json
import multiprocessing as mp
import signal
import sys
import time
from pathlib import Path

from src.agregador import aggregator_loop
from src.analizadores import fds, memoria, resumen, scheduling, senales as ansig
from src.analizadores import sistema, threads
from src.analizadores.comun import analyzer_loop
from src.display import display_process
from src.recolector import collector_loop
from src.senales import SignalCoordinator, dump_snapshot, load_config

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
ANALYZERS = [
    ("resumen", resumen.analyze), ("memoria", memoria.analyze),
    ("fds", fds.analyze), ("threads", threads.analyze),
    ("senales", ansig.analyze), ("scheduling", scheduling.analyze),
    ("sistema", sistema.analyze),
]


def apply_config(config, intervals, minimums, filters=None):
    values = config.get("intervalos", {})
    for index, (name, _function) in enumerate(ANALYZERS):
        requested = float(values.get(name, intervals[index].value))
        with intervals[index].get_lock():
            intervals[index].value = max(minimums[index], requested)
    if filters is not None:
        defaults = config.get("filtros", {})
        filters["comando"] = str(defaults.get("comando", ""))
        filters["usuario"] = str(defaults.get("usuario", ""))


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit("Este monitor requiere Linux; ejecutalo con Docker.")
    mp.set_start_method("spawn")
    config = load_config(CONFIG)
    defaults = config["intervalos"]
    minimum_map = config["minimos"]
    names = [item[0] for item in ANALYZERS]
    minimums = [float(minimum_map[name]) for name in names]

    ctx = mp.get_context()
    manager = ctx.Manager()
    snapshot = manager.dict()
    filters = manager.dict(config.get("filtros", {}))
    snapshot_lock = ctx.Lock()
    stop_event = ctx.Event()
    result_queue = ctx.Queue(maxsize=32)
    task_queues = [ctx.Queue(maxsize=1) for _ in ANALYZERS]
    intervals = [ctx.Value("d", float(defaults[name])) for name in names]
    cycles = ctx.Array("L", len(ANALYZERS), lock=True)
    verbose = ctx.Value("b", False)
    parent_control, child_control = ctx.Pipe(duplex=False)

    processes = [
        ctx.Process(name="recolector", target=collector_loop,
                    args=(task_queues, stop_event)),
        ctx.Process(name="agregador", target=aggregator_loop,
                    args=(result_queue, snapshot, snapshot_lock, stop_event)),
    ]
    for index, ((name, function), task_queue) in enumerate(
            zip(ANALYZERS, task_queues)):
        processes.append(ctx.Process(
            name=f"analizador-{name}", target=analyzer_loop,
            args=(name, task_queue, result_queue, stop_event,
                  intervals[index], cycles, index, function)))
    processes.append(ctx.Process(
        name="display", target=display_process,
        args=(snapshot, snapshot_lock, intervals, minimums, child_control,
              stop_event, verbose, filters)))

    coordinator = SignalCoordinator()
    for process in processes:
        process.start()
    try:
        while not stop_event.is_set():
            if parent_control.poll(0.1):
                message = parent_control.recv()
                if message.get("action") == "quit":
                    stop_event.set()
            for signum in coordinator.pending():
                if signum in (signal.SIGINT, signal.SIGTERM):
                    stop_event.set()
                elif signum == getattr(signal, "SIGHUP", -1):
                    apply_config(load_config(CONFIG), intervals, minimums,
                                 filters)
                elif signum == getattr(signal, "SIGUSR1", -1):
                    dump_snapshot(snapshot, snapshot_lock, ROOT)
                elif signum == getattr(signal, "SIGUSR2", -1):
                    with verbose.get_lock():
                        verbose.value = not verbose.value
                # SIGWINCH no necesita trabajo: curses consulta el tamaño.
            failed = [p for p in processes[:-1]
                      if p.exitcode not in (None, 0)]
            if failed:
                raise RuntimeError(
                    "Proceso hijo finalizó inesperadamente: " +
                    ", ".join(p.name for p in failed))
    except (EOFError, KeyboardInterrupt):
        stop_event.set()
    finally:
        stop_event.set()
        for process in processes:
            process.join(timeout=3)
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
        coordinator.close()
        parent_control.close()
        child_control.close()
        for target in task_queues + [result_queue]:
            target.close()
            target.join_thread()
        manager.shutdown()


if __name__ == "__main__":
    main()
