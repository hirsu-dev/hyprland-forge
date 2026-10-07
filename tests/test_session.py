import os
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
            env = {**os.environ, "HOME": str(root), "XDG_RUNTIME_DIR": str(root), "XDG_CONFIG_HOME": str(root / ".config"), "FORGE_SESSION_FIXTURE": str(root), "PATH": str(binaries) + os.pathsep + os.environ["PATH"]}
            process = subprocess.Popen(["bash", str(ROOT / "configs/bin/forge-session")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                while len(list(root.glob("*.pid"))) != 6 and time.monotonic() < deadline:
                    self.assertIsNone(process.poll())
                    time.sleep(0.05)
                self.assertEqual(len(list(root.glob("*.pid"))), 6)
                self.assertEqual((root / "renderer").read_text(), "software")
                self.assertFalse((root / "leaked-lock").exists())
                duplicate = subprocess.run(["bash", str(ROOT / "configs/bin/forge-session")], env=env, capture_output=True, timeout=3)
                self.assertEqual(duplicate.returncode, 0)
                process.terminate()
                _, error = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, error)
                self.assertIn(b"authentication agent unavailable", error)
                deadline = time.monotonic() + 3
                while len(list(root.glob("*.stopped"))) != 6 and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertEqual(len(list(root.glob("*.stopped"))), 6)
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
