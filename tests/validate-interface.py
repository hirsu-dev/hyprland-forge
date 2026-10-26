import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.runtime import lock, restore

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
assert os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
home = Path.home()
transactions = []


def ipc(*args):
    return subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", "forge", *args], text=True, timeout=10).strip()


def status(**expected):
    current = None
    for _ in range(80):
        raw = ipc("status")
        try:
            current = json.loads(raw)
        except json.JSONDecodeError:
            current = raw
            time.sleep(0.1)
            continue
        if all(current.get(key) == value for key, value in expected.items()):
            return current
        time.sleep(0.1)
    raise AssertionError((expected, current))


def appearance(*args):
    result = subprocess.check_output([str(home / ".local/bin/forge-appearance"), *args, "--apply"], text=True, timeout=15).strip()
    assert result.startswith("Appearance saved: "), result
    transactions.append(result.split(": ", 1)[1])


try:
    status()
    ipc("close")
    appearance("--preset", "redline")
    status(accent="#ff4d61")
    appearance("--preset", "icewire")
    status(accent="#74f7ef")
    appearance("--motion", "off")
    status(motion=False)
    appearance("--effects", "off")
    status(motion=False, effects=False)
    ipc("appearance")
    status(settings=True, settingsPage=1, launcher=False, controls=False)
    ipc("launcher")
    status(settings=False, launcher=True)
    ipc("controls")
    status(launcher=False, controls=True)
    ipc("power")
    ipc("powerChoice", "reboot")
    status(power=True, powerAction="reboot", controls=False)
    ipc("close")
    status(power=False, powerAction="", launcher=False, controls=False, settings=False)
    for scale in (0.75, 1, 1.25, 1.75):
        appearance("--interface", json.dumps({"motion": True, "effects": True, "ambient": True, "scanlines": True, "scale": scale, "textScale": 1.25, "spacing": 1.6, "jaggedness": 2, "intensity": 1}))
        ipc("appearance")
        view = None
        for attempt in range(60):
            view = json.loads(subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", "forgeInterface", "status"], text=True, timeout=10))
            if view["values"]["scale"] == scale and view["open"] and view["viewportWidth"] > 100 and view["viewportHeight"] > 20 and view["animationsActive"]:
                break
            time.sleep(0.1)
        else:
            raise AssertionError(view)
        assert view["viewportWidth"] <= view["width"] and view["viewportHeight"] <= view["height"], view
        time.sleep(0.5)
        subprocess.run(["grim", str(home / "Pictures/Forge" / ("interface-scale-" + str(scale) + ".png"))], check=True, timeout=10)
        ipc("close")
        for attempt in range(60):
            view = json.loads(subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", "forgeInterface", "status"], text=True, timeout=10))
            if not view["open"] and not view["animationsActive"]:
                break
            time.sleep(0.05)
        else:
            raise AssertionError(view)
    appearance("--interface", json.dumps({"motion": False}))
    ipc("appearance")
    time.sleep(0.4)
    view = json.loads(subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", "forgeInterface", "status"], text=True, timeout=10))
    assert not view["animationsActive"] and not view["values"]["motion"], view
    errors = json.loads(subprocess.check_output(["hyprctl", "-j", "configerrors"], text=True))
    assert not [error for error in errors if error.strip()], errors
    print(json.dumps({"live_palettes": True, "motion_preference": True, "clean_effects": True, "panel_exclusivity": True, "power_cancellation": True, "ui_scale_extremes": True, "independent_text_and_spacing": True, "hidden_animations_stopped": True, "configuration_errors": []}))
finally:
    ipc("close")
    with lock(home / ".local/state/hyprland-forge"):
        for transaction in reversed(transactions):
            assert not restore(transaction, home, home / ".local/state/hyprland-forge/themes")
    subprocess.run(["hyprctl", "reload"], check=True, capture_output=True, timeout=10)
