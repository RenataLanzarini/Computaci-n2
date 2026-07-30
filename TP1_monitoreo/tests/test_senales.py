import json
import tempfile
import threading
import unittest
from pathlib import Path

from src.senales import dump_snapshot


class SignalActionsTests(unittest.TestCase):
    def test_dump_contains_all_snapshot_sections_and_timestamps(self):
        names = (
            "resumen",
            "memoria",
            "fds",
            "threads",
            "senales",
            "scheduling",
            "sistema",
        )
        snapshot = {
            name: {"datos": {"pid": 42}, "ts": 1234.5}
            for name in names
        }

        with tempfile.TemporaryDirectory() as directory:
            destination = dump_snapshot(
                snapshot,
                threading.Lock(),
                Path(directory),
            )
            data = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(set(data), set(names))
        for section in data.values():
            self.assertEqual(section["datos"], {"pid": 42})
            self.assertEqual(section["ts"], 1234.5)


if __name__ == "__main__":
    unittest.main()
