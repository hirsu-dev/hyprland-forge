import json
import select
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image


RESULTS = Path("test-results/native-startup").resolve()
PASSWORD = "fixture-password-123"


def run(command):
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)


def target_disk(root, label, guid, path):
    image = root / (label + ".img")
    with image.open("wb") as stream:
        stream.truncate(96 * 1024 * 1024)
    run(["sgdisk", "--new=1:2048:0", "--typecode=1:ef00", "--partition-guid=1:" + guid, str(image)])
    run(["mkfs.fat", "-F", "32", "--offset=2048", str(image)])
    source = root / (label + ".cfg")
    source.write_text("serial --unit=0 --speed=115200\nterminal_output serial\necho FORGE_TEST_" + label.upper() + "_OK\nhalt\n")
    efi = root / (label + ".efi")
    run(["grub-mkstandalone", "--format=x86_64-efi", "--locales=", "--fonts=", "--output=" + str(efi), "boot/grub/grub.cfg=" + str(source)])
    directory = ""
    for part in path.strip("/").split("/")[:-1]:
        directory += "/" + part
        run(["mmd", "-i", str(image) + "@@1048576", "::" + directory])
    run(["mcopy", "-i", str(image) + "@@1048576", str(efi), "::" + path])


class Machine:
    def __init__(self, root, label):
        self.root, self.label = root, label
        self.pending, self.log = bytearray(), bytearray()

    def __enter__(self):
        for name in ("trace", "serial", "qmp"):
            (self.root / (name + ".sock")).unlink(missing_ok=True)
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", self.root / "vars.fd")
        self.errors = (RESULTS / (self.label + "-qemu.log")).open("wb")
        command = ["qemu-system-x86_64", "-machine", "q35,accel=tcg", "-m", "256", "-display", "none", "-vga", "std", "-net", "none", "-no-reboot", "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd", "-drive", "if=pflash,format=raw,file=" + str(self.root / "vars.fd"), "-drive", "format=raw,file=fat:rw:" + str(self.root / "bootfs"), "-drive", "format=raw,file=" + str(self.root / "forge.img"), "-drive", "format=raw,file=" + str(self.root / "windows.img")]
        for option, name in (("-debugcon", "trace"), ("-serial", "serial"), ("-qmp", "qmp")):
            command += [option, "unix:" + str(self.root / (name + ".sock")) + ",server=on,wait=off"]
        self.process = subprocess.Popen(command, stdout=self.errors, stderr=subprocess.STDOUT)
        self.sockets = []
        for name in ("trace", "serial", "qmp"):
            path = self.root / (name + ".sock")
            end = time.monotonic() + 10
            while not path.exists() and time.monotonic() < end:
                time.sleep(.05)
            connection = socket.socket(socket.AF_UNIX)
            connection.settimeout(10)
            connection.connect(str(path))
            self.sockets.append(connection)
        self.protocol = self.sockets[2].makefile("rwb", buffering=0)
        self.protocol.readline()
        self.qmp("qmp_capabilities")
        return self

    def qmp(self, action, arguments=None):
        self.protocol.write((json.dumps({"execute": action, "arguments": arguments or {}}) + "\n").encode())
        while True:
            result = json.loads(self.protocol.readline())
            if "return" in result:
                return result["return"]
            if "error" in result:
                raise AssertionError(result)

    def key(self, code):
        self.qmp("send-key", {"keys": [{"type": "qcode", "data": code}], "hold-time": 15})
        time.sleep(.035)

    def password(self, value):
        for character in value:
            self.key("minus" if character == "-" else character)
        self.key("ret")

    def wait(self, marker, timeout=90):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if marker.encode() in self.pending:
                position = self.pending.index(marker.encode()) + len(marker)
                result = bytes(self.pending[:position])
                del self.pending[:position]
                print(self.label + ": " + marker, flush=True)
                return result
            ready, _, _ = select.select(self.sockets[:2], [], [], .2)
            for connection in ready:
                data = connection.recv(65536)
                self.log.extend(data)
                self.pending.extend(data)
        self.screenshot(self.label + "-failure")
        raise AssertionError("Missing " + marker + "\n" + self.log.decode(errors="replace")[-3000:])

    def screenshot(self, label):
        path = RESULTS / (label + ".ppm")
        self.qmp("screendump", {"filename": str(path)})
        with Image.open(path) as image:
            image.save(path.with_suffix(".png"))
        path.unlink()

    def __exit__(self, *args):
        (RESULTS / (self.label + "-events.log")).write_bytes(self.log)
        self.protocol.close()
        for connection in self.sockets:
            connection.close()
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=10)
        self.errors.close()


with tempfile.TemporaryDirectory(prefix="forge-native-qemu-") as directory:
    root = Path(directory)
    boot = root / "bootfs/EFI/BOOT"
    boot.mkdir(parents=True)
    shutil.copyfile(RESULTS / "private-fixture/EFI/Forge/forge-startup-x64.efi", boot / "BOOTX64.EFI")
    target_disk(root, "forge", "11111111-2222-4333-8444-555555555555", "/EFI/systemd/systemd-bootx64.efi")
    target_disk(root, "windows", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "/EFI/Microsoft/Boot/bootmgfw.efi")
    with Machine(root, "windows") as vm:
        vm.wait("FORGE:TRANSITION")
        vm.screenshot("firmware-intro-a")
        time.sleep(.35)
        vm.screenshot("firmware-intro-b")
        assert (RESULTS / "firmware-intro-a.png").read_bytes() != (RESULTS / "firmware-intro-b.png").read_bytes()
        vm.wait("FORGE:LOCKED")
        vm.key("down"); vm.key("ret")
        assert b"FORGE:SELECTOR" not in vm.log
        vm.password("wrong-password-123")
        vm.wait("FORGE:DENIED")
        vm.wait("FORGE:LOCKED")
        vm.key("x"); vm.key("esc")
        vm.screenshot("firmware-password")
        vm.password(PASSWORD)
        vm.wait("FORGE:SELECTOR")
        vm.screenshot("firmware-selector")
        vm.key("down"); vm.key("ret")
        vm.wait("FORGE_TEST_WINDOWS_OK")
    with Machine(root, "forge") as vm:
        vm.wait("FORGE:LOCKED")
        vm.password(PASSWORD)
        vm.wait("FORGE:SELECTOR")
        vm.key("ret")
        vm.wait("FORGE_TEST_FORGE_OK")
    run(["mdel", "-i", str(root / "windows.img") + "@@1048576", "::/EFI/Microsoft/Boot/bootmgfw.efi"])
    with Machine(root, "missing") as vm:
        vm.wait("FORGE:LOCKED")
        vm.password(PASSWORD)
        vm.wait("FORGE:SELECTOR")
        vm.key("down"); vm.key("ret")
        vm.wait("FORGE:MISSING")
        vm.key("ret"); vm.wait("FORGE:SELECTOR")
        vm.key("esc"); vm.wait("FORGE:LOCKED")
        assert b"FORGE_TEST_WINDOWS_OK" not in vm.log
print("Native UEFI: actual animated frames, password-only rejection/unlock, both GPT-identified loader fixtures, missing-loader recovery and relock passed")
