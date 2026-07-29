"""Recolector central de PID."""

import queue

from src.procfs import list_pids


def collector_loop(queues, stop_event):
    while not stop_event.is_set():
        pids = list_pids()
        for target in queues:
            try:
                while True:
                    target.get_nowait()
            except queue.Empty:
                pass
            try:
                target.put_nowait(pids)
            except queue.Full:
                pass
        stop_event.wait(0.5)
