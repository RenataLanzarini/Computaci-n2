"""Configuración de scheduling."""

from src import procfs

POLICIES = {0: "OTHER", 1: "FIFO", 2: "RR", 3: "BATCH", 5: "IDLE",
            6: "DEADLINE"}


def analyze(pids):
    result = {}
    for pid in pids:
        try:
            stat = procfs.read_stat(pid)
            status = procfs.read_status(pid)
            result[str(pid)] = {
                "nice": stat["nice"], "priority": stat["priority"],
                "policy": POLICIES.get(stat["policy"], str(stat["policy"])),
                "rt_priority": stat["rt_priority"],
                "affinity": status.get("Cpus_allowed_list", "?"),
                "voluntary": procfs.numeric_value(
                    status.get("voluntary_ctxt_switches", "0")),
                "involuntary": procfs.numeric_value(
                    status.get("nonvoluntary_ctxt_switches", "0")),
                "utime": stat["utime"], "stime": stat["stime"],
                "sid": stat["sid"], "pgid": stat["pgid"],
            }
        except procfs.TRANSIENT_ERRORS + (ValueError, OSError):
            continue
    return result
