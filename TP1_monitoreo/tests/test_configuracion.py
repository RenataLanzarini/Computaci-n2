import unittest

from src.main import apply_config


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


if __name__ == "__main__":
    unittest.main()
