import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from .manifest import ForgeError
from .runtime import execute, lock, preflight, restore
from .storage import atomic_write, safe_target

TARGET = ".config/forge/preferences.json"
STATE = ".local/state/hyprland-forge/control"
ACTIONS = {
    "terminal": ("SUPER + Return", "kitty"),
    "files": ("SUPER + E", "thunar"),
    "browser": ("SUPER + B", "firefox"),
    "launcher": ("SUPER + Space", "~/.local/bin/forge-launcher"),
    "controls": ("SUPER + A", "quickshell -c forge ipc call forge controls"),
    "settings": ("SUPER + I", "quickshell -c forge ipc call forge settings"),
    "lock": ("SUPER + L", "hyprlock"),
}
LIVE = {"enabled": False, "project": "", "assets": "", "output": "primary", "fps": 30, "silent": True, "pauseOnGaming": True}
GAME = {"overlay": False, "gamescope": False, "width": 1920, "height": 1080, "fps": 120}
DEFAULTS = {"sensitivity": 0, "naturalScroll": True, "tapToClick": True, "disableWhileTyping": True, "gaming": False, "bindings": {key: item[0] for key, item in ACTIONS.items()}, "wallpapers": {}, "profiles": {}, "liveWallpaper": LIVE, "gameOptions": GAME}


def run(command, runner=subprocess.run, accepted=(0,), timeout=15, **kwargs):
    result = runner(command, text=True, capture_output=True, timeout=timeout, env={**os.environ, "LC_ALL": "C"}, **kwargs)
    if result.returncode not in accepted:
        raise ForgeError("Operation failed: " + command[0] + " (" + str(result.returncode) + ")")
    return result.stdout.strip()


def text(value, limit=256):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ForgeError("Invalid text value")
    return value


def keybind(value):
    value = text(value, 80)
    tokens = [token.strip() for token in value.split("+")]
    if len(tokens) < 2 or len(tokens) > 5 or len(set(tokens[:-1])) != len(tokens[:-1]) or any(token not in ("SUPER", "CTRL", "ALT", "SHIFT") for token in tokens[:-1]):
        raise ForgeError("Use modifiers followed by a key, such as SUPER + CTRL + T")
    if not re.fullmatch(r"[A-Za-z0-9]|F(?:[1-9]|1[0-2])|Return|Space|Tab|Home|End|Prior|Next|Escape", tokens[-1]):
        raise ForgeError("Unsupported shortcut key")
    if len(tokens[-1]) == 1:
        tokens[-1] = tokens[-1].upper()
    return " + ".join(sorted(tokens[:-1], key=("SUPER", "CTRL", "ALT", "SHIFT").index) + [tokens[-1]])


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ForgeError("Invalid desktop preferences")
    result = json.loads(json.dumps({**DEFAULTS, **value}, allow_nan=False))
    sensitivity = result["sensitivity"]
    if isinstance(sensitivity, bool) or not isinstance(sensitivity, (int, float)) or not math.isfinite(sensitivity) or not -1 <= sensitivity <= 1:
        raise ForgeError("Pointer sensitivity must be between -1 and 1")
    for name in ("naturalScroll", "tapToClick", "disableWhileTyping", "gaming"):
        if type(result[name]) is not bool:
            raise ForgeError("Input switches must be booleans")
    if not isinstance(result["bindings"], dict) or set(result["bindings"]) != set(ACTIONS):
        raise ForgeError("Unknown shortcut action")
    result["bindings"] = {name: keybind(binding) for name, binding in result["bindings"].items()}
    reserved = {"ALT + Tab", "SUPER + O", "SUPER + N", "SUPER + G", "SUPER + Q", "SUPER + V", "SUPER + F", "SUPER + S", "SUPER + SHIFT + S", "SUPER + CTRL + V", "SUPER + SHIFT + R", "SUPER + SHIFT + Escape"}
    reserved.update("SUPER + " + str(index) for index in range(10))
    reserved.update("SUPER + SHIFT + " + str(index) for index in range(10))
    reserved.update("SUPER + CTRL + " + key for key in ("Home", "End", "Prior", "Next"))
    if len(set(result["bindings"].values())) != len(ACTIONS) or set(result["bindings"].values()) & reserved:
        raise ForgeError("Shortcut conflicts with another Forge action")
    if not isinstance(result["wallpapers"], dict) or len(result["wallpapers"]) > 16:
        raise ForgeError("Too many wallpapers")
    for name, path in result["wallpapers"].items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}|default", name):
            raise ForgeError("Invalid wallpaper output")
        if not Path(text(path, 4096)).is_absolute() or Path(path).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
            raise ForgeError("Choose an absolute image path")
    if not isinstance(result["profiles"], dict) or len(result["profiles"]) > 12:
        raise ForgeError("Save up to 12 display profiles")
    for name, settings in result["profiles"].items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,31}", name) or not isinstance(settings, dict):
            raise ForgeError("Invalid display profile")
        from .desktop_settings import validate as validate_display
        outputs = settings.get("outputs", [])
        hardware = [{"name": item.get("name"), "availableModes": [item.get("mode")]} for item in outputs if isinstance(item, dict)] if isinstance(outputs, list) else []
        validate_display(settings, hardware)
    live = result["liveWallpaper"]
    game = result["gameOptions"]
    if not isinstance(live, dict) or set(live) != set(LIVE) or not isinstance(game, dict) or set(game) != set(GAME):
        raise ForgeError("Invalid live wallpaper or gaming options")
    for name in ("enabled", "silent", "pauseOnGaming"):
        if type(live[name]) is not bool:
            raise ForgeError("Wallpaper switches must be booleans")
    for name in ("overlay", "gamescope"):
        if type(game[name]) is not bool:
            raise ForgeError("Gaming switches must be booleans")
    if type(live["fps"]) is not int or not 10 <= live["fps"] <= 60:
        raise ForgeError("Live wallpaper FPS must be between 10 and 60")
    if not isinstance(live["output"], str) or not re.fullmatch(r"primary|[A-Za-z][A-Za-z0-9_-]{0,63}", live["output"]):
        raise ForgeError("Invalid live wallpaper output")
    for name in ("project", "assets"):
        value = live[name]
        if value != "" and not Path(text(value, 4096)).is_absolute():
            raise ForgeError("Choose an absolute wallpaper directory")
    for name, lower, upper in (("width", 640, 3840), ("height", 480, 2160), ("fps", 30, 240)):
        if type(game[name]) is not int or not lower <= game[name] <= upper:
            raise ForgeError("Invalid game resolution or frame cap")
    return result


