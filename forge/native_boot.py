import hashlib
import json
import os
import secrets
import shutil
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path

from .boot import source_assets
from .manifest import ForgeError


SOURCES = ("Cargo.toml", "Cargo.lock", "src/lib.rs", "src/state.rs", "src/visual.rs", "src/main.rs", "src/preview.rs")
ROUNDS = 600000


def partition_id(value):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ForgeError("Use each EFI partition's GPT PARTUUID, not its FAT filesystem UUID") from exc
    if parsed.int == 0 or str(parsed) != value.lower():
        raise ForgeError("Use a canonical nonzero GPT PARTUUID")
    return parsed


def provisioning(password, forge_partuuid, windows_partuuid, salt=None):
    if not isinstance(password, str) or not 12 <= len(password) <= 128 or not password.isascii() or any(not 32 <= ord(c) <= 126 for c in password):
        raise ForgeError("Use a separate 12-128 character printable ASCII boot password")
    forge, windows = partition_id(forge_partuuid), partition_id(windows_partuuid)
    salt = secrets.token_bytes(32) if salt is None else salt
    if len(salt) != 32 or not any(salt):
        raise ForgeError("Invalid provisioning salt")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS, 32)
    return b"FGX1" + struct.pack("<I", ROUNDS) + forge.bytes_le + windows.bytes_le + salt + digest


def licenses(project, destination, runner):
    data = json.loads(runner(["cargo", "metadata", "--locked", "--format-version", "1"], cwd=project, check=True, capture_output=True, text=True).stdout)
    inventory = []
    for package in data["packages"]:
        if not package.get("source"):
            continue
        root = Path(package["manifest_path"]).parent
        files = [p for p in root.iterdir() if p.is_file() and not p.is_symlink() and p.name.lower().startswith(("license", "copying", "notice"))]
        if package.get("license_file"):
            candidate = root / package["license_file"]
            if candidate.is_symlink() or not candidate.resolve().is_relative_to(root.resolve()):
                raise ForgeError("Unsafe dependency license path")
            files.append(candidate)
        if not files:
            raise ForgeError("Missing dependency license: " + package["name"])
        target = destination / (package["name"] + "-" + package["version"])
        target.mkdir(parents=True)
        for path in set(files):
            shutil.copyfile(path, target / path.name)
        inventory.append({"name": package["name"], "version": package["version"], "license": package.get("license")})
    return inventory


def build(output, provision, runner=subprocess.run, telemetry=False):
    if len(provision) != 104 or provision[:4] != b"FGX1" or struct.unpack("<I", provision[4:8])[0] != ROUNDS or not all(any(provision[a:b]) for a,b in ((8,24),(24,40),(40,72),(72,104))):
        raise ForgeError("Invalid native boot provisioning")
    if not shutil.which("cargo"):
        raise ForgeError("Rust is required to compile this experimental boot application")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ForgeError("Choose a new output folder; existing files will not be replaced")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".forge-native-", dir=output.parent) as temporary:
        stage = Path(temporary)
        stage.chmod(0o700)
        project = stage / "source"
        project.mkdir()
        for name in SOURCES:
            source = source_assets() / "native" / name
            if source.is_symlink() or not source.is_file():
                raise ForgeError("Missing or unsafe native source: " + name)
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        config = stage / "provision.bin"
        config.write_bytes(provision)
        config.chmod(0o600)
        environment = {**os.environ, "FORGE_BOOT_CONFIG": str(config.resolve()), "CARGO_TARGET_DIR": str((stage / "compile").resolve())}
        try:
            runner(["cargo", "build", "--locked", "--release", "--target", "x86_64-unknown-uefi", "--features", "firmware-test" if telemetry else "firmware", "--bin", "forge-startup"], cwd=project, env=environment, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise ForgeError("Native build failed:\n" + (exc.stderr or "")[-8000:]) from exc
        dependencies = licenses(project, stage / "licenses", runner)
        efi = stage / "EFI/Forge/forge-startup-x64.efi"
        efi.parent.mkdir(parents=True)
        shutil.copyfile(stage / "compile/x86_64-unknown-uefi/release/forge-startup.efi", efi)
        efi.chmod(0o600)
        config.unlink()
        shutil.rmtree(stage / "compile")
        shutil.rmtree(project)
        (stage / "plan.json").write_text(json.dumps({"engine": "native-UEFI-experimental", "activation": "not-installed", "password": "PBKDF2-HMAC-SHA256-600000-constant-time-comparison", "partition_changes": False, "firmware_writes": False, "secure_boot": "unsigned-requires-separate-signing-and-review", "password_scope": "boot-menu-only-not-disk-encryption-or-OS-login", "telemetry": telemetry, "dependencies": dependencies, "sha256": hashlib.sha256(efi.read_bytes()).hexdigest()}, indent=2) + "\n", encoding="utf-8")
        os.rename(stage, output)
    return output
