import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
status_path = Path(os.environ["XDG_RUNTIME_DIR"]) / "hyprland-forge-session.json"


def status():
    data = json.loads(status_path.read_text())
    assert data["running"] and 0 <= time.time() - data["updated"] < 20
    return data


def children(parent, needle):
    pids = (Path("/proc") / str(parent) / "task" / str(parent) / "children").read_text().split()
    result = []
    for pid in pids:
        try:
            if (Path("/proc") / pid / "cmdline").read_bytes().split(b"\0")[:len(needle)] == needle:
                result.append(int(pid))
        except FileNotFoundError:
            continue
    return result


initial = status()
supervisor = initial["pid"]
assert (Path("/proc") / str(supervisor)).stat().st_uid == os.getuid()
checks = {}
for name, command in (("shell", [b"quickshell", b"-c", b"forge"]), ("clipboard-text", [b"wl-paste", b"--type", b"text"])):
    previous = children(supervisor, command)
    assert len(previous) == 1, previous
    restarts = next(item["restarts"] for item in status()["components"] if item["name"] == name)
    os.kill(previous[0], signal.SIGKILL)
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        data = status()
        component = next(item for item in data["components"] if item["name"] == name)
        current = children(supervisor, command)
        if data["pid"] == supervisor and component["running"] and component["restarts"] > restarts and len(current) == 1 and current != previous:
            break
        time.sleep(0.2)
    else:
        raise AssertionError({"component": name, "status": data})
    checks[name] = "recovered-after-SIGKILL"
result = subprocess.run([str(Path.home() / ".local/bin/forge-session")], capture_output=True, text=True, timeout=5)
assert result.returncode == 0 and status()["pid"] == supervisor
for attempt in range(50):
    result = subprocess.run(["quickshell", "-c", "forge", "ipc", "call", "forge", "status"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0 and json.loads(result.stdout).get("screens", 0) > 0:
        break
    time.sleep(0.2)
else:
    raise AssertionError("Panel did not become interactive after recovery")
print(json.dumps({"scope": "virtual-machine", "components": checks, "duplicate_session_refused": True, "panel_interactive_after_recovery": True}))
