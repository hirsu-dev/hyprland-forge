import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forge.hardware import resolve_plan
from forge.manifest import load_manifest, make_plan
from forge.setup import with_gaming


assert "--arch-container" in sys.argv and Path("/.dockerenv").exists() and os.geteuid() == 0
root = Path(__file__).resolve().parent.parent
for gaming in (False, True):
    plan = resolve_plan(make_plan(load_manifest(root), None), profile="virtual-machine")
    if gaming:
        plan = with_gaming(plan, root)
    result = subprocess.run(["pacman", "-Sp", "--noconfirm", "--print-format", "%n", "--", *plan["packages"]], capture_output=True, text=True, check=True, timeout=120)
    packages = result.stdout.splitlines()
    assert packages and not any(name.startswith(("nvidia", "lib32-nvidia")) for name in packages), packages
    assert "vulkan-swrast" in packages, packages
    assert not gaming or "lib32-vulkan-swrast" in packages, packages
    print("VM package dependencies resolved without NVIDIA packages / gaming=" + str(gaming))
