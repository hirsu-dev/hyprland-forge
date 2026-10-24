import subprocess
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from forge.control import dispatch
from forge.maintenance import report


Space = namedtuple("Space", "total used free")


class MaintenanceTests(unittest.TestCase):
    def test_readable_report_keeps_warnings_and_includes_storage(self):
        data = {"checks": {"audio": {"status": "passed", "reason": "Output routing checked"}, "session_components": {"status": "warning", "recovering": ["shell"]}, "hyprland_config": {"status": "failed", "errors": ["Bad setting"]}}}
        result = report(Path("/home/test"), collector=lambda **_: data, usage=lambda _: Space(20 * 1024 ** 3, 19 * 1024 ** 3, 1024 ** 3))
        self.assertEqual(result["health"][0]["name"], "Audio output")
        self.assertEqual(result["health"][1]["detail"], "Restarting: shell")
        self.assertEqual(result["health"][2]["status"], "failed")
        self.assertEqual(result["health"][-1]["status"], "warning")
        self.assertIn("1.0 GiB free", result["health"][-1]["detail"])

    def test_unreadable_storage_does_not_hide_other_checks(self):
        data = {"checks": {"audio": {"status": "failed"}}}
        def denied(_):
            raise PermissionError()
        value = report(Path("/home/test"), collector=lambda **_: data, usage=denied)
        self.assertEqual(len(value["health"]), 3)
        self.assertEqual(value["health"][0]["status"], "failed")

    def test_health_and_logs_are_read_only_and_journal_failure_is_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / ".local/state/hyprland-forge/session.log"
            path.parent.mkdir(parents=True)
            path.write_text("shell restarted\n")
            with patch("forge.control.preflight", side_effect=AssertionError("must stay read-only")), patch("forge.maintenance.collect", return_value={"checks": {}}):
                self.assertTrue(dispatch({"action": "health"}, home)["health"])
                result = dispatch({"action": "logs"}, home, runner=lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", ""))
            self.assertIn("shell restarted", result["logs"])
            self.assertIn("User journal unavailable", result["logs"])
