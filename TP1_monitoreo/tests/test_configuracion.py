import json
import signal
import tempfile
import threading
import unittest
from pathlib import Path

from src.main import apply_config, handle_monitor_signal


class _Lock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Value:
    def __init__(self, value):
        self.value = value
        self._lock = _Lock()

    def get_lock(self):
        return self._lock


class ConfigurationTests(unittest.TestCase):
    def test_reload_updates_intervals_filters_and_respects_minimums(self):
        intervals = [_Value(99.0) for _ in range(7)]
        minimums = [0.5, 1.0, 2.0, 0.5, 5.0, 5.0, 1.0]
        filters = {"comando": "", "usuario": ""}
        config = {
            "intervalos": {
                "resumen": 0.1,
                "memoria": 2.5,
                "fds": 4.0,
                "threads": 1.5,
                "senales": 8.0,
                "scheduling": 9.0,
                "sistema": 1.5,
            },
            "filtros": {"comando": "python", "usuario": "root"},
        }

        apply_config(config, intervals, minimums, filters)

        self.assertEqual(
            [item.value for item in intervals],
            [0.5, 2.5, 4.0, 1.5, 8.0, 9.0, 1.5],
        )
        self.assertEqual(filters, {"comando": "python", "usuario": "root"})

    def test_monitor_signal_actions_reload_dump_verbose_and_shutdown(self):
        intervals = [_Value(99.0) for _ in range(7)]
        minimums = [0.5, 1.0, 2.0, 0.5, 5.0, 5.0, 1.0]
        filters = {"comando": "", "usuario": ""}
        verbose = _Value(False)
        stop_event = threading.Event()
        snapshot = {
            "resumen": {"datos": {"1": {"pid": 1}}, "ts": 10.0}
        }
        snapshot_lock = threading.Lock()
        config = {
            "intervalos": {
                "resumen": 0.5,
                "memoria": 1.0,
                "fds": 2.0,
                "threads": 0.5,
                "senales": 5.0,
                "scheduling": 5.0,
                "sistema": 1.0,
            },
            "filtros": {"comando": "python", "usuario": "root"},
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            handle_monitor_signal(
                signal.SIGHUP,
                intervals,
                minimums,
                filters,
                snapshot,
                snapshot_lock,
                verbose,
                stop_event,
                config_path,
                root,
            )
            dump_path = handle_monitor_signal(
                signal.SIGUSR1,
                intervals,
                minimums,
                filters,
                snapshot,
                snapshot_lock,
                verbose,
                stop_event,
                config_path,
                root,
            )
            handle_monitor_signal(
                signal.SIGUSR2,
                intervals,
                minimums,
                filters,
                snapshot,
                snapshot_lock,
                verbose,
                stop_event,
                config_path,
                root,
            )
            handle_monitor_signal(
                signal.SIGTERM,
                intervals,
                minimums,
                filters,
                snapshot,
                snapshot_lock,
                verbose,
                stop_event,
                config_path,
                root,
            )

            self.assertTrue(dump_path.is_file())
            self.assertEqual(
                json.loads(dump_path.read_text(encoding="utf-8")),
                snapshot,
            )

        self.assertEqual(
            [item.value for item in intervals],
            minimums,
        )
        self.assertEqual(filters, {"comando": "python", "usuario": "root"})
        self.assertTrue(verbose.value)
        self.assertTrue(stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
