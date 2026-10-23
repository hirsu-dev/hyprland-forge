import json
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .control import load
from .manifest import ForgeError
from .gaming import active_games


def command(home, preferences):
    images = preferences["wallpapers"]
    default = images.get("default", str(home / ".local/share/backgrounds/forge.svg"))
    result = ["swaybg", "--color", "#100d16"]
    if Path(default).is_file():
        result += ["--image", default, "--mode", "fill"]
    for name, path in images.items():
        if name != "default" and Path(path).is_file():
            result += ["--output", name, "--image", path, "--mode", "fill"]
    return result


def validate_project(value):
    project = Path(value["project"])
    assets = Path(value["assets"])
    metadata = project / "project.json"
    if not project.is_dir() or not assets.is_dir() or not metadata.is_file() or metadata.stat().st_size > 131072:
        raise ForgeError("Choose a downloaded Wallpaper Engine project and its Steam assets folder")
    data = json.loads(metadata.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or str(data.get("type", "")).lower() not in ("scene", "video", "web"):
        raise ForgeError("Only scene, video and web wallpapers are accepted; executable wallpapers are blocked")
    return data


def renderer_status(available=shutil.which):
    path = available("linux-wallpaperengine")
    return {"installed": path is not None, "binary": path or "", "implementation": "community-linux-wallpaperengine", "requiresSteamAssets": True}


def library(home):
    roots = [home / ".local/share/Steam", home / ".steam/steam", home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
    for root in roots[:]:
        path = root / "steamapps/libraryfolders.vdf"
        if path.is_file() and path.stat().st_size < 1048576:
            roots.extend(Path(value.replace("\\\\", "\\")) for value in re.findall(r'"path"\s*"((?:\\.|[^"\\])*)"', path.read_text(errors="replace")) if value.startswith("/"))
    roots = list(dict.fromkeys(root.resolve() for root in roots))[:16]
    assets, projects = [], []
    for root in roots:
        manifest = root / "steamapps/appmanifest_431960.acf"
        directory = "wallpaper_engine"
        if manifest.is_file() and manifest.stat().st_size < 1048576:
            match = re.search(r'"installdir"\s*"([^"\\/]+)"', manifest.read_text(errors="replace"))
            if match and match[1] not in (".", ".."):
                directory = match[1]
        asset = root / "steamapps/common" / directory / "assets"
        if asset.is_dir():
            assets.append(str(asset))
        for metadata in sorted((root / "steamapps/workshop/content/431960").glob("*/project.json"))[:1000]:
            try:
                if metadata.stat().st_size > 131072:
                    continue
                data = json.loads(metadata.read_text(encoding="utf-8-sig"))
                kind = str(data.get("type", "")).lower()
                if kind in ("scene", "video", "web"):
                    projects.append({"path": str(metadata.parent), "title": str(data.get("title", metadata.parent.name))[:128], "type": kind})
            except (OSError, ValueError, AttributeError):
                continue
    return {"wallpaperAssets": assets, "wallpaperProjects": projects[:1000], "wallpaperRenderer": renderer_status()}


def live_command(value, output, available=shutil.which):
    validate_project(value)
    executable = available("linux-wallpaperengine")
    if not executable:
        raise ForgeError("Install the optional Linux Wallpaper Engine renderer first")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", output):
        raise ForgeError("Invalid live output")
    result = [executable, "--assets-dir", value["assets"], "--fps", str(value["fps"]), "--disable-mouse", "--disable-parallax", "--screen-root", output, "--bg", value["project"]]
    if value["silent"]:
        result += ["--silent", "--no-audio-processing"]
    return result


def monitor_names(runner=subprocess.run):
    result = runner(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=3, check=True)
    values = json.loads(result.stdout)
    names = [item["name"] for item in values if not item.get("disabled") and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", item.get("name", ""))]
    if not names:
        raise ForgeError("No live wallpaper output is connected")
    return names


def static_other(home, preferences, names):
    if not names:
        return None
    result = ["swaybg"]
    default = preferences["wallpapers"].get("default", str(home / ".local/share/backgrounds/forge.svg"))
    for name in names:
        path = preferences["wallpapers"].get(name, default)
        result += ["--output", name, "--color", "#100d16"]
        if Path(path).is_file():
            result += ["--image", path, "--mode", "fill"]
    return result


def stop_process(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    home = Path.home()
    process = None
    engine = None
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop)
    previous = None
    retry_after = 0
    last_error = ""
    try:
        while running:
            try:
                preferences = load(home)
                live = preferences["liveWallpaper"]
                current = command(home, preferences)
                animated = None
                if engine and engine.poll() is not None:
                    retry_after = time.monotonic() + 60
                    engine = None
                    previous = None
                paused = live["pauseOnGaming"] and (preferences["gaming"] or active_games(home))
                if live["enabled"] and not paused and time.monotonic() >= retry_after:
                    names = monitor_names()
                    output = live["output"]
                    if output == "primary":
                        from .desktop_settings import saved_settings
                        preferred = saved_settings(home).get("primary")
                        output = preferred if preferred in names else next((name for name in names if name.startswith("HDMI")), names[0])
                    if output in names:
                        animated = live_command(live, output)
                        current = static_other(home, preferences, [name for name in names if name != output])
                signature = (current, animated)
                if signature != previous or current and (process is None or process.poll() is not None):
                    stop_process(engine)
                    stop_process(process)
                    process = subprocess.Popen(current) if current else None
                    engine = subprocess.Popen(animated) if animated else None
                    previous = signature
                last_error = ""
            except (OSError, ValueError, TypeError, ForgeError, subprocess.SubprocessError) as exc:
                if str(exc) != last_error:
                    print("Forge wallpaper: " + str(exc), file=sys.stderr)
                    last_error = str(exc)
                stop_process(engine)
                engine = None
                fallback = command(home, {"wallpapers": {}})
                if previous != ("fallback", fallback) or process is None or process.poll() is not None:
                    stop_process(process)
                    process = subprocess.Popen(fallback)
                previous = ("fallback", fallback)
            time.sleep(2)
    finally:
        stop_process(engine)
        stop_process(process)
    return 0
