import os
import sys
import tempfile
import threading
import unittest

from src import procfs
from src.analizadores import fds, memoria, resumen, scheduling, senales, sistema
from src.analizadores import threads as thread_analyzer


@unittest.skipUnless(sys.platform.startswith("linux"), "requiere /proc de Linux")
class LinuxAnalyzerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.pid = os.getpid()

    def test_summary_matches_stat_and_status(self):
        expected_stat = procfs.read_stat(self.pid)
        expected_status = procfs.read_status(self.pid)

        data = resumen.analyze([self.pid])[str(self.pid)]

        self.assertEqual(data["pid"], self.pid)
        self.assertEqual(data["ppid"], expected_stat["ppid"])
        self.assertEqual(data["estado"], expected_stat["state"])
        self.assertEqual(
            data["threads"],
            procfs.numeric_value(expected_status["Threads"]),
        )
        self.assertEqual(
            data["rss"],
            procfs.numeric_value(expected_status["VmRSS"]),
        )
        self.assertIn("uid", data)
        self.assertIn("gid", data)
        self.assertIn("usuario", data)
        self.assertTrue(data["comando"])

    def test_memory_matches_status_stat_and_maps(self):
        expected_status = procfs.read_status(self.pid)
        expected_stat = procfs.read_stat(self.pid)

        data = memoria.analyze([self.pid])[str(self.pid)]

        for key in memoria.KEYS:
            self.assertEqual(
                data[key],
                procfs.numeric_value(expected_status.get(key, "0")),
            )
        self.assertEqual(data["minor_faults"], expected_stat["minflt"])
        self.assertEqual(data["major_faults"], expected_stat["majflt"])
        self.assertEqual(
            set(data["segmentos_bytes"]),
            {"text", "data", "heap", "stack", "shared"},
        )

    def test_open_file_descriptor_is_reported(self):
        with tempfile.NamedTemporaryFile() as opened:
            data = fds.analyze([self.pid])[str(self.pid)]
            item = next(
                descriptor
                for descriptor in data["fds"]
                if descriptor["fd"] == opened.fileno()
            )

        self.assertEqual(item["tipo"], "file")
        self.assertIn(os.path.basename(opened.name), item["destino"])
        self.assertEqual(data["cantidad"], len(data["fds"]))

    def test_current_thread_matches_task_files(self):
        tid = threading.get_native_id()
        data = thread_analyzer.analyze([self.pid])[str(self.pid)]["threads"]
        item = next(thread for thread in data if thread["tid"] == tid)
        task = procfs.PROC_ROOT / str(self.pid) / "task" / str(tid)
        expected_stat = procfs.parse_stat(procfs.read_text(task / "stat"))
        expected_status = procfs.parse_status(procfs.read_text(task / "status"))

        self.assertEqual(item["nombre"], procfs.read_text(task / "comm"))
        self.assertEqual(item["estado"], expected_stat["state"])
        self.assertEqual(
            item["voluntary"],
            procfs.numeric_value(
                expected_status.get("voluntary_ctxt_switches", "0")
            ),
        )
        self.assertGreaterEqual(item["cpu"], 0)

    def test_signals_and_scheduling_match_proc(self):
        expected_status = procfs.read_status(self.pid)
        expected_stat = procfs.read_stat(self.pid)
        signal_data = senales.analyze([self.pid])[str(self.pid)]
        scheduling_data = scheduling.analyze([self.pid])[str(self.pid)]

        for key in senales.FIELDS:
            self.assertEqual(
                signal_data[key],
                procfs.decode_signal_mask(expected_status.get(key, "0")),
            )
        self.assertEqual(scheduling_data["nice"], expected_stat["nice"])
        self.assertEqual(
            scheduling_data["priority"],
            expected_stat["priority"],
        )
        self.assertEqual(
            scheduling_data["rt_priority"],
            expected_stat["rt_priority"],
        )
        self.assertEqual(
            scheduling_data["affinity"],
            expected_status["Cpus_allowed_list"],
        )
        self.assertEqual(scheduling_data["sid"], expected_stat["sid"])
        self.assertEqual(scheduling_data["pgid"], expected_stat["pgid"])

    def test_global_system_data_has_requested_fields(self):
        data = sistema.analyze([])

        self.assertEqual(
            set(data["cpu"]),
            {"user", "system", "idle", "iowait"},
        )
        self.assertEqual(len(data["load"]), 3)
        self.assertEqual(
            set(data["memoria"]),
            {"MemTotal", "MemFree", "Buffers", "Cached", "SwapTotal",
             "SwapFree"},
        )
        self.assertGreater(data["procesos"], 0)
        self.assertGreaterEqual(data["threads"], data["procesos"])
        self.assertEqual(data["zombies"], data["estados"].get("Z", 0))
        self.assertGreater(data["boot_time"], 0)
        self.assertGreater(data["uptime"], 0)


if __name__ == "__main__":
    unittest.main()
