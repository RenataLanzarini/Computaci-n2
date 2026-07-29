import queue
import threading
import time
import unittest

from src.agregador import aggregator_loop


class AggregatorTests(unittest.TestCase):
    def test_replaces_section_and_derives_top(self):
        messages = queue.Queue()
        snapshot = {
            "resumen": {
                "datos": {
                    "1": {"pid": 1, "cpu": 5.0, "rss": 10,
                          "comando": "uno"},
                    "2": {"pid": 2, "cpu": 9.0, "rss": 7,
                          "comando": "dos"},
                }
            }
        }
        lock = threading.Lock()
        stop = threading.Event()
        worker = threading.Thread(
            target=aggregator_loop,
            args=(messages, snapshot, lock, stop),
        )
        worker.start()
        messages.put(("sistema", {"procesos": 2}, 123.0))
        deadline = time.monotonic() + 1
        while "sistema" not in snapshot and time.monotonic() < deadline:
            time.sleep(0.01)
        stop.set()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(snapshot["sistema"]["ts"], 123.0)
        self.assertEqual(snapshot["sistema"]["datos"]["top_cpu"][0]["pid"], 2)
        self.assertEqual(
            snapshot["sistema"]["datos"]["top_memoria"][0]["pid"], 1
        )


if __name__ == "__main__":
    unittest.main()
