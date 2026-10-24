import json
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from forge.diagnostics import session_health
from forge.session import Component


class SupervisorTests(unittest.TestCase):
    def test_crashes_back_off_and_stable_running_resets_failures(self):
        component = Component("shell", ["quickshell", "-c", "forge"])
        process = Mock(pid=1234)
        process.poll.return_value = None
        factory = Mock(return_value=process)
        logger = logging.getLogger("test.session")
        with patch("forge.session.terminate_group"), patch("forge.session.signal.SIGKILL", 9, create=True):
            self.assertTrue(component.update(100, logger, factory))
            self.assertFalse(component.update(101, logger, factory))
            process.poll.return_value = 1
            component.update(102, logger, factory)
            self.assertEqual(component.retry_at, 104)
            self.assertFalse(component.update(103, logger, factory))
            component.update(104, logger, factory)
            component.update(105, logger, factory)
            self.assertEqual(component.retry_at, 109)
            component.update(109, logger, factory)
            component.update(170, logger, factory)
            self.assertEqual(component.retry_at, 172)
        self.assertEqual(component.restarts, 2)
        self.assertTrue(factory.call_args.kwargs["close_fds"])
        self.assertTrue(factory.call_args.kwargs["start_new_session"])
        self.assertEqual(factory.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_missing_binary_never_spins_and_retry_is_bounded(self):
        component = Component("idle", ["missing"])
        factory = Mock(side_effect=FileNotFoundError("not installed"))
        logger = Mock()
        now = 0
        for _ in range(12):
            component.update(now, logger, factory)
            delay = component.retry_at - now
            self.assertTrue(2 <= delay <= 60)
            calls = factory.call_count
            self.assertFalse(component.update(now + 0.5, logger, factory))
            self.assertEqual(factory.call_count, calls)
            now = component.retry_at
        self.assertEqual(component.status()["last_exit"], "unavailable")

    def test_stale_or_recovering_components_are_not_reported_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            path = runtime / "hyprland-forge-session.json"
            value = {"running": True, "updated": 100, "components": [{"name": name, "running": True} for name in ("idle", "clipboard-text", "clipboard-image", "wallpaper", "shell")]}
            path.write_text(json.dumps(value))
            self.assertEqual(session_health(runtime, 105)["status"], "passed")
            self.assertEqual(session_health(runtime, 121)["status"], "warning")
            value["components"][-1]["running"] = False
            path.write_text(json.dumps(value))
            self.assertEqual(session_health(runtime, 105)["recovering"], ["shell"])
            for malformed in ([], {}, {"running": True, "updated": "bad"}, {**value, "components": [1]}):
                path.write_text(json.dumps(malformed))
                self.assertEqual(session_health(runtime, 105)["status"], "warning")
