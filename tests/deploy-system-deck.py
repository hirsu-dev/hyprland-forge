import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.manifest import load_manifest, make_plan
from forge.hardware import resolve_plan
from forge.runtime import execute, lock

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0
root = Path(__file__).resolve().parent.parent
home = Path.home()
plan = resolve_plan(make_plan(load_manifest(root), []), profile="virtual-machine")
plan["commands"] = []
plan["services"] = []
plan.pop("default_target", None)
plan.pop("login", None)
with lock(home / ".local/state/hyprland-forge"):
    print(execute(plan, root, home, home / ".local/state/hyprland-forge"))
