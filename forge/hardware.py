import platform
import subprocess
from pathlib import Path

from .manifest import ForgeError


KERNELS = ("linux", "linux-lts", "linux-zen", "linux-hardened")
SERVICES = ("NetworkManager.service", "bluetooth.service", "power-profiles-daemon.service", "fstrim.timer", "nvidia-suspend.service", "nvidia-hibernate.service", "nvidia-resume.service")
CONFLICTS = ("tlp.service", "tuned.service", "auto-cpufreq.service", "systemd-networkd.service", "dhcpcd.service")


def inventory(sys_root=Path("/sys"), runner=subprocess.run):
    devices = []
    for device in sorted((sys_root / "bus/pci/devices").glob("*")):
        try:
            if int((device / "class").read_text().strip(), 16) >> 16 != 3:
                continue
            devices.append({"pci": device.name, "vendor": (device / "vendor").read_text().strip(), "device": (device / "device").read_text().strip()})
        except (OSError, ValueError):
            continue
    secure_boot = False
    for variable in (sys_root / "firmware/efi/efivars").glob("SecureBoot-*"):
        value = variable.read_bytes()
        secure_boot = secure_boot or len(value) >= 5 and value[4] == 1
    installed = runner(["pacman", "-Qq"], capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()
    return {"gpus": devices, "kernels": [k for k in KERNELS if k in installed], "secure_boot": secure_boot}


def hardware_packages(data):
    if not data["kernels"]:
        raise ForgeError("Install a supported Arch kernel: linux, linux-lts, linux-zen or linux-hardened")
    if not any(gpu["vendor"] == "0x10de" for gpu in data["gpus"]):
        raise ForgeError("The RTX 4050 profile requires an NVIDIA GPU visible to Linux")
    if data["secure_boot"]:
        raise ForgeError("Secure Boot is enabled; configure signed NVIDIA DKMS modules before using this profile")
    return [f"{kernel}-headers" for kernel in data["kernels"]]


def verify_services(runner=subprocess.run):
    conflicts = []
    for service in CONFLICTS:
        enabled = runner(["systemctl", "is-enabled", service], capture_output=True, text=True)
        active = runner(["systemctl", "is-active", service], capture_output=True, text=True)
        if enabled.returncode == 0 or active.returncode == 0:
            conflicts.append(service)
    for service in SERVICES:
        result = runner(["systemctl", "is-enabled", service], capture_output=True, text=True)
        if result.stdout.strip() in ("masked", "masked-runtime"):
            conflicts.append(service + " (masked)")
    if conflicts:
        raise ForgeError("Resolve existing service configuration before installing: " + ", ".join(conflicts))


def resolve_plan(plan, apply=False, profile="laptop"):
    if profile not in ("laptop", "virtual-machine"):
        raise ForgeError("Unknown hardware profile")
    plan["profile"] = profile
    if "hardware" not in plan["stages"]:
        return plan
    virtual = profile == "virtual-machine"
    if virtual and apply:
        result = subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or result.stdout.strip() in ("", "none"):
            raise ForgeError("The virtual-machine profile requires a detected virtual machine")
    if platform.system() == "Linux" and Path("/etc/arch-release").is_file():
        data = inventory()
        headers = [] if virtual else hardware_packages(data) if apply else [f"{k}-headers" for k in data["kernels"] or ["linux"]]
        if apply:
            verify_services()
        plan["hardware"] = data
    else:
        headers = [] if virtual else ["linux-headers"]
        plan["hardware"] = {"preview_only": True, "kernels": ["linux"]}
    if virtual:
        excluded = {"amd-ucode", "nvidia-open-dkms", "nvidia-utils", "nvidia-prime", "egl-wayland", "vulkan-radeon"}
        plan["packages"] = [package for package in plan["packages"] if package not in excluded]
        plan["hardware"]["validation_scope"] = "virtual-hardware-only"
    plan["packages"] = list(dict.fromkeys([*plan["packages"], *headers]))
    plan["commands"] = [["sudo", "pacman", "-Syu", "--needed", "--", *plan["packages"]]]
    plan["services"] = ["NetworkManager.service", "fstrim.timer"] if virtual else list(SERVICES)
    plan["reboot_required"] = True
    return plan


def doctor():
    from .diagnostics import collect
    return collect()
