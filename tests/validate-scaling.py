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
path = Path(os.environ["XDG_CONFIG_HOME"]) / "forge/interface.json"
original = path.read_bytes()
screenshots = Path("test-results")


def ipc(target, *args):
    return subprocess.check_output(["quickshell", "-p", config, "ipc", "call", target, *args], text=True, timeout=10).strip()


def wait(predicate):
    state = None
    for _ in range(60):
        state = json.loads(ipc("forgeInterface", "status"))
        if predicate(state):
            return state
        time.sleep(0.1)
    raise AssertionError(state)


try:
    for scale in (0.75, 1, 1.25, 1.75):
        value = {**INTERFACE_DEFAULTS, "scale": scale, "textScale": 1.25, "spacing": 1.6, "jaggedness": 2, "intensity": 1}
        atomic_write(path, json.dumps(value).encode())
        wait(lambda state: state["values"]["scale"] == scale and state["values"]["spacing"] == 1.6)
        ipc("forge", "appearance")
        state = wait(lambda state: state["open"] and state["viewportWidth"] > 100 and state["viewportHeight"] > 20 and state["animationsActive"])
        assert state["width"] > 300 and state["height"] > 150, state
        assert state["viewportWidth"] <= state["width"] and state["viewportHeight"] <= state["height"], state
        if os.environ.get("QT_QPA_PLATFORM") == "wayland":
            time.sleep(0.4)
            subprocess.run(["grim", "-o", "HEADLESS-1", str(screenshots / ("interface-scale-" + str(scale) + ".png"))], check=True, timeout=10)
        ipc("forge", "close")
        wait(lambda state: not state["open"] and not state["animationsActive"])
    atomic_write(path, json.dumps({**INTERFACE_DEFAULTS, "motion": False}).encode())
    wait(lambda state: not state["values"]["motion"])
    ipc("forge", "appearance")
    wait(lambda state: state["open"] and not state["animationsActive"])
    print("UI scales 75-175%, text, density, jaggedness, visible motion, hidden suspension and reduced motion passed")
finally:
    ipc("forge", "close")
    atomic_write(path, original)
