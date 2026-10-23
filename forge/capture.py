import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from .manifest import ForgeError
from .storage import safe_target


def destination(home, recording=False):
    relative = ("Videos/Forge/" if recording else "Pictures/Forge/") + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6] + (".mp4" if recording else ".png")
    path = safe_target(home, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def geometry(mode, runner=subprocess.run):
    if mode == "region":
        result = runner(["slurp"], text=True, capture_output=True, timeout=120)
        if result.returncode:
            return None
        value = result.stdout.strip()
        if not re.fullmatch(r"-?\d+,-?\d+ [1-9]\d*x[1-9]\d*", value):
            raise ForgeError("Invalid capture region")
        return ["-g", value]
    if mode == "display":
        result = runner(["hyprctl", "-j", "monitors"], text=True, capture_output=True, check=True, timeout=5)
        selected = next((item for item in json.loads(result.stdout) if item.get("focused")), None)
        if not selected or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", selected.get("name", "")):
            raise ForgeError("No focused display")
        return ["-o", selected["name"]]
    if mode == "desktop":
        return []
    raise ForgeError("Invalid capture mode")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-capture")
    parser.add_argument("--mode", choices=("region", "display", "desktop"), default="region")
    parser.add_argument("--delay", type=int, choices=(0, 3, 5, 10), default=0)
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "linux" or os.geteuid() == 0:
            raise ForgeError("Capture requires a normal Linux desktop session")
        if args.record and (args.annotate or args.mode == "desktop"):
            raise ForgeError("Record a region or a display")
        area = geometry(args.mode)
        if area is None:
            print(json.dumps({"cancelled": True}))
            return 0
        time.sleep(args.delay + 0.25)
        output = destination(Path.home(), args.record)
        if args.record:
            command = ["wf-recorder", "--no-dmabuf", "--no-damage", "-r", "30", *area, "-f", str(output)]
            if args.audio:
                command.append("--audio")
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            previous = {}
            deadline = None
            def stop(signum, frame):
                nonlocal deadline
                if deadline is None:
                    deadline = time.monotonic() + 10
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
            try:
                for signum in (signal.SIGINT, signal.SIGTERM):
                    previous[signum] = signal.signal(signum, stop)
                while process.poll() is None:
                    try:
                        process.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        if deadline is not None and time.monotonic() >= deadline:
                            process.terminate()
                            raise ForgeError("Recorder did not finalize in time; the partial file was preserved")
                code = process.returncode
                if code not in (0, -signal.SIGINT):
                    raise ForgeError("Screen recorder failed; check compositor capture support")
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=10)
                for signum, handler in previous.items():
                    signal.signal(signum, handler)
        else:
            subprocess.run(["grim", *area, str(output)], check=True, timeout=15)
            subprocess.run(["wl-copy", "--type", "image/png"], input=output.read_bytes(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            if args.annotate:
                subprocess.run(["satty", "--filename", str(output), "--output-filename", str(output)], check=True)
                subprocess.run(["wl-copy", "--type", "image/png"], input=output.read_bytes(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
        if not output.exists() or output.stat().st_size == 0:
            raise ForgeError("Capture did not produce a file")
        print(json.dumps({"path": str(output), "recording": args.record}))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"cancelled": True}))
        return 0
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
