import unittest

from src.procfs import (
    classify_fd,
    cpu_percentages,
    decode_signal_mask,
    group_maps,
    parse_stat,
    parse_status,
)


class ProcfsTests(unittest.TestCase):
    def test_status(self):
        parsed = parse_status("Name:\tpython\nUid:\t1000 1000 1000 1000\n")
        self.assertEqual(parsed["Name"], "python")
        self.assertTrue(parsed["Uid"].startswith("1000"))

    def test_stat_preserves_comm_spaces_and_fields(self):
        values = ["S"] + [str(number) for number in range(4, 53)]
        parsed = parse_stat("42 (nombre con espacios) " + " ".join(values))
        self.assertEqual(parsed["pid"], 42)
        self.assertEqual(parsed["comm"], "nombre con espacios")
        self.assertEqual(parsed["state"], "S")
        self.assertEqual(parsed["ppid"], 4)
        self.assertEqual(parsed["utime"], 14)
        self.assertEqual(parsed["policy"], 41)

    def test_signal_mask(self):
        names = decode_signal_mask("0000000000000002")
        self.assertEqual(names, ["SIGINT"])
        self.assertEqual(decode_signal_mask("not-hex"), [])

    def test_fd_classification(self):
        self.assertEqual(classify_fd("socket:[123]"), "socket")
        self.assertEqual(classify_fd("pipe:[123]"), "pipe")
        self.assertEqual(classify_fd("/dev/pts/0"), "tty")
        self.assertEqual(classify_fd("/tmp/file"), "file")

    def test_cpu_delta(self):
        result = cpu_percentages((100, 0, 50, 850, 0),
                                 (150, 0, 100, 900, 0))
        self.assertAlmostEqual(result["user"], 100 / 3, places=4)
        self.assertAlmostEqual(result["system"], 100 / 3, places=4)
        self.assertAlmostEqual(result["idle"], 100 / 3, places=4)

    def test_group_maps(self):
        text = (
            "00400000-00401000 r-xp 0 00:00 0 /bin/a\n"
            "00600000-00602000 rw-p 0 00:00 0 [heap]\n"
            "00700000-00701000 rw-p 0 00:00 0 [stack]\n"
            "00800000-00801000 rw-s 0 00:00 0 /tmp/x\n"
        )
        groups = group_maps(text)
        self.assertEqual(groups["text"], 4096)
        self.assertEqual(groups["heap"], 8192)
        self.assertEqual(groups["stack"], 4096)
        self.assertEqual(groups["shared"], 4096)


if __name__ == "__main__":
    unittest.main()
