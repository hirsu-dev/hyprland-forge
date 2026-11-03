import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path.home() / ".local/lib/hyprland-forge"))
from forge import desktop_settings as settings
from forge.runtime import lock, restore

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
home = Path.home()
assert not settings.read_pending(home)
transactions = []
idle = subprocess.check_output(["pgrep", "-u", str(os.getuid()), "-x", "hypridle"], text=True).split()
for pid in idle:
    os.kill(int(pid), signal.SIGSTOP)
test = home / ".config/quickshell/forge/display-controls-test.qml"
assert not test.exists()
before = settings.read_result(home)
proof = {}
try:
    subprocess.run(["quickshell", "-c", "forge", "ipc", "call", "forge", "close"], check=True, capture_output=True, text=True, timeout=10)
    test.write_bytes(Path(__file__).with_name("display-controls.qml").read_bytes())
    result = subprocess.run(["quickshell", "-p", str(test)], capture_output=True, text=True, timeout=30)
    Path("/tmp/forge-display-ui.log").write_text(result.stdout + result.stderr)
    outcome = settings.read_result(home)
    if outcome and outcome != before and outcome["status"] == "kept":
        transactions.append(outcome["id"])
    assert result.returncode == 0 and "FORGE_DISPLAY_UI_PASS" in result.stdout + result.stderr, result.stdout + result.stderr
    assert not any(error in result.stdout + result.stderr for error in ("TypeError", "ReferenceError", "Binding loop", "Unable to assign")), result.stdout + result.stderr
    assert Path("/tmp/forge-display-controls.png").is_file()
    proof["ui_refresh_resolution_orientation_preview_keep"] = True
    actual = settings.monitors()[0]
    assert actual["transform"] == 1 and abs(actual["refreshRate"] - 59.81) < 0.03, actual
    settings.reload()
    time.sleep(0.5)
    actual = settings.monitors()[0]
    assert actual["transform"] == 1 and abs(actual["refreshRate"] - 59.81) < 0.03, actual
    proof["kept_mode_survives_reload"] = True
    for rotation in range(4):
        connected = settings.monitors()
        value = settings.current(home, connected)
        value["outputs"][0]["rotation"] = rotation
        pending = settings.apply(value, home, connected)
        assert settings.monitors()[0]["transform"] == rotation
        settings.finish(home, pending["id"], False)
    proof["all_four_orientations_applied_and_reverted"] = True
    connected = settings.monitors()
    value = settings.current(home, connected)
    value["outputs"][0].update(mode="1280x800@60.00", rotation=0)
    pending = settings.apply(value, home, connected)
    assert settings.monitors()[0]["transform"] == 0
    time.sleep(settings.WAIT + 1)
    assert settings.read_pending(home) is None
    actual = settings.monitors()[0]
    assert actual["transform"] == 1 and abs(actual["refreshRate"] - 59.81) < 0.03, actual
    proof["watchdog_restores_refresh_and_orientation"] = True
    errors = json.loads(subprocess.check_output(["hyprctl", "-j", "configerrors"], text=True))
    assert not [error for error in errors if error.strip()], errors
    proof["config_errors"] = []
    proof["physical_HDMI_120Hz_tested"] = False
    print(json.dumps(proof), flush=True)
finally:
    test.unlink(missing_ok=True)
    pending = settings.read_pending(home)
    if pending:
        settings.finish(home, pending["id"], False)
    state, _ = settings.paths(home)
    for transaction in reversed(transactions):
        with lock(home / ".local/state/hyprland-forge"):
            assert not restore(transaction, home, state)
        settings.reload()
    for pid in idle:
        os.kill(int(pid), signal.SIGCONT)
