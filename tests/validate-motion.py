import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.storage import atomic_write
from forge.theme import INTERFACE_DEFAULTS


config = sys.argv[1]
path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "forge/interface.json"
original = path.read_bytes()


def ipc(target, *args):
    return subprocess.check_output(["quickshell", "-p", config, "ipc", "call", target, *args], text=True, timeout=10).strip()


def wait(target, predicate):
    state = None
    for _ in range(80):
        state = json.loads(ipc(target, "status"))
        if predicate(state):
            return state
        time.sleep(0.05)
    raise AssertionError(state)


try:
    atomic_write(path, json.dumps({**INTERFACE_DEFAULTS, "speed": 0.5}).encode())
    wait("forge", lambda state: state["motion"])
    wait("forgeInterface", lambda state: state["values"]["speed"] == 0.5)
    for name, command in (("launcher", "launcher"), ("controls", "controls"), ("settings", "settings"), ("power", "power"), ("overview", "overview"), ("hub", "hub")):
        ipc("forge", "close")
        wait("forgeMotion", lambda states: not any(state["shown"] for state in states))
        before = next(state for state in json.loads(ipc("forgeMotion", "status")) if state["name"] == name)
        ipc("forge", command, *(["hardware"] if name == "hub" else []))
        opened = wait("forgeMotion", lambda states: any(state["name"] == name and state["opened"] and state["shown"] and state["reveal"] == 1 and not state["moving"] for state in states))
        opened = next(state for state in opened if state["name"] == name)
        assert opened["entryFrames"] > before["entryFrames"], opened
        ipc("forge", "close")
        assert not any(state["focusable"] for state in json.loads(ipc("forgeMotion", "status")))
        closed = wait("forgeMotion", lambda states: not any(state["shown"] or state["moving"] for state in states))
        closed = next(state for state in closed if state["name"] == name)
        assert closed["exitFrames"] > opened["exitFrames"], closed
    for _ in range(3):
        ipc("forge", "launcher")
        ipc("forge", "close")
        ipc("forge", "launcher")
    wait("forgeMotion", lambda states: any(state["name"] == "launcher" and state["reveal"] == 1 for state in states))
    ipc("forgeLauncher", "query", "> animation")
    wait("forgeLauncher", lambda state: state["actions"] and state["count"] == 1 and state["first"] == "Interface & motion")
    ipc("forgeLauncher", "activate")
    wait("forge", lambda state: state["settings"] and state["settingsPage"] == 1 and not state["launcher"])
    ipc("forge", "controls")
    before = json.loads(ipc("forgeCalendar", "status"))
    assert len(before["cells"]) == 42 and len({cell["key"] for cell in before["cells"]}) == 42, before
    first = before["cells"][0]
    from datetime import date
    assert date.fromisoformat(first["key"]).weekday() == 0, before
    ipc("forgeCalendar", "navigate", "1")
    after = wait("forgeCalendar", lambda state: not state["moving"])
    assert (after["year"] * 12 + after["month"]) - (before["year"] * 12 + before["month"]) == 1, after
    ipc("forgeCalendar", "choose", "18")
    chosen = json.loads(ipc("forgeCalendar", "status"))
    assert chosen["selected"] == after["cells"][18]["key"], chosen
    ipc("forgeCalendar", "today")
    atomic_write(path, json.dumps({**INTERFACE_DEFAULTS, "motion": False}).encode())
    wait("forge", lambda state: not state["motion"])
    ipc("forge", "close")
    wait("forgeMotion", lambda states: not any(state["shown"] or state["moving"] for state in states))
    ipc("forge", "launcher")
    wait("forgeMotion", lambda states: any(state["name"] == "launcher" and state["reveal"] == 1 and not state["moving"] for state in states))
    print("Six panel entry/exit curves, rapid reversal, immediate focus release, quick actions, calendar and reduced motion passed")
finally:
    ipc("forge", "close")
    atomic_write(path, original)
