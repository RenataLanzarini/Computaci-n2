"""Datos básicos y CPU por proceso."""

import os
import time

from src import procfs

_previous = {}
_previous_time = None


def analyze(pids):
    global _previous_time
    now = time.monotonic()
    elapsed = now - _previous_time if _previous_time else 0.0
    ticks = os.sysconf("SC_CLK_TCK")
    result = {}
    current = {}
    for pid in pids:
        try:
            stat = procfs.read_stat(pid)
            status = procfs.read_status(pid)
            total = stat["utime"] + stat["stime"]
            current[pid] = total
            old = _previous.get(pid, total)
            cpu = 100.0 * (total - old) / ticks / elapsed if elapsed else 0.0
            item = {
                **procfs.ids_and_user(status),
                "pid": pid, "ppid": stat["ppid"], "estado": stat["state"],
                "comando": procfs.read_cmdline(pid, stat["comm"]),
                "cpu": max(0.0, cpu),
                "threads": procfs.numeric_value(status.get("Threads", "0")),
                "rss": procfs.numeric_value(status.get("VmRSS", "0")),
            }
            result[str(pid)] = item
        except procfs.TRANSIENT_ERRORS + (ValueError, OSError):
            continue
    _previous.clear()
    _previous.update(current)
    _previous_time = now
    return result
