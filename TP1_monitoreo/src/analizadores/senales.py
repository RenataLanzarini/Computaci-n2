"""Máscaras de señales por proceso."""

from src import procfs

FIELDS = ("SigBlk", "SigIgn", "SigCgt", "SigPnd", "ShdPnd")


def analyze(pids):
    result = {}
    for pid in pids:
        try:
            status = procfs.read_status(pid)
            result[str(pid)] = {
                key: procfs.decode_signal_mask(status.get(key, "0"))
                for key in FIELDS
            }
        except procfs.TRANSIENT_ERRORS:
            continue
    return result
