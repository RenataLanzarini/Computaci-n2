import curses
import unittest

from src.display import _format_detail, _format_header, _key


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


class _Control:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class DisplayKeyTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"pid": 10}, {"pid": 20}, {"pid": 30}]
        self.intervals = [_Value(value) for value in (2, 3, 5, 2, 10, 10, 2)]
        self.minimums = [0.5, 1, 2, 0.5, 5, 5, 1]
        self.control = _Control()

    def press(self, key, *, view=0, selected=0, pinned=None,
              sort_mode=0, help_visible=False):
        return _key(
            key,
            view,
            selected,
            self.rows,
            pinned,
            sort_mode,
            help_visible,
            self.intervals,
            self.minimums,
            self.control,
        )

    def test_numeric_and_letter_shortcuts_select_views(self):
        for expected, key in enumerate("1234567"):
            self.assertEqual(self.press(ord(key))[0], expected)
        for expected, key in enumerate("rmftspg"):
            self.assertEqual(self.press(ord(key))[0], expected)

    def test_navigation_stays_inside_process_list(self):
        self.assertEqual(self.press(curses.KEY_UP, selected=0)[1], 0)
        self.assertEqual(self.press(curses.KEY_DOWN, selected=0)[1], 1)
        self.assertEqual(self.press(curses.KEY_DOWN, selected=2)[1], 2)

    def test_enter_pins_and_unpins_pid_not_position(self):
        pinned = self.press(10, selected=1)[2]
        self.assertEqual(pinned, 20)
        self.assertIsNone(self.press(10, selected=1, pinned=pinned)[2])

    def test_sort_help_and_quit(self):
        self.assertEqual(self.press(ord("c"), sort_mode=2)[3], 0)
        self.assertTrue(self.press(ord("h"))[4])
        self.press(ord("q"))
        self.assertEqual(self.control.messages, [{"action": "quit"}])

    def test_interval_adjustment_respects_active_view_minimum(self):
        self.press(ord("+"), view=0)
        self.assertEqual(self.intervals[0].value, 2.5)
        self.intervals[0].value = 0.5
        self.press(ord("-"), view=0)
        self.assertEqual(self.intervals[0].value, 0.5)

    def test_verbose_mode_increases_visible_file_descriptors(self):
        value = {
            "fds": [
                {"fd": number, "tipo": "file", "destino": f"/tmp/{number}"}
                for number in range(40)
            ]
        }

        self.assertEqual(len(_format_detail(value, False)), 10)
        self.assertEqual(len(_format_detail(value, True)), 30)

    def test_thread_detail_shows_context_switches(self):
        value = {
            "threads": [{
                "tid": 123,
                "estado": "S",
                "cpu": 2.5,
                "voluntary": 17,
                "involuntary": 4,
                "nombre": "worker",
            }]
        }

        self.assertEqual(
            _format_detail(value, False),
            ["TID 123 S CPU=2.5% CTX=17/4 worker"],
        )

    def test_header_shows_free_and_pinned_process(self):
        self.assertIn("pin=libre", _format_header(0, 2.0, 0, None))
        self.assertIn("pin=20", _format_header(0, 2.0, 0, 20))


if __name__ == "__main__":
    unittest.main()
