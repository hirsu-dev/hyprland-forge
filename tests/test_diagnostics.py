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
            "sink": 'media.class = "Audio/Sink"\nnode.name = "alsa_output.test"',
            "systemd-detect-virt": "none",
            "dkms": "nvidia/590, test-kernel, x86_64: installed",
            "monitors": json.dumps([{"name": "HDMI-A-1", "width": 1920, "height": 1080, "refreshRate": 119.99}, {"name": "eDP-1", "disabled": False}]),
            "configerrors": "[]",
            "quickshell": '{"screens":2}',
        }

    def runner(self, command, **kwargs):
        if command[:2] == ["systemctl", "is-active"]:
            return subprocess.CompletedProcess(command, 0, "active", "")
        if command[0] == "systemd-detect-virt":
            return subprocess.CompletedProcess(command, int(self.responses[command[0]] == "none"), self.responses[command[0]], "")
        if command[:2] == ["wpctl", "inspect"]:
            return subprocess.CompletedProcess(command, 0, self.responses["sink"], "")
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

    def test_bad_monitor_data_is_contained(self):
        for response in ("[1]", '[{"name":"HDMI-A-1","refreshRate":"bad"}]'):
            self.responses["monitors"] = response
            self.assertEqual(self.collect()["checks"]["hyprland_config"]["status"], "failed")

    def test_unreadable_modeset_does_not_hide_remaining_checks(self):
        original = Path.read_text
        def read(path, *args, **kwargs):
            if path.name == "modeset":
                raise PermissionError("read denied")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            report = self.collect()
        self.assertEqual(report["checks"]["nvidia_modeset"]["status"], "warning")
        self.assertEqual(report["checks"]["audio"]["status"], "passed")

    def test_virtualbox_is_qualified_separately(self):
        self.responses["systemd-detect-virt"] = "oracle"
        self.responses["monitors"] = '[{"name":"Virtual-1","refreshRate":60}]'
        report = self.collect()
        self.assertTrue(report["runtime_ready"])
        self.assertFalse(report["physical_hardware_qualified"])
        self.assertEqual(report["validation_scope"], "virtual-hardware-only")
        self.assertIsNone(report["dkms"])
        self.assertEqual(report["checks"]["nvidia_dkms"]["status"], "not-applicable")
        self.assertIn("vboxservice.service", report["services"])
        self.assertNotIn("nvidia-suspend.service", report["services"])

    def test_other_vm_does_not_require_virtualbox(self):
        self.responses["systemd-detect-virt"] = "kvm"
        report = self.collect()
        self.assertTrue(report["runtime_ready"])
        self.assertNotIn("vboxservice.service", report["services"])

    def test_empty_hyprland_errors_are_not_failures(self):
        self.responses["configerrors"] = '["", "  "]'
        self.assertTrue(self.collect()["runtime_ready"])

    def test_malformed_errors_fail_closed(self):
        for response in ('{}', 'null', '""', '[null]'):
            self.responses["configerrors"] = response
            self.assertFalse(self.collect()["runtime_ready"])

    def test_no_monitors_is_not_ready(self):
        self.responses["monitors"] = '[]'
        self.assertEqual(self.collect()["checks"]["active_displays"]["status"], "failed")

    def test_invalid_shell_status_is_not_ready(self):
        for response in ('ok', '{}', 'null', '{"screens":true}', '{"screens":0}'):
            self.responses["quickshell"] = response
            self.assertEqual(self.collect()["checks"]["shell"]["status"], "failed")

    def test_audio_server_without_output_is_not_ready(self):
        self.responses["sink"] = 'media.class = "Audio/Source"'
        self.assertEqual(self.collect()["checks"]["audio"]["status"], "failed")

    def test_dummy_output_warns(self):
        self.responses["sink"] = 'media.class = "Audio/Sink"\nnode.name = "auto_null"'
        self.assertEqual(self.collect()["checks"]["audio"]["status"], "warning")

    def test_dkms_requires_exact_kernel_and_installed_status(self):
        for value in ('nvidia/590, test-kernel-other, x86_64: installed', 'nvidia/590, test-kernel, x86_64: not installed'):
            self.responses["dkms"] = value
            self.assertEqual(self.collect()["checks"]["nvidia_dkms"]["status"], "failed")

    def test_enabled_but_stopped_services_fail(self):
        original = self.runner
        def stopped(command, **kwargs):
            if command[:2] == ["systemctl", "is-active"]:
                return subprocess.CompletedProcess(command, 3, "inactive", "")
            return original(command, **kwargs)
        with patch.object(self, "runner", stopped):
            report = self.collect()
        self.assertEqual(report["checks"]["system_services"]["status"], "passed")
        self.assertEqual(report["checks"]["running_services"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
