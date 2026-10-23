import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.control import STATE
from forge.runtime import lock, restore

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
assert os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
home = Path.home()
transactions = []
processes = []
original_output = None
sink_id = None
idle = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "hypridle"], capture_output=True, text=True).stdout.split()
for pid in idle:
    os.kill(int(pid), signal.SIGSTOP)


def ipc(target, *arguments):
    return subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", target, *map(str, arguments)], text=True, timeout=10).strip()


def wait(predicate, getter):
    latest = None
    for _ in range(100):
        latest = getter()
        if predicate(latest):
            return latest
        time.sleep(0.1)
    raise AssertionError(latest)


def status():
    return json.loads(ipc("forge", "status"))


def alerts():
    return json.loads(ipc("forgeAlerts", "status"))


def hub():
    return json.loads(ipc("forgeHub", "status"))


def control(action, **values):
    result = subprocess.run([str(home / ".local/bin/forge-control")], input=json.dumps({"action": action, **values}) + "\n", text=True, capture_output=True, timeout=30, check=True)
    value = json.loads(result.stdout)
    if "transaction" in value:
        transactions.append(value["transaction"])
    return value


try:
    subprocess.run(["hyprctl", "dispatch", 'hl.dsp.dpms({action="on"})'], check=True, capture_output=True)
    subprocess.run(["hyprctl", "reload"], check=True, capture_output=True)
    wait(lambda value: not value["busy"], hub)
    ipc("forgeAlerts", "clear")
    ipc("forgeAlerts", "quiet", "false")
    subprocess.run(["notify-send", "--app-name=Forge Test", "--expire-time=1500", "Signal test", "<b>Untrusted content stays plain text</b>"], check=True)
    first = wait(lambda value: len(value["history"]) == 1 and value["popups"] == 1, alerts)
    assert first["history"][0]["body"].startswith("<b>")
    wait(lambda value: value["active"] == 0 and len(value["history"]) == 1, alerts)
    ipc("forgeAlerts", "quiet", "true")
    subprocess.run(["notify-send", "--expire-time=1000", "Quiet signal", "No popup"], check=True)
    wait(lambda value: len(value["history"]) == 2 and value["popups"] == 0, alerts)
    ipc("forgeAlerts", "quiet", "false")
    action = subprocess.Popen(["notify-send", "--wait", "--expire-time=10000", "--action=default=OPEN", "Action signal", "Test action"], stdout=subprocess.PIPE, text=True)
    processes.append(action)
    entry = wait(lambda value: value["history"][0]["title"] == "Action signal", alerts)["history"][0]
    ipc("forgeAlerts", "invoke", entry["id"], 0)
    output, _ = action.communicate(timeout=10)
    assert output.strip() == "default", output
    for page in ("alerts", "connections", "customize", "hardware", "capture", "recovery"):
        ipc("forge", "hub", page)
        wait(lambda value: value["page"] == page and not value["busy"], hub)
        state = status()
        assert state["hub"] and not any(state[key] for key in ("settings", "overview", "launcher", "controls", "power")), state
    ipc("forge", "overview")
    assert status()["overview"] and not status()["hub"]
    ipc("forge", "close")
    current = control("preferences")["preferences"]
    value = control("save", patch={"sensitivity": 0.15, "gaming": True})
    assert value["preferences"]["gaming"]
    option = json.loads(subprocess.check_output(["hyprctl", "-j", "getoption", "animations:enabled"], text=True))
    assert option["bool"] is False, option
    control("save", patch={"gaming": False})
    telemetry = control("metrics")
    assert telemetry["memoryTotal"] > 0 and telemetry["gpu"] is None
    profiles = control("profile-save", name="Forge VM Validation")["preferences"]["profiles"]
    assert "Forge VM Validation" in profiles
    preview = control("profile-preview", name="Forge VM Validation")["pending"]
    subprocess.run([str(home / ".local/bin/forge-settings"), "--revert", preview["id"]], check=True, capture_output=True)
    subprocess.run(["pw-cli", "create-node", "adapter", '{ factory.name=support.null-audio-sink node.name=ForgeDeckTestSink node.description="Forge deck test" media.class=Audio/Sink object.linger=true audio.position=[ FL FR ] }'], check=True, capture_output=True)
    outputs = wait(lambda values: any(value["name"] == "ForgeDeckTestSink" for value in values), lambda: json.loads(ipc("forgeHub", "outputs")))
    original_output = next((value["id"] for value in outputs if value["active"]), None)
    sink_id = next(value["id"] for value in outputs if value["name"] == "ForgeDeckTestSink")
    ipc("forgeHub", "output", sink_id)
    wait(lambda values: any(value["id"] == sink_id and value["active"] for value in values), lambda: json.loads(ipc("forgeHub", "outputs")))
    capture = subprocess.run([str(home / ".local/bin/forge-capture"), "--mode", "display"], text=True, capture_output=True, check=True, timeout=20)
    screenshot = Path(json.loads(capture.stdout)["path"])
    assert screenshot.read_bytes().startswith(b"\x89PNG")
    recording = subprocess.Popen([str(home / ".local/bin/forge-capture"), "--mode", "display", "--record"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    processes.append(recording)
    time.sleep(4)
    recording.send_signal(signal.SIGINT)
    output, errors = recording.communicate(timeout=15)
    assert recording.returncode == 0, (output, errors)
    movie = Path(json.loads(output)["path"])
    assert movie.stat().st_size > 1000
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "quiet", "-show_format", "-of", "json", str(movie)], text=True))
    assert float(probe["format"]["duration"]) > 0
    errors = json.loads(subprocess.check_output(["hyprctl", "-j", "configerrors"], text=True))
    assert not [error for error in errors if error.strip()], errors
    print(json.dumps({"notification_history": True, "notification_expiry": True, "dnd": True, "notification_action": True, "all_deck_pages": True, "panel_exclusivity": True, "input_apply": True, "gaming_effects": True, "display_profile_revert": True, "hardware_telemetry": True, "audio_output_switch": True, "screenshot": str(screenshot), "recording": str(movie), "config_errors": []}))
finally:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.communicate(timeout=5)
    if original_output is not None:
        ipc("forgeHub", "output", original_output)
    if sink_id is not None:
        subprocess.run(["pw-cli", "destroy", str(sink_id)], capture_output=True)
    ipc("forgeAlerts", "clear")
    ipc("forgeAlerts", "quiet", "false")
    ipc("forge", "close")
    with lock(home / ".local/state/hyprland-forge"):
        for transaction in reversed(transactions):
            assert not restore(transaction, home, home / STATE)
    subprocess.run(["hyprctl", "reload"], capture_output=True, check=True)
    for pid in idle:
        os.kill(int(pid), signal.SIGCONT)
