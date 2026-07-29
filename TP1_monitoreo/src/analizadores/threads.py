"""Threads Linux (LWPs) por proceso."""

import os
import time

from src import procfs

_previous = {}
_previous_time = None


def analyze(pids):
    global _previous_time
    now = time.monotonic()
    elapsed = now - _previous_time if _previous_time else 0
    ticks = os.sysconf("SC_CLK_TCK")
    current = {}
    result = {}
    for pid in pids:
        task = procfs.PROC_ROOT / str(pid) / "task"
        try:
            items = []
            for name in os.listdir(task):
                if not name.isdigit():
                    continue
                tid = int(name)
                try:
                    stat = procfs.parse_stat(
                        procfs.read_text(task / name / "stat"))
                    status = procfs.parse_status(
                        procfs.read_text(task / name / "status"))
                    total = stat["utime"] + stat["stime"]
                    current[(pid, tid)] = total
                    old = _previous.get((pid, tid), total)
                    cpu = 100 * (total - old) / ticks / elapsed if elapsed else 0
                    items.append({
                        "tid": tid,
                        "nombre": procfs.read_text(task / name / "comm"),
                        "estado": stat["state"], "cpu": max(0.0, cpu),
                        "voluntary": procfs.numeric_value(
                            status.get("voluntary_ctxt_switches", "0")),
                        "involuntary": procfs.numeric_value(
                            status.get("nonvoluntary_ctxt_switches", "0")),
                    })
                except procfs.TRANSIENT_ERRORS + (ValueError, OSError):
                    continue
            result[str(pid)] = {"threads": items}
        except procfs.TRANSIENT_ERRORS:
            continue
    _previous.clear()
    _previous.update(current)
    _previous_time = now
    return result
