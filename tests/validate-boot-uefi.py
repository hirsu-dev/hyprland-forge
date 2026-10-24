import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from forge.boot import build, configuration, password_hash


ROOT = Path("test-results/boot-uefi").resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PASSWORD = "ephemeral-boot-test-password"


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def serial_config(*args):
    result = configuration(*args)
    return result.replace("terminal_output gfxterm", "serial --unit=0 --speed=115200\nterminal_input console serial\nterminal_output gfxterm serial")


def stub(path, marker):
    source = path.with_suffix(".cfg")
    source.write_text("serial --unit=0 --speed=115200\nterminal_output serial\necho " + marker + "\nhalt\n")
    command(["grub-mkstandalone", "--format=x86_64-efi", "--locales=", "--fonts=", "--output=" + str(path), "boot/grub/grub.cfg=" + str(source)])


def disk(path, serial, efi, destination):
    with path.open("wb") as stream:
        stream.truncate(64 * 1024 * 1024)
    command(["mkfs.fat", "-F", "32", "-i", serial, str(path)])
    parts = destination.strip("/").split("/")
    current = ""
    for part in parts[:-1]:
        current += "/" + part
        command(["mmd", "-i", str(path), "::" + current])
    command(["mcopy", "-i", str(path), str(efi), "::" + destination])


class BootVM:
    def __init__(self, root, label):
        self.root, self.label = root, label
        self.console = socket.socket(socket.AF_UNIX)
        self.monitor = socket.socket(socket.AF_UNIX)
        self.log = bytearray()
        self.pending = bytearray()

    def __enter__(self):
        serial, qmp = self.root / "serial.sock", self.root / "qmp.sock"
        for path in (serial, qmp):
            path.unlink(missing_ok=True)
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", self.root / "vars.fd")
        self.errors = (ROOT / (self.label + "-qemu.log")).open("wb")
        self.process = subprocess.Popen(["qemu-system-x86_64", "-machine", "q35,accel=tcg", "-m", "256", "-display", "none", "-vga", "std", "-net", "none", "-no-reboot", "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd", "-drive", "if=pflash,format=raw,file=" + str(self.root / "vars.fd"), "-drive", "format=raw,file=fat:rw:" + str(self.root / "bootfs"), "-drive", "format=raw,file=" + str(self.root / "forge.img"), "-drive", "format=raw,file=" + str(self.root / "windows.img"), "-serial", "unix:" + str(serial) + ",server=on,wait=off", "-qmp", "unix:" + str(qmp) + ",server=on,wait=off"], stdout=self.errors, stderr=subprocess.STDOUT)
        for _ in range(100):
            if serial.exists() and qmp.exists():
                break
            if self.process.poll() is not None:
                raise AssertionError("QEMU exited before exposing its test interfaces")
            time.sleep(.1)
        self.console.connect(str(serial))
        self.console.settimeout(.2)
        self.monitor.connect(str(qmp))
        self.protocol = self.monitor.makefile("rwb", buffering=0)
        self.protocol.readline()
        self.qmp("qmp_capabilities")
        return self

    def qmp(self, action, arguments=None):
        self.protocol.write((json.dumps({"execute": action, "arguments": arguments or {}}) + "\n").encode())
        while True:
            data = json.loads(self.protocol.readline())
            if "return" in data:
                return data["return"]
            if "error" in data:
                raise AssertionError(data)

    def wait(self, marker, timeout=45):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if marker.encode() in self.pending:
                count = self.pending.index(marker.encode()) + len(marker)
                result = bytes(self.pending[:count])
                del self.pending[:count]
                return result
            try:
                part = self.console.recv(65536)
            except socket.timeout:
                continue
            if not part:
                break
            self.log.extend(part)
            self.pending.extend(part)
        raise AssertionError("Missing test marker: " + marker + "\n" + self.log.decode(errors="replace")[-4000:])

    def screenshot(self, name):
        path = ROOT / (name + ".ppm")
        self.qmp("screendump", {"filename": str(path)})
        with Image.open(path) as image:
            image.save(path.with_suffix(".png"))
        path.unlink()

    def __exit__(self, *args):
        (ROOT / (self.label + "-serial.log")).write_bytes(self.log)
        self.console.close()
        self.protocol.close()
        self.monitor.close()
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=10)
        self.errors.close()


with tempfile.TemporaryDirectory(prefix="forge-uefi-") as temporary:
    root = Path(temporary)
    with patch("forge.boot.configuration", side_effect=serial_config):
        output = build(root / "package", "1234-ABCD", "5678-EF01", password_hash(PASSWORD))
    boot = root / "bootfs/EFI/BOOT"
    boot.mkdir(parents=True)
    shutil.copyfile(output / "EFI/Forge/forge-x64.efi", boot / "BOOTX64.EFI")
    stub(root / "forge.efi", "FORGE_TEST_LINUX_CHAINLOADER_OK")
    stub(root / "windows.efi", "FORGE_TEST_WINDOWS_CHAINLOADER_OK")
    disk(root / "forge.img", "1234ABCD", root / "forge.efi", "/EFI/systemd/systemd-bootx64.efi")
    disk(root / "windows.img", "5678EF01", root / "windows.efi", "/EFI/Microsoft/Boot/bootmgfw.efi")
    with BootVM(root, "windows") as vm:
        vm.wait("Enter username:")
        vm.screenshot("authentication")
        assert b"Windows 11" not in vm.log and b"Forge OS" not in vm.log
        vm.console.sendall(b"forge\rwrong-test-password\r")
        vm.wait("Access denied")
        vm.wait("Enter username:")
        assert b"Windows 11" not in vm.log
        vm.console.sendall(b"\x1b")
        vm.wait("Access denied")
        vm.wait("Enter username:")
        vm.console.sendall(("forge\r" + PASSWORD + "\r").encode())
        vm.wait("Windows 11")
        time.sleep(.3)
        vm.screenshot("selector")
        vm.console.sendall(b"\x1b[B\r")
        vm.wait("FORGE_TEST_WINDOWS_CHAINLOADER_OK")
    with BootVM(root, "forge") as vm:
        vm.wait("Enter username:")
        vm.console.sendall(("forge\r" + PASSWORD + "\r").encode())
        vm.wait("Windows 11")
        vm.console.sendall(b"\r")
        vm.wait("FORGE_TEST_LINUX_CHAINLOADER_OK")
print("QEMU UEFI: wrong password and Escape blocked; correct PBKDF2 password reveals menu; both separate ESP chainload fixtures booted")
