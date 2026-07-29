"""Lectores y parsers de procfs sin dependencias externas."""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Any, Iterable

try:
    import pwd
except ImportError:  # Permite probar parsers en Windows; producción es Linux.
    pwd = None  # type: ignore[assignment]

PROC_ROOT = Path("/proc")
TRANSIENT_ERRORS = (FileNotFoundError, PermissionError, ProcessLookupError)


def list_pids(root: Path = PROC_ROOT) -> list[int]:
    """Devuelve los directorios PID presentes, ordenados numéricamente."""
    try:
        return sorted(int(entry.name) for entry in root.iterdir()
                      if entry.name.isdigit() and entry.is_dir())
    except (FileNotFoundError, PermissionError):
        return []


def read_text(path: Path, *, nul: bool = False) -> str:
    data = path.read_bytes()
    if nul:
        return data.replace(b"\0", b" ").decode(errors="replace").strip()
    return data.decode(errors="replace").strip()


def parse_status(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            result[key] = value.strip()
    return result


def read_status(pid: int, root: Path = PROC_ROOT) -> dict[str, str]:
    return parse_status(read_text(root / str(pid) / "status"))


def parse_stat(text: str) -> dict[str, Any]:
    """Parsea /proc/PID/stat preservando nombres que contienen espacios."""
    left = text.find("(")
    right = text.rfind(")")
    if left < 0 or right <= left:
        raise ValueError("formato stat inválido")
    pid = int(text[:left].strip())
    comm = text[left + 1:right]
    fields = text[right + 2:].split()
    if len(fields) < 39:
        raise ValueError("stat incompleto")

    def field(number: int) -> str:
        return fields[number - 3]

    return {
        "pid": pid,
        "comm": comm,
        "state": field(3),
        "ppid": int(field(4)),
        "pgid": int(field(5)),
        "sid": int(field(6)),
        "minflt": int(field(10)),
        "cminflt": int(field(11)),
        "majflt": int(field(12)),
        "cmajflt": int(field(13)),
        "utime": int(field(14)),
        "stime": int(field(15)),
        "priority": int(field(18)),
        "nice": int(field(19)),
        "num_threads": int(field(20)),
        "rt_priority": int(field(40)),
        "policy": int(field(41)),
    }


def read_stat(pid: int, root: Path = PROC_ROOT) -> dict[str, Any]:
    return parse_stat(read_text(root / str(pid) / "stat"))


def numeric_value(value: str, default: int = 0) -> int:
    """Extrae el primer entero (los valores de memoria quedan en KiB)."""
    try:
        return int(value.split()[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        return default


def ids_and_user(status: dict[str, str]) -> dict[str, Any]:
    uid = numeric_value(status.get("Uid", "0"))
    gid = numeric_value(status.get("Gid", "0"))
    try:
        user = pwd.getpwuid(uid).pw_name if pwd is not None else str(uid)
    except KeyError:
        user = str(uid)
    return {"uid": uid, "gid": gid, "usuario": user}


def read_cmdline(pid: int, fallback: str, root: Path = PROC_ROOT) -> str:
    try:
        return read_text(root / str(pid) / "cmdline", nul=True) or fallback
    except TRANSIENT_ERRORS:
        return fallback


def decode_signal_mask(raw: str) -> list[str]:
    try:
        mask = int(raw, 16)
    except (TypeError, ValueError):
        return []
    names: list[str] = []
    for number in range(1, 65):
        if mask & (1 << (number - 1)):
            try:
                names.append(signal.Signals(number).name)
            except ValueError:
                names.append(f"SIG{number}")
    return names


FD_PREFIXES = {
    "socket:": "socket",
    "pipe:": "pipe",
    "anon_inode:": "anon_inode",
    "/dev/pts/": "tty",
    "/dev/tty": "tty",
}


def classify_fd(target: str) -> str:
    for prefix, fd_type in FD_PREFIXES.items():
        if target.startswith(prefix):
            return fd_type
    return "file" if target.startswith("/") else "otro"


def parse_cpu_line(text: str) -> tuple[int, ...]:
    parts = text.split()
    if not parts or parts[0] != "cpu":
        raise ValueError("línea global de CPU inválida")
    return tuple(int(item) for item in parts[1:])


def cpu_percentages(previous: Iterable[int],
                    current: Iterable[int]) -> dict[str, float]:
    old, new = tuple(previous), tuple(current)
    length = min(len(old), len(new))
    delta = [max(0, new[i] - old[i]) for i in range(length)]
    total = sum(delta)
    if not total:
        return {"user": 0.0, "system": 0.0, "idle": 0.0, "iowait": 0.0}
    value = lambda index: 100.0 * delta[index] / total if index < length else 0.0
    return {
        "user": value(0) + value(1),
        "system": value(2) + value(5) + value(6),
        "idle": value(3),
        "iowait": value(4),
    }


def group_maps(text: str) -> dict[str, int]:
    """Agrupa bytes virtuales de maps por finalidad aproximada."""
    groups = {"text": 0, "data": 0, "heap": 0, "stack": 0, "shared": 0}
    for line in text.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 2:
            continue
        try:
            start, end = (int(item, 16) for item in parts[0].split("-", 1))
        except ValueError:
            continue
        size = end - start
        perms = parts[1]
        path = parts[5] if len(parts) == 6 else ""
        if "[heap]" in path:
            group = "heap"
        elif "[stack" in path:
            group = "stack"
        elif "s" in perms:
            group = "shared"
        elif "x" in perms:
            group = "text"
        else:
            group = "data"
        groups[group] += size
    return groups


def safe_process(pid: int, reader: Any) -> Any | None:
    try:
        return reader(pid)
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError,
            OSError):
        return None
