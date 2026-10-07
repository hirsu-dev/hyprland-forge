import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from .manifest import ForgeError
from .runtime import lock, preflight, restore
from .storage import safe_target
from .theme import apply_files


def render(external=None, position="right", scale="auto"):
    if external is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", external):
        raise ForgeError("Invalid external connector name")
    if position not in ("right", "left", "above", "below"):
        raise ForgeError("Invalid laptop display position")
    if scale != "auto":
        try:
            scale = float(scale)
        except (TypeError, ValueError) as exc:
            raise ForgeError("Scale must be auto or a number from 0.75 to 3") from exc
        if not math.isfinite(scale) or not 0.75 <= scale <= 3:
            raise ForgeError("Scale must be auto or a number from 0.75 to 3")
    options = {"internal_position": position, "internal_scale": scale}
    if external:
        options["external"] = external
    literal = ", ".join(key + " = " + json.dumps(value) for key, value in options.items())
    return {".config/hypr/monitors.local.lua": "return { " + literal + " }\n"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-displays")
    parser.add_argument("--external")
    parser.add_argument("--position", choices=("right", "left", "above", "below"), default="right")
    parser.add_argument("--scale", default="auto")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--rollback")
    args = parser.parse_args(argv)
    try:
        payload = render(args.external, args.position, args.scale)
        if not args.apply and not args.rollback:
            print(json.dumps(payload, indent=2))
            return 0
        preflight()
        home = Path.home()
        state = home / ".local/state/hyprland-forge/displays"
        safe_target(home, ".local/state/hyprland-forge/install.lock")
        if args.rollback:
            with lock(home / ".local/state/hyprland-forge"):
                conflicts = restore(args.rollback, home, state)
            if conflicts:
                raise ForgeError("Kept edited files: " + ", ".join(conflicts))
            print("Display settings restored")
        else:
            print("Display settings saved: " + apply_files(payload, home, state))
        try:
            subprocess.run(["hyprctl", "reload"], check=False, capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 0
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Forge displays: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
