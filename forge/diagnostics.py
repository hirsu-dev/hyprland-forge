import json
import math
import os
import platform
import re
import subprocess
from pathlib import Path

from .hardware import inventory, profile_services, virtualization
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
    hypervisor = virtualization(runner)
    virtual = bool(hypervisor)
    data["hypervisor"] = hypervisor
    data["profile"] = "virtual-machine" if virtual else "laptop"
    data["validation_scope"] = "virtual-hardware-only" if virtual else "local-runtime-checks"
    data["physical_hardware_qualified"] = False
    checks = {}
    checks["environment"] = {"status": "warning" if hypervisor is None else "passed", "reason": "Virtualization detection unavailable" if hypervisor is None else hypervisor or "physical-machine"}
    checks["nvidia_gpu"] = {"status": "passed" if any(gpu["vendor"] == "0x10de" for gpu in data["gpus"]) else "failed"}
    parameter = sys_root / "module/nvidia_drm/parameters/modeset"
    try:
        value = parameter.read_text().strip() if parameter.is_file() else "not-loaded"
    except OSError:
        value = "unreadable"
    checks["nvidia_modeset"] = {"status": "passed" if value in ("Y", "1") else "warning" if value == "unreadable" else "failed", "value": value}
    checks["secure_boot"] = {"status": "warning" if data["secure_boot"] else "passed", "enabled": data["secure_boot"]}
    data["services"] = {service: probe(["systemctl", "is-enabled", service], runner) for service in profile_services(data["profile"], hypervisor)}
    checks["system_services"] = {"status": "passed" if all(item["ok"] and item["output"] == "enabled" for item in data["services"].values()) else "failed"}
    data["running_services"] = {service: probe(["systemctl", "is-active", service], runner) for service in data["services"] if not service.startswith("nvidia-")}
    checks["running_services"] = {"status": "passed" if all(item["ok"] and item["output"] == "active" for item in data["running_services"].values()) else "failed"}
    data["audio"] = probe(["wpctl", "status"], runner)
    data["audio_sink"] = probe(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], runner)
    sink = data["audio_sink"]
    has_sink = sink["ok"] and re.search(r'media\.class\s*=\s*"Audio/Sink"', sink["output"])
    dummy = re.search(r'node\.name\s*=\s*"auto_null"', sink["output"])
    checks["audio"] = {"status": "passed" if data["audio"]["ok"] and has_sink and not dummy else "warning" if dummy else "failed", "reason": "Audio routing only; audible playback requires user verification" if has_sink and not dummy else "No usable default audio output"}
    data["dkms"] = probe(["dkms", "status"], runner) if not virtual else None
    kernel = platform.release()
    if virtual:
        for name in ("nvidia_gpu", "nvidia_modeset", "nvidia_dkms"):
            checks[name] = {"status": "not-applicable", "reason": "Physical NVIDIA checks are not qualified by a VM"}
        if hypervisor == "oracle":
            guest = probe(["systemctl", "is-active", "vboxservice.service"], runner)
            checks["guest_integration"] = {"status": "passed" if guest["ok"] and guest["output"] == "active" else "failed"}
    else:
        checks["nvidia_dkms"] = {"status": "passed" if data["dkms"]["ok"] and any(re.match(r"nvidia/[^,]+,\s*" + re.escape(kernel) + r",[^:]+:\s*installed\s*$", line) for line in data["dkms"]["output"].splitlines()) else "failed", "kernel": kernel}
    data["monitors"] = []
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        monitors = probe(["hyprctl", "-j", "monitors"], runner)
        errors = probe(["hyprctl", "-j", "configerrors"], runner)
        try:
            data["monitors"] = json.loads(monitors["output"]) if monitors["ok"] else []
            if not isinstance(data["monitors"], list) or any(not isinstance(monitor, dict) or not isinstance(monitor.get("name"), str) or type(monitor.get("refreshRate", 0)) not in (int, float) or not math.isfinite(monitor.get("refreshRate", 0)) for monitor in data["monitors"]):
                raise ValueError("Expected monitor list")
            config_errors = json.loads(errors["output"]) if errors["ok"] else [errors["error"] or "Unavailable"]
            if not isinstance(config_errors, list) or any(not isinstance(error, str) for error in config_errors):
                raise ValueError("Expected compositor error list")
            config_errors = [error for error in config_errors if error.strip()]
        except (ValueError, TypeError):
            data["monitors"] = []
            config_errors = ["Invalid compositor response"]
        checks["hyprland_config"] = {"status": "passed" if not config_errors else "failed", "errors": config_errors}
        checks["active_displays"] = {"status": "passed" if any(not monitor.get("disabled", False) for monitor in data["monitors"]) else "failed"}
        external = next((monitor for monitor in data["monitors"] if monitor.get("name", "").startswith("HDMI")), None)
        internal = next((monitor for monitor in data["monitors"] if monitor.get("name", "").startswith(("eDP", "LVDS", "DSI"))), None)
        checks["external_1080p120"] = {"status": "passed" if external and external.get("width") == 1920 and external.get("height") == 1080 and abs(float(external.get("refreshRate", 0)) - 120) <= 1 else "warning"}
        checks["internal_display"] = {"status": "passed" if internal and not internal.get("disabled", False) else "warning"}
        if virtual:
            for name in ("external_1080p120", "internal_display"):
                checks[name] = {"status": "not-applicable", "reason": "Virtual outputs do not validate the laptop or physical HDMI"}
        shell = probe(["quickshell", "-c", "forge", "ipc", "call", "forge", "status"], runner)
        try:
            state = json.loads(shell["output"]) if shell["ok"] else {}
            shell_ready = isinstance(state, dict) and type(state.get("screens")) is int and state["screens"] > 0
        except ValueError:
            shell_ready = False
        checks["shell"] = {"status": "passed" if shell_ready else "failed"}
    else:
        checks["hyprland_session"] = {"status": "pending", "reason": "Run inside Hyprland to verify displays and shell"}
    data["checks"] = checks
    data["runtime_ready"] = all(check["status"] in ("passed", "not-applicable") for check in checks.values())
    return data
