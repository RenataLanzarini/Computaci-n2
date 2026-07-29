"""Estadísticas globales del sistema."""

from src import procfs

_previous_cpu = None


def analyze(_pids):
    global _previous_cpu
    stat_text = procfs.read_text(procfs.PROC_ROOT / "stat")
    lines = stat_text.splitlines()
    current_cpu = procfs.parse_cpu_line(lines[0])
    cpu = procfs.cpu_percentages(_previous_cpu or current_cpu, current_cpu)
    _previous_cpu = current_cpu
    mem = procfs.parse_status(procfs.read_text(procfs.PROC_ROOT / "meminfo"))
    load = procfs.read_text(procfs.PROC_ROOT / "loadavg").split()
    uptime = float(procfs.read_text(procfs.PROC_ROOT / "uptime").split()[0])
    btime = next((int(line.split()[1]) for line in lines
                  if line.startswith("btime ")), 0)
    states = {}
    threads = 0
    for pid in procfs.list_pids():
        try:
            item = procfs.read_stat(pid)
            states[item["state"]] = states.get(item["state"], 0) + 1
            threads += item["num_threads"]
        except procfs.TRANSIENT_ERRORS + (ValueError, OSError):
            continue
    keys = ("MemTotal", "MemFree", "Buffers", "Cached", "SwapTotal",
            "SwapFree")
    return {
        "cpu": cpu, "load": load[:3],
        "memoria": {key: procfs.numeric_value(mem.get(key, "0"))
                    for key in keys},
        "procesos": sum(states.values()), "estados": states,
        "threads": threads, "zombies": states.get("Z", 0),
        "boot_time": btime, "uptime": uptime,
    }
