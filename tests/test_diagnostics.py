import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.diagnostics import collect, probe
from forge.manifest import ForgeError


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sys = Path(self.temporary.name)
        device = self.sys / "bus/pci/devices/gpu0"
        device.mkdir(parents=True)
        for name, value in (("class", "0x030000"), ("vendor", "0x10de"), ("device", "0x28a1")):
            (device / name).write_text(value)
        parameter = self.sys / "module/nvidia_drm/parameters/modeset"
        parameter.parent.mkdir(parents=True)
        parameter.write_text("Y")
        self.responses = {
            "pacman": "linux\nnvidia-open-dkms\n",
            "systemctl": "enabled",
            "wpctl": "Audio devices",
            "dkms": "nvidia/590, test-kernel, x86_64: installed",
            "monitors": json.dumps([{"name": "HDMI-A-1", "width": 1920, "height": 1080, "refreshRate": 119.99}, {"name": "eDP-1", "disabled": False}]),
            "configerrors": "[]",
            "quickshell": '{"screens":2}',
        }

    def runner(self, command, **kwargs):
        key = command[-1] if command[0] == "hyprctl" else command[0]
        return subprocess.CompletedProcess(command, 0, self.responses[key], "")

    def collect(self, session=True):
        with patch("forge.diagnostics.platform.system", return_value="Linux"), patch("forge.diagnostics.platform.release", return_value="test-kernel"), patch.dict("os.environ", {"HYPRLAND_INSTANCE_SIGNATURE": "test" if session else ""}):
            return collect(self.sys, self.runner)

    def test_complete_runtime_checks_pass(self):
        report = self.collect()
        self.assertTrue(report["runtime_ready"])
        self.assertEqual(report["checks"]["external_1080p120"]["status"], "passed")

    def test_tty_does_not_claim_display_validation(self):
        report = self.collect(False)
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(report["checks"]["hyprland_session"]["status"], "pending")

    def test_fallback_refresh_is_a_warning(self):
        monitors = json.loads(self.responses["monitors"])
        monitors[0]["refreshRate"] = 60
        self.responses["monitors"] = json.dumps(monitors)
        report = self.collect()
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(report["checks"]["external_1080p120"]["status"], "warning")

    def test_config_errors_fail_validation(self):
        self.responses["configerrors"] = '["Invalid key"]'
        self.assertEqual(self.collect()["checks"]["hyprland_config"]["status"], "failed")

    def test_missing_current_kernel_dkms_is_failed(self):
        self.responses["dkms"] = "nvidia/590, different-kernel, x86_64: installed"
        self.assertEqual(self.collect()["checks"]["nvidia_dkms"]["status"], "failed")

    def test_malformed_compositor_response_is_failed(self):
        self.responses["monitors"] = "not json"
        self.assertEqual(self.collect()["checks"]["hyprland_config"]["status"], "failed")

    def test_probe_contains_missing_commands_and_timeouts(self):
        for failure in (FileNotFoundError("missing"), subprocess.TimeoutExpired(["test"], 10)):
            with self.subTest(failure=failure):
                def runner(*args, **kwargs):
                    raise failure
                self.assertFalse(probe(["test"], runner)["ok"])

    def test_windows_diagnostics_refused(self):
        with patch("forge.diagnostics.platform.system", return_value="Windows"), self.assertRaises(ForgeError):
            collect(self.sys, self.runner)


if __name__ == "__main__":
    unittest.main()