def load(home):
    path = safe_target(home, TARGET)
    if path.exists() and path.stat().st_size > 131072:
        raise ForgeError("Preferences exceed the size limit")
    return validate(json.loads(path.read_text(encoding="utf-8")) if path.exists() else {})


def render(value):
    input_config = {"sensitivity": value["sensitivity"], "touchpad": {"natural_scroll": value["naturalScroll"], "tap_to_click": value["tapToClick"], "disable_while_typing": value["disableWhileTyping"]}}
    from .desktop_settings import lua
    lines = ["hl.config(" + lua({"input": input_config}) + ")"]
    if value["gaming"]:
        lines.append("hl.config(" + lua({"animations": {"enabled": False}, "decoration": {"blur": {"enabled": False}, "shadow": {"enabled": False}}}) + ")")
    return {TARGET: json.dumps(value, indent=2) + "\n", ".config/hypr/forge/preferences.lua": "\n".join(lines) + "\n", ".config/hypr/forge/shortcuts.lua": "return " + lua(value["bindings"]) + "\n"}


def apply(home, patch, runner=subprocess.run):
    if not isinstance(patch, dict):
        raise ForgeError("Changes must be an object")
    safe_target(home, ".local/state/hyprland-forge/install.lock")
    with lock(home / ".local/state/hyprland-forge"):
        value = validate({**load(home), **patch})
        for path in value["wallpapers"].values():
            if not Path(path).is_file():
                raise ForgeError("Wallpaper file does not exist")
        if value["liveWallpaper"]["enabled"]:
            from .wallpaper import validate_project
            validate_project(value["liveWallpaper"])
        with tempfile.TemporaryDirectory(prefix="forge-control-") as directory:
            source = Path(directory)
            files = []
            for index, (target, content) in enumerate(render(value).items()):
                name = "configs/" + str(index)
                atomic_write(source / name, content.encode(), 0o644)
                files.append({"source": name, "target": target})
            transaction = execute({"commands": [], "files": files}, source, home, home / STATE)
    try:
        run(["hyprctl", "reload"], runner)
    except Exception:
        with lock(home / ".local/state/hyprland-forge"):
            restore(transaction, home, home / STATE)
        raise
    return {"preferences": value, "transaction": transaction}


def split_fields(line):
    fields, current, escaped = [], "", False
    for character in line:
        if escaped:
            current += character
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append(current)
            current = ""
        else:
            current += character
    fields.append(current + ("\\" if escaped else ""))
    return fields


