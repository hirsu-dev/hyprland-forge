import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.hardware import hardware_packages, inventory, verify_services, resolve_plan, virtualization, VM_SERVICES
from forge.manifest import load_manifest, make_plan
from forge.manifest import ForgeError
from forge.runtime import execute


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.data = {"gpus": [{"vendor": "0x10de"}, {"vendor": "0x1002"}], "kernels": ["linux", "linux-lts"], "secure_boot": False}

    def test_headers_for_every_installed_kernel(self):
        self.assertEqual(hardware_packages(self.data), ["linux-headers", "linux-lts-headers"])

    def test_vm_plan_excludes_physical_gpu_drivers(self):
        plan = make_plan(load_manifest(Path(__file__).resolve().parent.parent), None)
        with patch("forge.hardware.platform.system", return_value="Windows"):
            result = resolve_plan(plan, profile="virtual-machine")
        self.assertFalse(any(package.startswith("nvidia") for package in result["packages"]))
        self.assertNotIn("linux-headers", result["packages"])
        self.assertIn("mesa", result["packages"])
        self.assertIn("vulkan-swrast", result["packages"])
        self.assertEqual(next(item["source"] for item in result["files"] if item["target"] == ".config/mpv/mpv.conf"), "configs/mpv/virtual-machine.conf")
        self.assertEqual(result["services"], ["NetworkManager.service", "fstrim.timer"])
        self.assertEqual(result["hardware"]["validation_scope"], "virtual-hardware-only")

    def test_vm_profile_refuses_physical_machine(self):
        with patch("forge.hardware.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "none")):
            with self.assertRaisesRegex(ForgeError, "detected virtual machine"):
                resolve_plan({"stages": ["hardware"]}, apply=True, profile="virtual-machine")

    def test_laptop_remains_default_profile(self):
        plan = make_plan(load_manifest(Path(__file__).resolve().parent.parent), None)
        with patch("forge.hardware.platform.system", return_value="Windows"):
            result = resolve_plan(plan)
        self.assertEqual(result["profile"], "laptop")
        self.assertIn("nvidia-open-dkms", result["packages"])
        self.assertEqual(next(item["source"] for item in result["files"] if item["target"] == ".config/mpv/mpv.conf"), "configs/mpv/mpv.conf")

    def test_virtualbox_profile_installs_guest_integration(self):
        plan = make_plan(load_manifest(Path(__file__).resolve().parent.parent), None)
        with patch("forge.hardware.platform.system", return_value="Linux"), patch("forge.hardware.virtualization", return_value="oracle"), patch("forge.hardware.inventory", return_value=self.data), patch("forge.hardware.verify_services"):
            result = resolve_plan(plan, apply=True, profile="virtual-machine")
        self.assertIn("virtualbox-guest-utils", result["packages"])
        self.assertIn("vboxservice.service", result["services"])
        self.assertEqual(result["hardware"]["hypervisor"], "oracle")

    def test_other_vm_does_not_install_virtualbox_tools(self):
        plan = make_plan(load_manifest(Path(__file__).resolve().parent.parent), None)
        with patch("forge.hardware.platform.system", return_value="Linux"), patch("forge.hardware.virtualization", return_value="kvm"), patch("forge.hardware.inventory", return_value=self.data), patch("forge.hardware.verify_services"):
            result = resolve_plan(plan, apply=True, profile="virtual-machine")
        self.assertNotIn("virtualbox-guest-utils", result["packages"])
        self.assertEqual(result["services"], list(VM_SERVICES))

    def test_vm_service_validation_ignores_unused_masked_gpu_service(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "masked" if command[-1] == "nvidia-suspend.service" else "disabled")
        verify_services(runner, services=VM_SERVICES)

    def test_virtualization_detection_distinguishes_unknown(self):
        self.assertEqual(virtualization(lambda *a, **k: subprocess.CompletedProcess(a, 1, "none")), "")
        self.assertEqual(virtualization(lambda *a, **k: subprocess.CompletedProcess(a, 0, "oracle")), "oracle")
        self.assertIsNone(virtualization(lambda *a, **k: subprocess.CompletedProcess(a, 1, "")))
        with patch("forge.hardware.subprocess.run", side_effect=FileNotFoundError()):
            self.assertIsNone(virtualization(__import__("subprocess").run))

    def test_gpu_required(self):
        self.data["gpus"] = [{"vendor": "0x1002"}]
        with self.assertRaisesRegex(ForgeError, "NVIDIA"):
            hardware_packages(self.data)

    def test_unsigned_secure_boot_is_refused(self):
        self.data["secure_boot"] = True
        with self.assertRaisesRegex(ForgeError, "Secure Boot"):
            hardware_packages(self.data)

    def test_custom_kernel_is_refused(self):
        self.data["kernels"] = []
        with self.assertRaisesRegex(ForgeError, "kernel"):
            hardware_packages(self.data)

    def test_pci_inventory_ignores_non_graphics_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, cls in enumerate(("0x030000", "0x030200", "0x040300")):
                device = root / "bus/pci/devices" / str(index)
                device.mkdir(parents=True)
                for name, value in (("class", cls), ("vendor", "0x10de"), ("device", "0x28a1")):
                    (device / name).write_text(value)
            variable = root / "firmware/efi/efivars/SecureBoot-test"
            variable.parent.mkdir(parents=True)
            variable.write_bytes(b"\x07\x00\x00\x00\x01")
            data = inventory(root, lambda *a, **k: subprocess.CompletedProcess(a, 0, "linux-lts\ngit\n"))
            self.assertEqual(len(data["gpus"]), 2)
            self.assertEqual(data["kernels"], ["linux-lts"])
            self.assertTrue(data["secure_boot"])

    def test_existing_power_manager_conflicts(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0 if command[-1] == "tlp.service" else 1, "enabled" if command[-1] == "tlp.service" else "disabled")
        with self.assertRaisesRegex(ForgeError, "tlp.service"):
            verify_services(runner)

    def test_masked_service_is_preserved(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "masked" if command[-1] == "bluetooth.service" else "disabled")
        with self.assertRaisesRegex(ForgeError, "masked"):
            verify_services(runner)

    def test_failed_service_enable_reverts_new_enables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                if command[:2] == ["systemctl", "is-enabled"]:
                    return subprocess.CompletedProcess(command, 1, "disabled\n")
                if command == ["sudo", "systemctl", "enable", "second.service"]:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0, "")

            plan = {"commands": [], "files": [], "services": ["first.service", "second.service"]}
            with self.assertRaises(subprocess.CalledProcessError):
                execute(plan, root, root, root / "state", runner)
            self.assertIn(["sudo", "systemctl", "disable", "first.service"], calls)
            self.assertFalse(any("--now" in command for command in calls))


if __name__ == "__main__":
    unittest.main()
