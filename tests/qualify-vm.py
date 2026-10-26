import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--disposable-vm", action="store_true", required=True)
parser.add_argument("--suite", action="append", choices=("runtime", "apps", "desktop", "system", "appearance", "clipboard", "unit"))
args = parser.parse_args()
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
root = Path(__file__).resolve().parent.parent
output = root / "test-results/qualification"
output.mkdir(parents=True, exist_ok=True)
scripts = {"runtime": "validate-vm.py", "apps": "validate-everyday-vm.py", "desktop": "validate-desktop.py", "system": "validate-system-deck.py", "appearance": "validate-interface.py", "clipboard": "validate-clipboard.py"}
commands = {name: [[sys.executable, str(root / "tests" / script), "--disposable-vm"]] for name, script in scripts.items()}
commands["desktop"] += [[sys.executable, str(root / "tests" / name), "--disposable-vm"] for name in ("validate-monitor-memory.py", "validate-taskbar.py")]
commands["runtime"].append([sys.executable, str(root / "tests/validate-supervision-vm.py"), "--disposable-vm"])
commands["runtime"].append([sys.executable, str(root / "tests/validate-lock-vm.py"), "--disposable-vm"])
commands["appearance"].append([sys.executable, str(root / "tests/validate-motion.py"), str(Path.home() / ".config/quickshell/forge/shell.qml")])
commands["unit"] = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]]
build = json.loads((root / "build.json").read_text())
report = {"scope": "virtual-machine", "version": build["version"], "revision": build["revision"], "kernel": os.uname().release, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "packages": subprocess.check_output(["pacman", "-Q", "hyprland", "quickshell", "mesa", "vulkan-swrast"], text=True).splitlines(), "started": time.time(), "checks": [], "physical_hardware_qualified": False, "result": "running"}
try:
    for suite in args.suite or ("runtime", "apps", "system", "desktop", "appearance", "clipboard", "unit"):
        for index, command in enumerate(commands[suite]):
            log = output / (suite + "-" + str(index) + ".log")
            with log.open("w") as stream:
                result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=240)
            report["checks"].append({"suite": suite, "script": Path(command[1]).name, "exit_code": result.returncode, "log": log.name, "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
            print(suite + " / " + ("passed" if result.returncode == 0 else "failed"), flush=True)
            if result.returncode:
                raise RuntimeError(log.read_text(errors="replace")[-4000:])
    report["result"] = "passed"
finally:
    report["finished"] = time.time()
    if report["result"] == "running":
        report["result"] = "failed"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