def network(runner=subprocess.run):
    raw = run(["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE", "device", "wifi", "list", "--rescan", "auto"], runner)
    networks = []
    for line in raw.splitlines():
        fields = split_fields(line)
        if len(fields) == 6 and fields[1]:
            networks.append(dict(zip(("active", "ssid", "bssid", "signal", "security", "device"), fields)))
    connections = []
    raw = run(["nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE", "connection", "show"], runner)
    for line in raw.splitlines():
        fields = split_fields(line)
        if len(fields) == 4:
            connections.append(dict(zip(("name", "uuid", "type", "device"), fields)))
    return {"networks": networks, "connections": connections, "wifi": run(["nmcli", "radio", "wifi"], runner) == "enabled"}


def wifi_connect(request, runner=subprocess.run):
    selected = next((item for item in network(runner)["networks"] if item["bssid"] == request.get("bssid")), None)
    if not selected:
        raise ForgeError("Network disappeared; refresh the list")
    password = request.get("password", "")
    if not isinstance(password, str) or "\n" in password or "\r" in password or "\x00" in password or len(password) > 64:
        raise ForgeError("Invalid Wi-Fi password")
    security = selected["security"]
    secured = security not in ("", "--")
    if secured and ("802.1X" in security or "WPA3" in security and "WPA2" not in security or "WEP" in security):
        raise ForgeError("Use Advanced Network for enterprise, WEP or WPA3-only networks")
    if secured and not (8 <= len(password) <= 63 or len(password) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", password)):
        raise ForgeError("Enter an 8–63 character WPA password")
    identity = str(uuid.uuid4())
    command = ["nmcli", "connection", "add", "type", "wifi", "ifname", text(selected["device"], 64), "con-name", "Forge-" + identity[:8], "connection.uuid", identity, "ssid", text(selected["ssid"], 32), "802-11-wireless.bssid", selected["bssid"], "connection.autoconnect", "no"]
    if secured:
        command += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk-flags", "2"]
    run(command, runner)
    try:
        with tempfile.TemporaryDirectory(prefix="forge-wifi-") as folder:
            path = Path(folder) / "secret"
            atomic_write(path, ("802-11-wireless-security.psk:" + password + "\n").encode(), 0o600)
            run(["nmcli", "--wait", "25", "connection", "up", "uuid", identity, "passwd-file", str(path)], runner, timeout=30)
    except Exception:
        run(["nmcli", "connection", "delete", "uuid", identity], runner, accepted=(0, 10))
        raise
    return {"message": "Connected. Password was not saved; use Advanced Network to configure automatic reconnection."}


def bluetooth(runner=subprocess.run):
    devices = []
    raw = run(["bluetoothctl", "devices"], runner)
    for line in raw.splitlines():
        match = re.fullmatch(r"Device ([0-9A-Fa-f:]{17}) (.*)", line)
        if match:
            info = run(["bluetoothctl", "info", match[1]], runner)
            devices.append({"address": match[1], "name": match[2], "paired": "Paired: yes" in info, "connected": "Connected: yes" in info})
    return {"devices": devices, "powered": "Powered: yes" in run(["bluetoothctl", "show"], runner)}


def metrics(proc=Path("/proc"), sysfs=Path("/sys"), runner=subprocess.run):
    memory = {}
    for line in (proc / "meminfo").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2:
            memory[fields[0].rstrip(":")] = int(fields[1])
    cpu = [int(value) for value in (proc / "stat").read_text().splitlines()[0].split()[1:]]
    result = {"memoryTotal": memory.get("MemTotal", 0), "memoryUsed": memory.get("MemTotal", 0) - memory.get("MemAvailable", 0), "cpuTotal": sum(cpu[:8]), "cpuIdle": cpu[3] + (cpu[4] if len(cpu) > 4 else 0), "temperatures": [], "batteries": [], "gpu": None}
    for device in sorted((sysfs / "class/hwmon").glob("hwmon*")):
        for sensor in device.glob("temp*_input"):
            try:
                value = int(sensor.read_text()) / 1000
                label = sensor.with_name(sensor.name.replace("_input", "_label"))
                name = label.read_text().strip() if label.exists() else (device / "name").read_text().strip()
                if -20 <= value <= 150:
                    result["temperatures"].append({"name": name, "celsius": value})
            except (OSError, ValueError):
                pass
    for battery in (sysfs / "class/power_supply").glob("*"):
        try:
            if (battery / "type").read_text().strip() == "Battery":
                result["batteries"].append({"name": battery.name, "percent": int((battery / "capacity").read_text()), "status": (battery / "status").read_text().strip()})
        except (OSError, ValueError):
            pass
    try:
        raw = run(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], runner, timeout=3)
        values = [part.strip() for part in raw.splitlines()[0].split(",")]
        result["gpu"] = {"name": values[0], "usage": float(values[1]), "temperature": float(values[2]), "memoryUsed": float(values[3]), "memoryTotal": float(values[4])}
    except (OSError, ValueError, IndexError, ForgeError, subprocess.SubprocessError):
        pass
    return result


