import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge import desktop_settings as settings
from forge.runtime import lock, restore
from forge.storage import atomic_write

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
home = Path.home()
assert not settings.read_pending(home)
transactions = []
process = None
idle = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "hypridle"], capture_output=True, text=True).stdout.split()
for pid in idle:
    os.kill(int(pid), signal.SIGSTOP)


def ctl(*args):
    result = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


def dispatch(value):
    result = ctl("dispatch", value)
    assert result.strip() == "ok", result


def client():
    return next(item for item in json.loads(ctl("-j", "clients")) if item["class"] == "forge-tiling-test")


try:
    dispatch('hl.dsp.dpms({action = "on"})')
    connected = settings.monitors()
    baseline = settings.current(home, connected)
    value = json.loads(json.dumps(baseline))
    value["tiling"] = "windows"
    pending = settings.apply(value, home, connected)
    transactions.append(pending["id"])
    settings.finish(home, pending["id"], True)
    time.sleep(1)
    assert not [error for error in json.loads(ctl("-j", "configerrors")) if error.strip()]
    process = subprocess.Popen(["kitty", "--start-as", "normal", "-o", "remember_window_size=no", "--class", "forge-tiling-test", "--title", "Forge tiling validation", "sh", "-c", "sleep 120"], env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"}, stdout=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(0.2)
        if any(item["class"] == "forge-tiling-test" for item in json.loads(ctl("-j", "clients"))):
            break
    time.sleep(1)
    original = client()
    assert original["floating"], original
    dispatch('hl.dsp.focus({window = "class:forge-tiling-test"})')
    dispatch('function() require("forge.tiling").snap("left") end')
    time.sleep(0.6)
    left = client()
    dispatch('function() require("forge.tiling").snap("right") end')
    time.sleep(0.6)
    right = client()
    assert right["at"][0] > left["at"][0], (left, right)
    assert right["size"] == left["size"], (left, right)
    dispatch('function() require("forge.tiling").snap("restore") end')
    time.sleep(0.6)
    restored = client()
    assert restored["size"] == original["size"] and restored["at"] == original["at"], (original, restored)
    value["tiling"] = "caelestia"
    pending = settings.apply(value, home, settings.monitors())
    transactions.append(pending["id"])
    time.sleep(0.8)
    assert not client()["floating"]
    settings.finish(home, pending["id"], False)
    transactions.pop()
    time.sleep(0.8)
    assert client()["floating"]
    value["outputs"][0]["scale"] = 1 if value["outputs"][0]["scale"] != 1 else 2
    value["tiling"] = "caelestia"
    pending = settings.apply(value, home, settings.monitors())
    transactions.append(pending["id"])
    time.sleep(1)
    assert settings.monitors()[0]["scale"] == value["outputs"][0]["scale"]
    time.sleep(settings.WAIT + 2)
    assert settings.read_pending(home) is None
    assert settings.monitors()[0]["scale"] == baseline["outputs"][0]["scale"]
    assert client()["floating"]
    transactions.pop()
    value = settings.current(home, settings.monitors())
    value["tiling"] = "caelestia"
    pending = settings.apply(value, home, settings.monitors())
    transactions.append(pending["id"])
    path = home / ".config/hypr/tiling.local.lua"
    installed = path.read_bytes()
    edited = installed + b"\n"
    try:
        atomic_write(path, edited, 0o644)
        outcome = settings.finish(home, pending["id"], False)
        assert outcome["status"] == "reverted-with-conflicts"
        assert settings.read_pending(home) is None
        assert settings.read_result(home) == outcome
        assert path.read_bytes() == edited
    finally:
        if path.read_bytes() == edited:
            atomic_write(path, installed, 0o644)
    print(json.dumps({"windows_float": True, "left_right_snap": True, "restore_geometry": True, "caelestia_tiles": True, "manual_revert": True, "scale_change": True, "independent_watchdog_revert": True, "external_edit_preserved_without_stuck_preview": True}))
finally:
    for pid in idle:
        os.kill(int(pid), signal.SIGCONT)
    if process:
        process.terminate()
        process.wait(timeout=10)
    for transaction in reversed(transactions):
        pending = settings.read_pending(home)
        if pending and pending["id"] == transaction:
            settings.finish(home, transaction, False)
        else:
            state, _ = settings.paths(home)
            with lock(home / ".local/state/hyprland-forge"):
                assert not restore(transaction, home, state)
            settings.reload(True)
