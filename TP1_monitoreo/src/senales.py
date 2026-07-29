"""Coordinación segura de señales mediante wakeup file descriptor."""

import json
import signal
import socket
from datetime import datetime
from pathlib import Path


class SignalCoordinator:
    def __init__(self):
        self.reader, self.writer = socket.socketpair()
        self.reader.setblocking(False)
        self.writer.setblocking(False)
        signal.set_wakeup_fd(self.writer.fileno())
        self._old = {}
        for signum in self.supported():
            self._old[signum] = signal.signal(signum, self._handler)

    @staticmethod
    def supported():
        names = ("SIGINT", "SIGTERM", "SIGHUP", "SIGUSR1", "SIGUSR2",
                 "SIGWINCH")
        return [getattr(signal, name) for name in names
                if hasattr(signal, name)]

    @staticmethod
    def _handler(_signum, _frame):
        # set_wakeup_fd efectúa la escritura; el handler no hace I/O ni locks.
        return None

    def pending(self):
        try:
            return list(self.reader.recv(1024))
        except BlockingIOError:
            return []

    def close(self):
        signal.set_wakeup_fd(-1)
        for signum, handler in self._old.items():
            signal.signal(signum, handler)
        self.reader.close()
        self.writer.close()


def load_config(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def dump_snapshot(snapshot, lock, directory: Path):
    with lock:
        data = dict(snapshot)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = directory / f"dump_{stamp}.json"
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return destination
