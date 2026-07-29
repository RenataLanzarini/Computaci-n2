"""Memoria virtual, faults y segmentos."""

from src import procfs

KEYS = ("VmSize", "VmRSS", "VmData", "VmStk", "VmExe", "VmLib",
        "VmHWM", "VmSwap")


def analyze(pids):
    result = {}
    for pid in pids:
        try:
            status = procfs.read_status(pid)
            stat = procfs.read_stat(pid)
            try:
                maps = procfs.group_maps(
                    procfs.read_text(procfs.PROC_ROOT / str(pid) / "maps"))
            except procfs.TRANSIENT_ERRORS:
                maps = {}
            result[str(pid)] = {
                **{key: procfs.numeric_value(status.get(key, "0"))
                   for key in KEYS},
                "minor_faults": stat["minflt"],
                "child_minor_faults": stat["cminflt"],
                "major_faults": stat["majflt"],
                "child_major_faults": stat["cmajflt"],
                "segmentos_bytes": maps,
            }
        except procfs.TRANSIENT_ERRORS + (ValueError, OSError):
            continue
    return result
