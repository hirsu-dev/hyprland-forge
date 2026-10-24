import os
import json
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(sys.platform == "linux", "Linux session process control required")
class SessionTests(unittest.TestCase):
    def running(self, pid):
        try:
            return "\nState:\tZ" not in Path(f"/proc/{pid}/status").read_text()
        except FileNotFoundError:
            return False

    def test_optional_startup_failure_lock_isolation_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / ".local/bin"
            binaries.mkdir(parents=True)
            config = root / ".config/quickshell/forge/shell.qml"
            config.parent.mkdir(parents=True)
            config.touch()
            (root / "active").touch()
            for name in ("systemctl", "dbus-update-activation-environment", "systemd-detect-virt", "hyprctl", "hypridle", "wl-paste", "mako", "forge-wallpaper", "quickshell"):
                target = binaries / name
                shutil.copyfile(ROOT / "tests/session-fixture", target)
                target.chmod(0o755)
            env = {**os.environ, "HOME": str(root), "PYTHONPATH": str(ROOT), "XDG_RUNTIME_DIR": str(root), "XDG_CONFIG_HOME": str(root / ".config"), "FORGE_SESSION_FIXTURE": str(root), "PATH": str(binaries) + os.pathsep + os.environ["PATH"]}
            process = subprocess.Popen(["bash", str(ROOT / "configs/bin/forge-session")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                while len(list(root.glob("*.pid"))) != 5 and time.monotonic() < deadline:
                    self.assertIsNone(process.poll())
                    time.sleep(0.05)
                self.assertEqual(len(list(root.glob("*.pid"))), 5)
                self.assertEqual((root / "renderer").read_text(), "software")
                self.assertFalse((root / "leaked-lock").exists())
                duplicate = subprocess.run(["bash", str(ROOT / "configs/bin/forge-session")], env=env, capture_output=True, timeout=3)
                self.assertEqual(duplicate.returncode, 0)
                previous = int((root / "quickshell.pid").read_text())
                child = int((root / "child-process").read_text())
                os.kill(previous, signal.SIGKILL)
                deadline = time.monotonic() + 10
                while int((root / "quickshell.pid").read_text()) == previous and time.monotonic() < deadline:
                    self.assertIsNone(process.poll())
                    time.sleep(0.05)
                self.assertNotEqual(int((root / "quickshell.pid").read_text()), previous)
                self.assertFalse(self.running(child))
                status = json.loads((root / "hyprland-forge-session.json").read_text())
                shell = next(item for item in status["components"] if item["name"] == "shell")
                self.assertEqual(shell["restarts"], 1)
                self.assertTrue(shell["running"])
                child = int((root / "child-process").read_text())
                process.terminate()
                _, error = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, error)
                self.assertIn(b"authentication agent unavailable", error)
                deadline = time.monotonic() + 3
                while len(list(root.glob("*.stopped"))) != 5 and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertEqual(len(list(root.glob("*.stopped"))), 5)
                self.assertFalse(self.running(child))
                self.assertFalse(json.loads((root / "hyprland-forge-session.json").read_text())["running"])
                probe = subprocess.run(["flock", "-n", str(root / "hyprland-forge-session.lock"), "true"], capture_output=True, timeout=3)
                self.assertEqual(probe.returncode, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
