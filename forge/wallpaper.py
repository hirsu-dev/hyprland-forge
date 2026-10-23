import signal
import subprocess
import sys
import time
from pathlib import Path

from .control import load
from .manifest import ForgeError


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


def main():
    home = Path.home()
    process = None
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop)
    previous = None
    try:
        while running:
            try:
                current = command(home, load(home))
            except (OSError, ValueError, TypeError, ForgeError) as exc:
                print("Forge wallpaper: " + type(exc).__name__, file=sys.stderr)
                current = previous or command(home, {"wallpapers": {}})
            if current != previous or process is None or process.poll() is not None:
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                process = subprocess.Popen(current)
                previous = current
            time.sleep(2)
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    return 0
