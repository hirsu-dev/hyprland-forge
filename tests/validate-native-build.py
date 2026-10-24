import os
import subprocess
from pathlib import Path

from PIL import Image

from forge.native_boot import build, preview, provisioning


root = Path("test-results/native-startup").resolve()
root.mkdir(parents=True, exist_ok=True)
project = Path("configs/boot/native").resolve()
subprocess.run(["cargo", "test", "--locked", "--release", "--lib"], cwd=project, check=True)
preview(root / "preview")
__import__("shutil").copyfile(root / "preview/intro.gif", root / "intro.gif")
config = provisioning("fixture-password-123", "11111111-2222-4333-8444-555555555555", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
output = build(root / "private-fixture", config, telemetry=True)
assert (output / "EFI/Forge/forge-startup-x64.efi").read_bytes().startswith(b"MZ")
assert not (output / "provision.bin").exists()
production = build(root / "private-production", config)
assert b"FORGE:SELECTOR" not in (production / "EFI/Forge/forge-startup-x64.efi").read_bytes()
assert not __import__("json").loads((production / "plan.json").read_text())["telemetry"]
print("Native Rust unit, rendering, firmware build and dependency-license capture passed")
