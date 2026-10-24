import os
import subprocess
from pathlib import Path

from PIL import Image

from forge.native_boot import build, provisioning


root = Path("test-results/native-startup").resolve()
root.mkdir(parents=True, exist_ok=True)
project = Path("configs/boot/native").resolve()
subprocess.run(["cargo", "test", "--locked", "--release", "--lib"], cwd=project, check=True)
subprocess.run(["cargo", "run", "--locked", "--release", "--features", "preview", "--bin", "forge-preview", "--", str(root / "preview")], cwd=project, check=True)
frames = []
for path in sorted((root / "preview").glob("*.ppm")):
    with Image.open(path) as image:
        image.save(path.with_suffix(".png"))
        if path.name.startswith("intro-"):
            frames.append(image.convert("RGB"))
    path.unlink()
frames[0].save(root / "intro.gif", save_all=True, append_images=frames[1:], duration=40, loop=0)
config = provisioning("fixture-password-123", "11111111-2222-4333-8444-555555555555", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
output = build(root / "private-fixture", config, telemetry=True)
assert (output / "EFI/Forge/forge-startup-x64.efi").read_bytes().startswith(b"MZ")
assert not (output / "provision.bin").exists()
production = build(root / "private-production", config)
assert b"FORGE:SELECTOR" not in (production / "EFI/Forge/forge-startup-x64.efi").read_bytes()
assert not __import__("json").loads((production / "plan.json").read_text())["telemetry"]
print("Native Rust unit, rendering, firmware build and dependency-license capture passed")
