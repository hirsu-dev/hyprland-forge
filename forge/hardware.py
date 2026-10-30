import platform
import subprocess
from pathlib import Path

from .manifest import ForgeError


KERNELS = ("linux", "linux-lts", "linux-zen", "linux-hardened")
SERVICES = ("NetworkManager.service", "bluetooth.service", "power-profiles-daemon.service", "fstrim.timer", "nvidia-suspend.service", "nvidia-hibernate.service", "nvidia-resume.service")
CONFLICTS = ("tlp.service", "tuned.service", "auto-cpufreq.service", "systemd-networkd.service", "dhcpcd.service")
VM_SERVICES = ("NetworkManager.service", "fstrim.timer")


def virtualization(runner=subprocess.run):
    try:
        result = runner(["systemd-detect-virt", "--vm"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    if result.returncode == 0 and value and value != "none":
        return value
    return "" if result.returncode == 1 and value == "none" else None


def profile_services(profile, hypervisor=None):
    if profile == "virtual-machine":
        return [*VM_SERVICES, *(["vboxservice.service"] if hypervisor == "oracle" else [])]
    return list(SERVICES)


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
    cpuinfo = Path('/proc/cpuinfo')
    text = cpuinfo.read_text() if cpuinfo.is_file() else ''
    cpu = 'amd' if 'AuthenticAMD' in text else 'intel' if 'GenuineIntel' in text else ''
    return {"gpus": devices, "kernels": [k for k in KERNELS if k in installed], "secure_boot": secure_boot, "cpu": cpu}


def hardware_packages(data):
    if not data["kernels"]:
        raise ForgeError("Install a supported Arch kernel: linux, linux-lts, linux-zen or linux-hardened")
    if not any(gpu["vendor"] == "0x10de" for gpu in data["gpus"]):
        raise ForgeError("The RTX 4050 profile requires an NVIDIA GPU visible to Linux")
    if data["secure_boot"]:
        raise ForgeError("Secure Boot is enabled; configure signed NVIDIA DKMS modules before using this profile")
    return [f"{kernel}-headers" for kernel in data["kernels"]]


def verify_services(runner=subprocess.run, services=SERVICES, conflicts=CONFLICTS):
    candidates = conflicts
    conflicts = []
    for service in candidates:
        enabled = runner(["systemctl", "is-enabled", service], capture_output=True, text=True)
        active = runner(["systemctl", "is-active", service], capture_output=True, text=True)
        if enabled.returncode == 0 or active.returncode == 0:
            conflicts.append(service)
    for service in services:
        result = runner(["systemctl", "is-enabled", service], capture_output=True, text=True)
        if result.stdout.strip() in ("masked", "masked-runtime"):
            conflicts.append(service + " (masked)")
    if conflicts:
        raise ForgeError("Resolve existing service configuration before installing: " + ", ".join(conflicts))


def resolve_plan(plan, apply=False, profile="laptop"):
    if profile == 'auto':
        return resolve_auto(plan, apply)
    if profile not in ("laptop", "virtual-machine"):
        raise ForgeError("Unknown hardware profile")
    plan["profile"] = profile
    if "hardware" not in plan["stages"]:
        return plan
    virtual = profile == "virtual-machine"
    hypervisor = virtualization(subprocess.run) if virtual and (apply or platform.system() == "Linux") else None
    if virtual and apply:
        if not hypervisor:
            raise ForgeError("The virtual-machine profile requires a detected virtual machine")
    if platform.system() == "Linux" and Path("/etc/arch-release").is_file():
        data = inventory()
        headers = [] if virtual else hardware_packages(data) if apply else [f"{k}-headers" for k in data["kernels"] or ["linux"]]
        if apply:
            verify_services(services=profile_services(profile, hypervisor), conflicts=CONFLICTS[-2:] if virtual else CONFLICTS)
        plan["hardware"] = data
    else:
        headers = [] if virtual else ["linux-headers"]
        plan["hardware"] = {"preview_only": True, "kernels": ["linux"]}
    if virtual:
        excluded = {"amd-ucode", "nvidia-open-dkms", "nvidia-utils", "nvidia-prime", "egl-wayland", "vulkan-radeon"}
        plan["packages"] = [package for package in plan["packages"] if package not in excluded]
        plan["packages"].append("vulkan-swrast")
        plan["files"] = [{**item, "source": "configs/mpv/virtual-machine.conf"} if item["target"] == ".config/mpv/mpv.conf" else item for item in plan.get("files", [])]
        plan["hardware"]["validation_scope"] = "virtual-hardware-only"
        plan["hardware"]["hypervisor"] = hypervisor
        if hypervisor == "oracle":
            plan["packages"].append("virtualbox-guest-utils")
    plan["packages"] = list(dict.fromkeys([*plan["packages"], *headers]))
    plan["commands"] = [["sudo", "pacman", "-Syu", "--needed", "--", *plan["packages"]]]
    plan["services"] = profile_services(profile, hypervisor)
    plan["reboot_required"] = True
    return plan


def resolve_auto(plan, apply=False):
    if 'hardware' not in plan['stages']:
        plan['profile'] = 'auto'
        return plan
    native = platform.system() == 'Linux' and Path('/etc/arch-release').is_file()
    if apply and not native:
        raise ForgeError('Automatic hardware setup requires a running Arch Linux system')
    hypervisor = virtualization(subprocess.run) if native else None
    if hypervisor:
        return resolve_plan(plan, apply, 'virtual-machine')
    if apply and hypervisor is None:
        raise ForgeError('Could not determine whether this machine is virtual or physical')
    data = inventory() if native else {'gpus': [], 'kernels': ['linux'], 'secure_boot': False, 'cpu': '', 'preview_only': True}
    if not data['kernels']:
        raise ForgeError('Install a supported Arch kernel before automatic hardware setup')
    vendors = {gpu['vendor'] for gpu in data['gpus']}
    packages = set(plan['packages']) - {'amd-ucode', 'intel-ucode', 'nvidia-open-dkms', 'nvidia-utils', 'nvidia-prime', 'egl-wayland', 'vulkan-radeon', 'vulkan-intel'}
    if data.get('cpu') in ('amd', 'intel'):
        packages.add(data['cpu'] + '-ucode')
    if '0x1002' in vendors:
        packages.add('vulkan-radeon')
    if '0x8086' in vendors:
        packages.add('vulkan-intel')
    services = list(SERVICES[:4])
    if '0x10de' in vendors:
        packages.update(hardware_packages(data))
        packages.update({'nvidia-open-dkms', 'nvidia-utils', 'nvidia-prime', 'egl-wayland'})
        services.extend(SERVICES[4:])
    if apply:
        verify_services(services=services)
    plan.update({'profile': 'auto', 'hardware': data, 'packages': sorted(packages), 'services': services, 'reboot_required': True})
    plan['commands'] = [['sudo', 'pacman', '-Syu', '--needed', '--', *plan['packages']]]
    return plan


def doctor():
    from .diagnostics import collect
    return collect()
