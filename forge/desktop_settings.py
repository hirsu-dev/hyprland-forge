import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .manifest import ForgeError
from .runtime import execute, lock, preflight, restore
from .storage import atomic_write, safe_target, write_json


WAIT = 20
RESULT = ".local/state/hyprland-forge/settings/last-result.json"


def lua(value):
    if isinstance(value, dict):
        return "{ " + ", ".join("[" + json.dumps(key) + "] = " + lua(item) for key, item in value.items()) + " }"
    return json.dumps(value, allow_nan=False)


def monitors(runner=subprocess.run):
    result = runner(["hyprctl", "-j", "monitors", "all"], capture_output=True, text=True, check=True, timeout=5)
    values = json.loads(result.stdout)
    if not isinstance(values, list) or not values:
        raise ForgeError("No connected monitors found")
    return values


def modes(monitor):
    return ["preferred", *dict.fromkeys(value.removesuffix("Hz") for value in monitor.get("availableModes", []) if re.fullmatch(r"\d+x\d+@\d+(?:\.\d+)?(?:Hz)?", value))]


def validate(value, connected, limit=16):
    if not isinstance(value, dict) or value.get("tiling") not in ("windows", "caelestia"):
        raise ForgeError("Choose Windows snapping or Caelestia-style tiling")
    outputs = value.get("outputs")
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= limit:
        raise ForgeError("Invalid display list")
    hardware = {monitor["name"]: monitor for monitor in connected}
    selected = {}
    for output in outputs:
        if not isinstance(output, dict):
            raise ForgeError("Invalid display settings")
        name = output.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) or name not in hardware or name in selected:
            raise ForgeError("Connected displays changed; refresh settings")
        if type(output.get("enabled")) is not bool or output.get("mode") not in modes(hardware[name]):
            raise ForgeError("Select an advertised display mode")
        scale = output.get("scale")
        if isinstance(scale, bool) or not isinstance(scale, (float, int)) or not math.isfinite(scale) or not 0.75 <= scale <= 3:
            raise ForgeError("Display scale must be between 0.75 and 3")
        for field in ("x", "y"):
            if type(output.get(field)) is not int or abs(output[field]) > 32768:
                raise ForgeError("Display positions must be whole numbers between -32768 and 32768")
        if type(output.get("rotation")) is not int or output["rotation"] not in (0, 1, 2, 3):
            raise ForgeError("Invalid display rotation")
        if type(output.get("vrr")) is not int or output["vrr"] not in (0, 1, 2):
            raise ForgeError("Invalid variable refresh setting")
        selected[name] = {key: output[key] for key in ("name", "enabled", "mode", "scale", "x", "y", "rotation", "vrr")}
    if set(selected) != set(hardware):
        raise ForgeError("Connected displays changed; refresh settings")
    primary = value.get("primary")
    if primary not in selected or not selected[primary]["enabled"]:
        raise ForgeError("The main display must remain enabled")
    return {"tiling": value["tiling"], "primary": primary, "outputs": list(selected.values())}


def render(value):
    outputs = {item["name"]: {"mode": item["mode"], "position": f"{item['x']}x{item['y']}", "scale": item["scale"], "transform": item["rotation"], "vrr": item["vrr"], "disabled": not item["enabled"]} for item in value["outputs"]}
    return {
        ".config/forge/desktop.json": json.dumps(value, indent=2) + "\n",
        ".config/hypr/monitors.local.lua": "return " + lua({"primary": value["primary"], "outputs": outputs}) + "\n",
        ".config/hypr/tiling.local.lua": "return " + json.dumps(value["tiling"]) + "\n",
    }


def paths(home):
    state = home / ".local/state/hyprland-forge/settings"
    safe_target(home, ".local/state/hyprland-forge/install.lock")
    pending = safe_target(home, ".local/state/hyprland-forge/settings/pending.json")
    return state, pending


def read_pending(home):
    _, path = paths(home)
    return json.loads(path.read_text()) if path.exists() else None


def read_result(home):
    path = safe_target(home, RESULT)
    return json.loads(path.read_text()) if path.exists() else None


def saved_settings(home):
    path = safe_target(home, ".config/forge/desktop.json")
    if not path.exists():
        return {}
    stored = json.loads(path.read_text())
    if not isinstance(stored, dict) or not isinstance(stored.get("outputs"), list):
        raise ForgeError("Saved display settings are invalid")
    hardware = []
    for output in stored["outputs"]:
        if not isinstance(output, dict):
            raise ForgeError("Saved display settings are invalid")
        hardware.append({"name": output.get("name"), "availableModes": [output.get("mode")] if isinstance(output.get("mode"), str) else []})
    return validate(stored, hardware, limit=64)


def active_tiling(runner=subprocess.run):
    result = runner(["hyprctl", "repl", 'return package.loaded["forge.tiling"] and package.loaded["forge.tiling"].mode or "unavailable"'], capture_output=True, text=True, check=True, timeout=5)
    mode = result.stdout.strip()
    if mode not in ("windows", "caelestia"):
        raise ForgeError("Cannot read the active Forge tiling mode from Hyprland")
    return mode


def remember(value, stored, connected):
    outputs = {item["name"]: item for item in stored.get("outputs", [])}
    outputs.update({item["name"]: item for item in value["outputs"]})
    if len(outputs) > 64:
        raise ForgeError("Too many remembered displays")
    preferred = stored.get("primary")
    primary = preferred if preferred in outputs and outputs[preferred]["enabled"] and preferred not in {item["name"] for item in connected} else value["primary"]
    return {"tiling": value["tiling"], "primary": primary, "outputs": list(outputs.values())}


