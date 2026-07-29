"""Loop común de los analizadores."""

from __future__ import annotations

import queue
import time
from typing import Callable


def analyzer_loop(name, input_queue, output_queue, stop_event, interval,
                  cycles, index: int, analyze: Callable):
    """Procesa el lote más reciente y publica una sección atómica."""
    last_run = 0.0
    latest_pids = []
    while not stop_event.is_set():
        try:
            while True:
                latest_pids = input_queue.get_nowait()
        except queue.Empty:
            pass
        with interval.get_lock():
            wait_time = max(0.05, float(interval.value))
        now = time.monotonic()
        if latest_pids and now - last_run >= wait_time:
            try:
                data = analyze(latest_pids)
                output_queue.put((name, data, time.time()), timeout=0.5)
                with cycles.get_lock():
                    cycles[index] += 1
            except (OSError, ValueError):
                pass
            last_run = now
        stop_event.wait(0.1)
