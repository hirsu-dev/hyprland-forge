import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.runtime import lock, restore
from forge.taskbar import STATE

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
assert os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
home = Path.home()
transactions = []
processes = []
extra_output = "FORGE-TASKBAR"
output_created = False
original_workspace = None
idle = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "hypridle"], capture_output=True, text=True).stdout.split()
for pid in idle:
    os.kill(int(pid), signal.SIGSTOP)


def ipc(target, *args):
    return subprocess.check_output(["quickshell", "-c", "forge", "ipc", "call", target, *args], text=True, timeout=10).strip()


def status():
    for _ in range(60):
        try:
            return json.loads(ipc("forgeTasks", "status"))
        except json.JSONDecodeError:
            time.sleep(0.1)
    raise AssertionError("Taskbar IPC did not become ready")


def wait(predicate):
    for _ in range(80):
        state = status()
        if predicate(state):
            return state
        time.sleep(0.1)
    raise AssertionError({"shell": state, "monitors": json.loads(ctl("-j", "monitors")), "clients": json.loads(ctl("-j", "clients"))})


def configure(*args):
    previous = status()["transaction"]
    action = {"--set": "configure", "--pin": "pin", "--unpin": "unpin"}[args[0]]
    ipc("forgeTasks", action, args[1])
    value = wait(lambda state: not state["busy"] and (state["error"] or state["transaction"] != previous))
    assert not value["error"], value["error"]
    transactions.append(value["transaction"])
    return value


def ctl(*args):
    return subprocess.check_output(["hyprctl", *args], text=True, timeout=10).strip()


def activate_title(title):
    state = status()
    index = next(index for index, window in enumerate(state["windows"]) if window["title"] == title)
    ipc("forgeTasks", "activate", str(index))
    wait(lambda value: any(window["title"] == title and window["active"] for window in value["windows"]))


def bottom_reserved():
    return json.loads(ctl("-j", "monitors"))[0]["reserved"][3]


try:
    ipc("forge", "close")
    assert not any(window["appId"].lower() == "kitty" for window in status()["windows"]), "Close other Kitty windows before this isolated test"
    original_workspace = json.loads(ctl("-j", "monitors"))[0]["activeWorkspace"]["id"]
    occupied = {workspace["id"] for workspace in json.loads(ctl("-j", "workspaces"))}
    fixture_workspace = next(index for index in range(930, 950) if index not in occupied)
    ctl("dispatch", "hl.dsp.focus({workspace=" + str(fixture_workspace) + "})")
    configure("--set", '{"enabled":true,"primaryOnly":false,"currentMonitorOnly":false,"showTitles":true}')
    wait(lambda value: value["enabled"] and all(bar["visible"] for bar in value["bars"]))
    time.sleep(0.3)
    assert bottom_reserved() == 60
    for title in ("ForgeTaskbar-A", "ForgeTaskbar-B"):
        processes.append(subprocess.Popen(["kitty", "--start-as", "normal", "-o", "remember_window_size=no", "--class", "kitty", "--title", title, "sh", "-c", "sleep 180"], env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    wait(lambda value: sum(window["title"].startswith("ForgeTaskbar-") for window in value["windows"]) == 2)
    activate_title("ForgeTaskbar-A")
    ipc("forgeTasks", "pinAction", "kitty")
    wait(lambda value: any(window["title"] == "ForgeTaskbar-B" and window["active"] for window in value["windows"]))
    ipc("forgeTasks", "pinAction", "kitty")
    wait(lambda value: any(window["title"] == "ForgeTaskbar-A" and window["active"] for window in value["windows"]))
    configure("--pin", "org.example.ForgeTaskbar")
    wait(lambda value: "org.example.forgetaskbar" in value["pins"])
    configure("--unpin", "org.example.ForgeTaskbar")
    wait(lambda value: "org.example.forgetaskbar" not in value["pins"])
    configure("--set", '{"showTitles":false,"primaryOnly":true,"currentMonitorOnly":true}')
    wait(lambda value: not value["showTitles"] and value["primaryOnly"] and value["currentMonitorOnly"])
    configure("--set", '{"enabled":false}')
    wait(lambda value: all(not bar["visible"] for bar in value["bars"]))
    time.sleep(0.3)
    assert bottom_reserved() == 0
    configure("--set", '{"enabled":true}')
    wait(lambda value: all(bar["visible"] for bar in value["bars"]))
    activate_title("ForgeTaskbar-A")
    ctl("dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen"})')
    wait(lambda value: any(window["title"] == "ForgeTaskbar-A" and window["fullscreen"] for window in value["windows"]) and all(not bar["visible"] for bar in value["bars"]))
    used = {workspace["id"] for workspace in json.loads(ctl("-j", "workspaces"))}
    other_workspace = next(index for index in range(901, 921) if index not in used)
    ctl("dispatch", "hl.dsp.focus({workspace=" + str(other_workspace) + "})")
    wait(lambda value: all(bar["visible"] for bar in value["bars"]))
    activate_title("ForgeTaskbar-A")
    wait(lambda value: all(not bar["visible"] for bar in value["bars"]))
    ctl("dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen"})')
    wait(lambda value: all(not window["fullscreen"] for window in value["windows"]) and all(bar["visible"] for bar in value["bars"]))
    ipc("forge", "taskbar")
    for _ in range(40):
        state = json.loads(ipc("forge", "status"))
        if state["settings"] and state["settingsPage"] == 2:
            break
        time.sleep(0.1)
    assert state["settings"] and state["settingsPage"] == 2
    ipc("forge", "close")
    configure("--set", '{"showTitles":true}')
    ipc("forgeTasks", "undo")
    wait(lambda value: not value["busy"] and value["transaction"] == "" and not value["showTitles"])
    transactions.pop()
    assert extra_output not in {monitor["name"] for monitor in json.loads(ctl("-j", "monitors", "all"))}
    assert ctl("output", "create", "headless", extra_output) == "ok"
    output_created = True
    wait(lambda value: len(value["bars"]) == 2 and sum(bar["visible"] for bar in value["bars"]) == 1)
    configure("--set", '{"primaryOnly":false}')
    wait(lambda value: len(value["bars"]) == 2 and all(bar["visible"] for bar in value["bars"]))
    assert ctl("output", "remove", extra_output) == "ok"
    output_created = False
    wait(lambda value: len(value["bars"]) == 1 and value["bars"][0]["visible"])
    print(json.dumps({"real_window_tracking": True, "window_activation": True, "pin_focus_cycles_windows": True, "pin_add_remove": True, "live_preferences": True, "reserved_space": True, "fullscreen_hide_restore": True, "taskbar_settings": True, "ui_writer_and_undo": True, "fullscreen_workspace_switch": True, "dual_monitor_hotplug": True}))
finally:
    ipc("forge", "close")
    if output_created:
        ctl("output", "remove", extra_output)
    for process in processes:
        process.terminate()
        process.wait(timeout=10)
    if original_workspace is not None:
        ctl("dispatch", "hl.dsp.focus({workspace=" + str(original_workspace) + "})")
    with lock(home / ".local/state/hyprland-forge"):
        for transaction in reversed(transactions):
            assert not restore(transaction, home, home / STATE)
    for pid in idle:
        os.kill(int(pid), signal.SIGCONT)
