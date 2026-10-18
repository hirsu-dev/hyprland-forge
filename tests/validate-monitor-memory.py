import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge import desktop_settings as settings
from forge.runtime import lock, restore

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
home = Path.home()
name = "FORGE-MEMORY"
assert not settings.read_pending(home)
assert name not in {monitor["name"] for monitor in settings.monitors()}
transactions = []
created = False


def output(action):
    command = ["hyprctl", "output", action]
    command += ["headless", name] if action == "create" else [name]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
    assert result.stdout.strip() == "ok", result.stdout


def wait_for(present):
    for _ in range(50):
        monitors = settings.monitors()
        if (name in {monitor["name"] for monitor in monitors}) == present:
            time.sleep(0.4)
            return settings.monitors()
        time.sleep(0.1)
    raise AssertionError("Virtual display did not change state")


try:
    output("create")
    created = True
    connected = wait_for(True)
    value = settings.current(home, connected)
    value["primary"] = name
    selected = next(item for item in value["outputs"] if item["name"] == name)
    selected.update(enabled=True, mode="preferred", x=-1600, y=50, scale=1, rotation=0, vrr=0)
    first = settings.apply(value, home, connected)
    transactions.append(first["id"])
    settings.finish(home, first["id"], True)
    expected = dict(selected)
    output("remove")
    created = False
    connected = wait_for(False)
    draft = settings.current(home, connected)
    assert name not in {item["name"] for item in draft["outputs"]}
    assert draft["primary"] != name
    draft["tiling"] = "windows" if draft["tiling"] == "caelestia" else "caelestia"
    second = settings.apply(draft, home, connected)
    transactions.append(second["id"])
    settings.finish(home, second["id"], True)
    stored = settings.saved_settings(home)
    assert stored["primary"] == name
    assert next(item for item in stored["outputs"] if item["name"] == name) == expected
    output("create")
    created = True
    connected = wait_for(True)
    restored = next(item for item in connected if item["name"] == name)
    assert restored["x"] == -1600 and restored["y"] == 50, restored
    assert settings.current(home, connected)["primary"] == name
    print(json.dumps({"unplugged_output_retained": True, "preferred_main_retained": True, "reconnected_position_restored": True}))
finally:
    if created:
        output("remove")
        wait_for(False)
    state, _ = settings.paths(home)
    for transaction in reversed(transactions):
        pending = settings.read_pending(home)
        if pending and pending["id"] == transaction:
            settings.finish(home, transaction, False)
        else:
            with lock(home / ".local/state/hyprland-forge"):
                assert not restore(transaction, home, state)
            settings.reload(True)
