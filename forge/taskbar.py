import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .manifest import ForgeError
from .runtime import execute, lock, preflight, restore
from .storage import atomic_write, safe_target

DEFAULTS = {"enabled": True, "primaryOnly": False, "currentMonitorOnly": False, "showTitles": True, "pins": ["kitty", "thunar", "firefox"]}
TARGET = ".config/forge/taskbar.json"
STATE = ".local/state/hyprland-forge/taskbar"


def app_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", value):
        raise ForgeError("Invalid application identifier")
    return value.lower().removesuffix(".desktop")


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ForgeError("Invalid taskbar preferences")
    result = {**DEFAULTS, **value}
    for key in ("enabled", "primaryOnly", "currentMonitorOnly", "showTitles"):
        if type(result[key]) is not bool:
            raise ForgeError("Taskbar switches must be booleans")
    if not isinstance(result["pins"], list) or len(result["pins"]) > 12:
        raise ForgeError("Pin up to 12 applications")
    result["pins"] = list(dict.fromkeys(app_id(item) for item in result["pins"]))
    return result


def load(home):
    target = safe_target(home, TARGET)
    if not target.exists():
        return validate({})
    if target.stat().st_size > 16384:
        raise ForgeError("Taskbar preferences exceed the size limit")
    return validate(json.loads(target.read_text(encoding="utf-8")))


def update(current, patch=None, pin=None, unpin=None):
    value = validate(current)
    if patch is not None:
        if not isinstance(patch, dict):
            raise ForgeError("Taskbar changes must be an object")
        value = validate({**value, **patch})
    if pin is not None:
        identity = app_id(pin)
        if identity not in value["pins"]:
            value["pins"].append(identity)
    if unpin is not None:
        identity = app_id(unpin)
        value["pins"] = [item for item in value["pins"] if item != identity]
    return validate(value)


def apply(home, patch=None, pin=None, unpin=None):
    safe_target(home, ".local/state/hyprland-forge/install.lock")
    safe_target(home, STATE + "/install.lock")
    safe_target(home, TARGET)
    with lock(home / ".local/state/hyprland-forge"):
        value = update(load(home), patch, pin, unpin)
        with tempfile.TemporaryDirectory(prefix="forge-taskbar-") as directory:
            source = Path(directory)
            atomic_write(source / "configs/taskbar.json", (json.dumps(value, indent=2) + "\n").encode("utf-8"), 0o644)
            plan = {"commands": [], "files": [{"source": "configs/taskbar.json", "target": TARGET}]}
            transaction = execute(plan, source, home, home / STATE)
    return {"settings": value, "transaction": transaction}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-taskbar")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--query", action="store_true")
    action.add_argument("--set", dest="patch")
    action.add_argument("--pin")
    action.add_argument("--unpin")
    action.add_argument("--rollback")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    try:
        home = Path.home()
        patch = json.loads(args.patch) if args.patch is not None else None
        if args.patch is not None and not isinstance(patch, dict):
            raise ForgeError("Taskbar changes must be an object")
        if args.rollback:
            if not args.apply:
                raise ForgeError("Rollback requires --apply")
            preflight()
            safe_target(home, ".local/state/hyprland-forge/install.lock")
            safe_target(home, STATE + "/install.lock")
            with lock(home / ".local/state/hyprland-forge"):
                conflicts = restore(args.rollback, home, home / STATE)
            if conflicts:
                raise ForgeError("Kept edited files: " + ", ".join(conflicts))
            result = {"settings": load(home), "restored": True}
        elif args.apply:
            if args.query or (patch is None and args.pin is None and args.unpin is None):
                raise ForgeError("Choose a taskbar change before applying")
            preflight()
            result = apply(home, patch, args.pin, args.unpin)
        else:
            result = {"settings": update(load(home), patch, args.pin, args.unpin)}
        print(json.dumps(result))
        return 0
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