def backups(home):
    root = home / ".local/state/hyprland-forge"
    result = []
    for group in ("", "themes", "taskbar", "control", "settings"):
        for record in (root / group / "transactions").glob("*/transaction.json"):
            safe_target(home, record.relative_to(home).as_posix())
            try:
                value = json.loads(record.read_text())
                if value.get("status") == "complete":
                    result.append({"id": record.parent.name, "group": group, "files": len(value.get("plan", {}).get("files", []))})
            except (OSError, ValueError):
                pass
    return sorted(result, key=lambda item: item["id"], reverse=True)[:30]


def dispatch(request, home, runner=subprocess.run):
    if not isinstance(request, dict):
        raise ForgeError("Request must be an object")
    action = request.get("action")
    if action == "preferences":
        from .wallpaper import renderer_status
        return {"preferences": load(home), "wallpaperRenderer": renderer_status()}
    if action == "wallpaper-library":
        from .wallpaper import library
        return library(home)
    if action == "metrics":
        return {**metrics(runner=runner), "preferences": load(home)}
    if action == "network":
        return network(runner)
    if action == "bluetooth":
        return bluetooth(runner)
    if action == "backups":
        return {"backups": backups(home), "preferences": load(home)}
    if action == "updates":
        return {"updates": run(["checkupdates"], runner, accepted=(0, 2), timeout=90).splitlines(), "message": "Preview only. Official repository packages; AUR packages are not managed here."}
    if action == "logs":
        return {"logs": run(["journalctl", "--user", "-b", "-n", "100", "--no-pager"], runner)[-20000:]}
    preflight()
    if action == "save":
        return apply(home, request.get("patch"), runner)
    if action == "profile-save":
        from .desktop_settings import current, monitors
        value = load(home)
        name = text(request.get("name"), 32)
        value["profiles"][name] = current(home, monitors(runner), runner)
        return apply(home, {"profiles": value["profiles"]}, runner)
    if action == "profile-preview":
        from .desktop_settings import apply as preview, monitors
        value = load(home)["profiles"].get(request.get("name"))
        if not value:
            raise ForgeError("Display profile not found")
        return {"pending": preview(value, home, monitors(runner), runner)}
    if action == "wifi-connect":
        return wifi_connect(request, runner)
    if action == "wifi-power":
        if type(request.get("enabled")) is not bool:
            raise ForgeError("Invalid Wi-Fi switch")
        run(["nmcli", "radio", "wifi", "on" if request["enabled"] else "off"], runner)
        return network(runner)
    if action == "connection-up":
        identity = request.get("uuid")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-fA-F0-9-]{36}", identity):
            raise ForgeError("Invalid connection identifier")
        run(["nmcli", "--wait", "25", "connection", "up", "uuid", identity], runner, timeout=30)
        return network(runner)
    if action == "bluetooth-power":
        if type(request.get("enabled")) is not bool:
            raise ForgeError("Invalid Bluetooth switch")
        run(["bluetoothctl", "power", "on" if request["enabled"] else "off"], runner)
        return bluetooth(runner)
    if action in ("bluetooth-connect", "bluetooth-disconnect"):
        address = request.get("address")
        if not isinstance(address, str) or not re.fullmatch(r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}", address):
            raise ForgeError("Invalid Bluetooth address")
        run(["bluetoothctl", "--timeout", "15", action.removeprefix("bluetooth-"), address], runner, timeout=20)
        return bluetooth(runner)
    if action == "restore":
        group = request.get("group")
        identity = request.get("id")
        if {"id": identity, "group": group, "files": request.get("files")} not in backups(home):
            raise ForgeError("Choose an available config backup")
        from .desktop_settings import read_pending
        if read_pending(home):
            raise ForgeError("Keep or revert the active display preview first")
        with lock(home / ".local/state/hyprland-forge"):
            conflicts = restore(identity, home, home / ".local/state/hyprland-forge" / group)
        run(["hyprctl", "reload"], runner)
        return {"message": "Configs restored. Packages and boot files were not changed." if not conflicts else "Kept externally edited files: " + ", ".join(conflicts), "backups": backups(home), "preferences": load(home)}
    raise ForgeError("Unknown control action")


def main():
    try:
        if platform.system() != "Linux":
            raise ForgeError("Forge control requires Linux")
        line = sys.stdin.readline(131073)
        if len(line) > 131072:
            raise ForgeError("Request exceeds the size limit")
        print(json.dumps(dispatch(json.loads(line), Path.home())))
        return 0
    except (ForgeError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
