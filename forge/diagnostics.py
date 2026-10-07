import json
import os
import platform
import subprocess
from pathlib import Path

from .hardware import SERVICES, inventory
from .manifest import ForgeError


def probe(command, runner):
    try:
        result = runner(command, capture_output=True, text=True, timeout=10)
        return {"ok": result.returncode == 0, "output": result.stdout.strip(), "error": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output": "", "error": str(exc)}


def collect(sys_root=Path("/sys"), runner=subprocess.run):
    if platform.system() != "Linux":
        raise ForgeError("Hardware diagnostics require Linux")
    data = inventory(sys_root, runner)
    checks = {}
    checks["nvidia_gpu"] = {"status": "passed" if any(gpu["vendor"] == "0x10de" for gpu in data["gpus"]) else "failed"}
    parameter = sys_root / "module/nvidia_drm/parameters/modeset"
    value = parameter.read_text().strip() if parameter.is_file() else "not-loaded"
    checks["nvidia_modeset"] = {"status": "passed" if value in ("Y", "1") else "failed", "value": value}
    checks["secure_boot"] = {"status": "warning" if data["secure_boot"] else "passed", "enabled": data["secure_boot"]}
    data["services"] = {service: probe(["systemctl", "is-enabled", service], runner) for service in SERVICES}
    checks["system_services"] = {"status": "passed" if all(item["ok"] and item["output"] == "enabled" for item in data["services"].values()) else "failed"}
    data["audio"] = probe(["wpctl", "status"], runner)
    checks["audio"] = {"status": "passed" if data["audio"]["ok"] else "failed"}
    data["dkms"] = probe(["dkms", "status"], runner)
    kernel = platform.release()
    checks["nvidia_dkms"] = {"status": "passed" if data["dkms"]["ok"] and any("nvidia" in line.lower() and kernel in line and "installed" in line.lower() for line in data["dkms"]["output"].splitlines()) else "failed", "kernel": kernel}
    data["monitors"] = []
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        monitors = probe(["hyprctl", "-j", "monitors"], runner)
        errors = probe(["hyprctl", "-j", "configerrors"], runner)
        try:
            data["monitors"] = json.loads(monitors["output"]) if monitors["ok"] else []
            if not isinstance(data["monitors"], list):
                raise ValueError("Expected monitor list")
            config_errors = json.loads(errors["output"]) if errors["ok"] else [errors["error"] or "Unavailable"]
        except (ValueError, TypeError):
            data["monitors"] = []
            config_errors = ["Invalid compositor response"]
        checks["hyprland_config"] = {"status": "passed" if not config_errors else "failed", "errors": config_errors}
        external = next((monitor for monitor in data["monitors"] if monitor.get("name", "").startswith("HDMI")), None)
        internal = next((monitor for monitor in data["monitors"] if monitor.get("name", "").startswith(("eDP", "LVDS", "DSI"))), None)
        checks["external_1080p120"] = {"status": "passed" if external and external.get("width") == 1920 and external.get("height") == 1080 and abs(float(external.get("refreshRate", 0)) - 120) <= 1 else "warning"}
        checks["internal_display"] = {"status": "passed" if internal and not internal.get("disabled", False) else "warning"}
        checks["shell"] = {"status": "passed" if probe(["quickshell", "-c", "forge", "ipc", "call", "forge", "status"], runner)["ok"] else "failed"}
    else:
        checks["hyprland_session"] = {"status": "pending", "reason": "Run inside Hyprland to verify displays and shell"}
    data["checks"] = checks
    data["runtime_ready"] = all(check["status"] == "passed" for check in checks.values())
    return data
