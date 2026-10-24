import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--disposable-vm", action="store_true", required=True)
parser.add_argument("--seconds", type=int, default=300)
args = parser.parse_args()
assert 60 <= args.seconds <= 1800
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
source = Path(__file__).resolve().parent.parent
output = source / "test-results/qualification"
output.mkdir(parents=True, exist_ok=True)
processes = []
classes = {"firefox", "thunar", "mpv"}
report = {"scope": "virtual-machine", "seconds_requested": args.seconds, "samples": [], "physical_hardware_qualified": False, "result": "running"}


def clients():
    return json.loads(subprocess.check_output(["hyprctl", "-j", "clients"], text=True, timeout=5))


def stop_apps():
    for item in clients():
        if (item["address"], item["pid"]) not in baseline and item.get("class", "").lower() in classes:
            subprocess.run(["hyprctl", "dispatch", "hl.dsp.window.close({window=" + json.dumps("address:" + item["address"]) + "})"], capture_output=True, timeout=5)
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


baseline = {(item["address"], item["pid"]) for item in clients()}
try:
    with tempfile.TemporaryDirectory(prefix="forge-session-vm-") as directory:
        root = Path(directory)
        profile = root / "browser"
        profile.mkdir()
        (profile / "user.js").write_text('user_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.aboutwelcome.enabled", false);\nuser_pref("browser.startup.homepage_override.mstone", "ignore");\n')
        page = root / "session.html"
        page.write_text('<!doctype html><title>Forge Session Validation</title><style>body{background:#100d16;color:#fcee0a;font:24px sans-serif;padding:30px}</style><h1>Forge Session Validation</h1><p>Browser, files and video running together.</p>')
        movie = root / "session.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30", "-t", "3", "-c:v", "mpeg4", str(movie)], check=True, timeout=20)
        with (output / "soak-apps.log").open("w") as errors:
            for command in (["thunar", str(root)], ["mpv", "--loop-file=inf", str(movie)], ["firefox", "--no-remote", "--profile", str(profile), "--new-window", page.as_uri()]):
                processes.append(subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True))
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                present = {item.get("class", "").lower() for item in clients() if (item["address"], item["pid"]) not in baseline}
                if classes <= present:
                    break
                time.sleep(0.2)
            else:
                raise AssertionError({"missing_apps": sorted(classes - present)})
            started = time.monotonic()
            recovered = False
            while time.monotonic() - started < args.seconds:
                present = {item.get("class", "").lower() for item in clients() if (item["address"], item["pid"]) not in baseline}
                assert classes <= present, present
                state = json.loads((Path(os.environ["XDG_RUNTIME_DIR"]) / "hyprland-forge-session.json").read_text())
                assert state["running"] and time.time() - state["updated"] < 20 and len(state["components"]) == 5 and all(item["running"] for item in state["components"]), state
                errors_found = json.loads(subprocess.check_output(["hyprctl", "-j", "configerrors"], text=True, timeout=5))
                assert not [error for error in errors_found if error.strip()], errors_found
                available = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
                elapsed = time.monotonic() - started
                report["samples"].append({"seconds": round(elapsed, 1), "memory_available_kib": available, "applications": sorted(present)})
                if elapsed >= args.seconds / 2 and not recovered:
                    subprocess.run([sys.executable, str(source / "tests/validate-supervision-vm.py"), "--disposable-vm"], stdout=errors, stderr=subprocess.STDOUT, check=True, timeout=60)
                    recovered = True
                time.sleep(min(15, max(0, args.seconds - (time.monotonic() - started))))
            screenshot = output / "multitasking.png"
            subprocess.run(["grim", str(screenshot)], check=True, capture_output=True, timeout=15)
            report.update(result="passed", seconds_observed=round(time.monotonic() - started, 1), recovery_during_multitasking=recovered, minimum_memory_available_kib=min(sample["memory_available_kib"] for sample in report["samples"]))
            stop_apps()
finally:
    stop_apps()
    if report["result"] == "running":
        report["result"] = "failed"
    (output / "soak.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
