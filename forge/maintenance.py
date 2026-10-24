import shutil
import subprocess
from pathlib import Path

from .diagnostics import collect


LABELS = {
    "environment": "Computer environment",
    "nvidia_gpu": "NVIDIA graphics detected",
    "nvidia_modeset": "NVIDIA display support",
    "secure_boot": "Graphics driver signing",
    "system_services": "Services configured",
    "running_services": "Services running",
    "audio": "Audio output",
    "nvidia_dkms": "Graphics driver for this kernel",
    "guest_integration": "Virtual machine integration",
    "hyprland_config": "Desktop configuration",
    "active_displays": "Active displays",
    "external_1080p120": "External display at 1080p / 120 Hz",
    "internal_display": "Laptop display",
    "shell": "Desktop panel",
    "session_components": "Desktop background services",
    "hyprland_session": "Desktop session",
}


def report(home, runner=subprocess.run, collector=None, usage=None):
    data = (collector or collect)(runner=runner)
    checks = []
    for key, value in data["checks"].items():
        detail = value.get("reason", "")
        if value.get("recovering"):
            detail = "Restarting: " + ", ".join(value["recovering"])
        if value.get("errors"):
            detail = "; ".join(value["errors"])
        checks.append({"name": LABELS.get(key, key.replace("_", " ")), "status": value["status"], "detail": str(detail)[:512]})
    for label, path in (("System storage", Path("/")), ("Personal storage", Path(home))):
        try:
            space = (usage or shutil.disk_usage)(path)
            checks.append({"name": label, "status": "passed" if space.free >= 2 * 1024 ** 3 else "warning", "detail": f"{space.free / 1024 ** 3:.1f} GiB free of {space.total / 1024 ** 3:.1f} GiB"})
        except OSError:
            checks.append({"name": label, "status": "warning", "detail": "Storage information unavailable"})
    return {"health": checks, "message": "Current session checked. Physical NVIDIA, suspend and monitor qualification still requires testing on your laptop."}
