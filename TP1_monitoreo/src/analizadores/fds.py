"""File descriptors abiertos."""

import os

from src import procfs


def analyze(pids):
    result = {}
    for pid in pids:
        directory = procfs.PROC_ROOT / str(pid) / "fd"
        try:
            fds = []
            for name in sorted(os.listdir(directory), key=int):
                try:
                    target = os.readlink(directory / name)
                    fds.append({"fd": int(name), "destino": target,
                                "tipo": procfs.classify_fd(target)})
                except procfs.TRANSIENT_ERRORS:
                    continue
            result[str(pid)] = {"cantidad": len(fds), "fds": fds}
        except procfs.TRANSIENT_ERRORS:
            continue
    return result
