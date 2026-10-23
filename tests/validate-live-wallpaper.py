import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.control import DEFAULTS
from forge.gaming import process_start
from forge.storage import write_json

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
root = Path(__file__).resolve().parent.parent


def wait(predicate):
    for _ in range(120):
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("Wallpaper lifecycle transition did not complete")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


with tempfile.TemporaryDirectory(prefix="forge-wallpaper-validation-") as directory:
    home = Path(directory)
    binary = home / "bin/linux-wallpaperengine"
    binary.parent.mkdir()
    shutil.copyfile(root / "tests/wallpaper-fixture", binary)
    binary.chmod(0o755)
    project = home / "workshop/test"
    project.mkdir(parents=True)
    write_json(project / "project.json", {"type": "scene", "title": "Synthetic lifecycle fixture, not a real wallpaper"})
    assets = home / "assets"
    assets.mkdir()
    log = home / "renderer.jsonl"
    target = home / ".config/forge/preferences.json"
    preferences = json.loads(json.dumps(DEFAULTS))
    preferences["liveWallpaper"].update(enabled=True, project=str(project), assets=str(assets), output="Virtual-1")
    write_json(target, preferences)
    env = {**os.environ, "HOME": str(home), "PATH": str(binary.parent) + os.pathsep + os.environ["PATH"], "PYTHONPATH": str(root), "FORGE_RENDER_LOG": str(log)}
    process = subprocess.Popen([sys.executable, "-c", "from forge.wallpaper import main; main()"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    records = lambda: [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    try:
        wait(lambda: len(records()) == 1)
        first = records()[0]
        assert "--silent" in first["arguments"] and "--no-fullscreen-pause" not in first["arguments"]
        marker = home / ".local/state/hyprland-forge/games/test.json"
        write_json(marker, {"pid": os.getpid(), "start": process_start(os.getpid())})
        wait(lambda: not alive(first["pid"]))
        marker.unlink()
        wait(lambda: len(records()) == 2)
        second = records()[1]
        preferences["gaming"] = True
        write_json(target, preferences)
        wait(lambda: not alive(second["pid"]))
        preferences["gaming"] = False
        write_json(target, preferences)
        wait(lambda: len(records()) == 3)
        third = records()[2]
        preferences["liveWallpaper"]["enabled"] = False
        write_json(target, preferences)
        wait(lambda: not alive(third["pid"]))
        assert process.poll() is None
        print(json.dumps({"fixture_only": True, "game_pause": True, "game_exit_restore": True, "preset_pause_restore": True, "disable_stops_renderer": True, "actual_Wallpaper_Engine_rendering": "not-tested-requires-owned-assets"}))
    finally:
        process.terminate()
        _, errors = process.communicate(timeout=10)
        assert process.returncode == 0, errors
