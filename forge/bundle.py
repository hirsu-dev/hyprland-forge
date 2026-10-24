import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .manifest import ForgeError, load_manifest, relative_path


def build_bundle(root, destination, revision):
    manifest = load_manifest(root)
    if not re.fullmatch(r"[a-z][a-z0-9-]*", manifest["name"]) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["release"]) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ForgeError("Invalid bundle identity")
    if not all(stage["status"] == "ready" for stage in manifest["stages"]):
        raise ForgeError("All modules must be released before packaging")
    paths = {"install.sh", "install-online.sh", "live.sh", "project.json"}
    paths.update(str(path.relative_to(root)).replace("\\", "/") for path in (root / "forge").glob("*.py"))
    paths.update(item["source"] for stage in manifest["stages"] for item in stage.get("files", []))
    payloads = {}
    for name in sorted(paths):
        source = root / relative_path(name)
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()) or not source.is_file():
            raise ForgeError("Unsafe bundle source: " + name)
        content = source.read_bytes()
        if source.suffix.lower() in (".sh", ".py", ".json", ".qml", ".conf", ".ini", ".lua", ".svg", ".desktop", ".rs", ".toml", ".lock") or name.startswith("configs/bin/") or source.name in ("config", "qmldir"):
            content = content.replace(b"\r\n", b"\n")
        payloads[name] = content
    payloads["build.json"] = (json.dumps({"name": manifest["name"], "version": manifest["release"], "revision": revision, "hardware_validation": "pending-on-device"}, indent=2) + "\n").encode()
    payloads["SHA256SUMS"] = "".join(hashlib.sha256(content).hexdigest() + "  " + name + "\n" for name, content in sorted(payloads.items())).encode()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / (manifest["name"] + "-" + manifest["release"] + ".tar.gz")
    descriptor, temporary = tempfile.mkstemp(prefix=".forge-bundle-", dir=destination)
    try:
        with os.fdopen(descriptor, "wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for name, content in sorted(payloads.items()):
                        entry = tarfile.TarInfo(manifest["name"] + "/" + name)
                        entry.size = len(content)
                        entry.mode = 0o644
                        entry.mtime = 0
                        archive.addfile(entry, io.BytesIO(content))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (destination / (target.name + ".sha256")).write_text(checksum + "  " + target.name + "\n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(prog="forge-bundle")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        if subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True).stdout.strip():
            raise ForgeError("Commit and verify changes before packaging")
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        print(build_bundle(root, args.output.resolve(), revision))
        return 0
    except (ForgeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("Forge bundle: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
