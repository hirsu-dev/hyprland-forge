import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from .control import GAME, load
from .hardware import virtualization
from .manifest import ForgeError
from .storage import atomic_write, safe_target


def process_start(pid, proc=Path("/proc")):
    return (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]


def active_games(home, proc=Path("/proc")):
    root = home / ".local/state/hyprland-forge/games"
    safe_target(home, ".local/state/hyprland-forge/games/check.json")
    for path in list(root.glob("*.json"))[:256]:
        try:
            safe_target(home, path.relative_to(home).as_posix())
            if path.stat().st_size > 1024:
                continue
            value = json.loads(path.read_text())
            pid = value.get("pid")
            if type(pid) is int and pid > 0 and value.get("start") == process_start(pid, proc):
                return True
        except (ForgeError, OSError, ValueError, IndexError, AttributeError):
            continue
    return False


def command(arguments, options, virtual=False, available=shutil.which):
    if not arguments or any(not isinstance(argument, str) or "\x00" in argument for argument in arguments):
        raise ForgeError("Choose a game executable")
    result = list(arguments)
    if options["overlay"]:
        if not available("mangohud"):
            raise ForgeError("Install MangoHud before enabling its overlay")
        result = ["mangohud", "--dlsym", *result]
    if options["gamescope"]:
        if not available("gamescope"):
            raise ForgeError("Install Gamescope before enabling it")
        result = ["gamescope", "-w", str(options["width"]), "-h", str(options["height"]), "-r", str(options["fps"]), "-f", "--", *result]
    if not virtual:
        result = ["gamemoderun", *result]
        if available("prime-run") and available("nvidia-smi"):
            result = ["prime-run", *result]
    return ["systemd-inhibit", "--no-ask-password", "--what=idle", "--mode=block", "--why=Forge gaming session", *result]


def main(argv=None):
    process = None
    marker = None
    try:
        if sys.platform != "linux" or os.geteuid() == 0:
            raise ForgeError("Game launch requires a normal Linux desktop session")
        home = Path.home()
        options = load(home).get("gameOptions", GAME)
        virtual = virtualization()
        if virtual is None:
            raise ForgeError("Cannot verify the gaming environment")
        arguments = command(list(sys.argv[1:] if argv is None else argv), options, bool(virtual))
        marker = safe_target(home, ".local/state/hyprland-forge/games/" + str(os.getpid()) + ".json")
        atomic_write(marker, json.dumps({"pid": os.getpid(), "start": process_start(os.getpid())}).encode(), 0o600)
        process = subprocess.Popen(arguments, start_new_session=True)
        def stop(signum, frame):
            if process.poll() is None:
                os.killpg(process.pid, signum)
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, stop)
        return process.wait()
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Forge game: " + str(exc), file=sys.stderr)
        return 1
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        if marker:
            marker.unlink(missing_ok=True)
