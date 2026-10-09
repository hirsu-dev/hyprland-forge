import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.diagnostics import collect
from forge.hardware import resolve_plan
from forge.manifest import load_manifest, make_plan

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
assert os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
root = Path(__file__).resolve().parent.parent
plan = resolve_plan(make_plan(load_manifest(root), None), apply=True, profile="virtual-machine")
assert "virtualbox-guest-utils" in plan["packages"]
assert "rtkit" in plan["packages"]
assert "vboxservice.service" in plan["services"]
assert not any(package.startswith("nvidia") for package in plan["packages"])
for attempt in range(10):
    report = collect()
    if report["runtime_ready"]:
        break
    time.sleep(1)
assert report["runtime_ready"], report["checks"]
assert report["validation_scope"] == "virtual-hardware-only"
assert not report["physical_hardware_qualified"]
assert report["checks"]["nvidia_dkms"]["status"] == "not-applicable"
assert report["checks"]["audio"]["status"] == "passed"
subprocess.run(["pw-play", "--raw", "--format", "s16", "--rate", "48000", "--channels", "2", "-"], input=bytes(48000 * 2 * 2), capture_output=True, check=True, timeout=10)
print(json.dumps({"checks": report["checks"], "vm_plan": "passed", "silent_audio_stream": "passed", "audible_playback": "requires-user-verification"}, indent=2))