def current(home, connected, runner=subprocess.run):
    stored = saved_settings(home)
    saved = {item["name"]: item for item in stored.get("outputs", [])}
    outputs = []
    for monitor in connected:
        name = monitor["name"]
        entry = {"name": name, "enabled": not monitor.get("disabled", False), "mode": "preferred", "scale": monitor.get("scale", 1), "x": monitor.get("x", 0), "y": monitor.get("y", 0), "rotation": monitor.get("transform", 0), "vrr": 0}
        for mode in modes(monitor)[1:]:
            dimensions, refresh = mode.split("@")
            if dimensions == f"{monitor.get('width')}x{monitor.get('height')}" and abs(float(refresh) - monitor.get("refreshRate", 0)) < 0.02:
                entry["mode"] = mode
                break
        if name in saved:
            entry["vrr"] = saved[name].get("vrr", 0)
        outputs.append(entry)
    enabled = [item["name"] for item in outputs if item["enabled"]]
    primary = stored.get("primary")
    if primary not in enabled:
        primary = next((name for name in enabled if name.startswith("HDMI")), enabled[0] if enabled else outputs[0]["name"])
    return {"tiling": active_tiling(runner), "primary": primary, "outputs": outputs}


def reload(mode_changed=False, runner=subprocess.run):
    result = runner(["hyprctl", "reload"], capture_output=True, text=True, check=True, timeout=5)
    if "ok" not in result.stdout.lower():
        raise ForgeError("The compositor did not accept the reload")
    if mode_changed:
        result = runner(["hyprctl", "dispatch", 'function() require("forge.tiling").apply() end'], capture_output=True, text=True, check=True, timeout=5)
        if "ok" not in result.stdout.lower():
            raise ForgeError("The compositor did not accept the tiling change")


def finish(home, transaction, keep, runner=subprocess.run):
    state, path = paths(home)
    result_path = safe_target(home, RESULT)
    with lock(home / ".local/state/hyprland-forge"):
        pending = read_pending(home)
        if not pending or pending["id"] != transaction:
            return {"status": "unchanged"}
        if keep and time.time() >= pending["deadline"]:
            keep = False
        conflicts = restore(transaction, home, state) if not keep else []
        result = {"status": "kept" if keep else "reverted-with-conflicts" if conflicts else "reverted", "conflicts": conflicts, "id": transaction}
        write_json(result_path, result)
        path.unlink()
    if not keep:
        reload(pending.get("mode_changed", False), runner)
    return result


def apply(value, home, connected, runner=subprocess.run, spawn=subprocess.Popen):
    value = validate(value, connected)
    state, pending_path = paths(home)
    result_path = safe_target(home, RESULT)
    with tempfile.TemporaryDirectory(prefix="forge-settings-") as folder:
        source = Path(folder)
        files = []
        with lock(home / ".local/state/hyprland-forge"):
            if read_pending(home):
                raise ForgeError("Keep or revert the current preview before applying another change")
            changed = active_tiling(runner) != value["tiling"]
            remembered = remember(value, saved_settings(home), connected)
            for index, (target, content) in enumerate(render(remembered).items()):
                safe_target(home, target)
                name = f"configs/{index}"
                atomic_write(source / name, content.encode(), 0o644)
                files.append({"source": name, "target": target})
            write_json(result_path, None)
            transaction = execute({"commands": [], "files": files}, source, home, state)
            pending = {"id": transaction, "deadline": time.time() + WAIT, "mode_changed": changed}
            try:
                write_json(pending_path, pending)
                spawn([sys.executable, str(home / ".local/bin/forge-settings"), "--watch", transaction], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except Exception:
                restore(transaction, home, state)
                pending_path.unlink(missing_ok=True)
                raise
    try:
        reload(changed, runner)
    except Exception:
        finish(home, transaction, False, runner)
        raise
    return pending


def watch(home, transaction):
    while True:
        pending = read_pending(home)
        if not pending or pending["id"] != transaction:
            return {"status": "unchanged"}
        delay = pending["deadline"] - time.time()
        if delay > 0:
            time.sleep(min(delay, WAIT))
            continue
        try:
            return finish(home, transaction, False)
        except ForgeError as exc:
            if str(exc) != "Another Forge operation is running":
                raise
            time.sleep(1)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-settings")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--query", action="store_true")
    group.add_argument("--set")
    group.add_argument("--confirm")
    group.add_argument("--revert")
    group.add_argument("--watch")
    group.add_argument("--recover", action="store_true")
    args = parser.parse_args(argv)
    try:
        home = Path.home()
        if args.watch or args.recover:
            pending = read_pending(home)
            print(json.dumps(watch(home, args.watch or pending["id"]) if pending else {"status": "unchanged"}))
            return 0
        pending = read_pending(home)
        if pending and time.time() >= pending["deadline"]:
            finish(home, pending["id"], False)
        if args.set:
            preflight()
            result = apply(json.loads(args.set), home, monitors())
        elif args.confirm or args.revert:
            result = finish(home, args.confirm or args.revert, bool(args.confirm))
        else:
            connected = monitors()
            result = {"settings": current(home, connected), "monitors": [{"name": item["name"], "modes": modes(item)} for item in connected], "pending": read_pending(home), "last_result": read_result(home)}
        print(json.dumps(result))
        return 0
    except (ForgeError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
