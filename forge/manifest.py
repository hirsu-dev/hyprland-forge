import json
import re
from pathlib import Path, PurePosixPath


class ForgeError(Exception):
    pass


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ForgeError(f"Invalid relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in (".", "..") for p in value.split("/")):
        raise ForgeError(f"Unsafe relative path: {value}")
    return path


def load_manifest(root):
    data = json.loads((root / "project.json").read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ForgeError("Unsupported project schema")
    stages = data.get("stages", [])
    if not stages or len({s["id"] for s in stages}) != len(stages):
        raise ForgeError("Invalid stage list")
    known = set()
    targets = set()
    for stage in stages:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", stage["id"]):
            raise ForgeError("Invalid stage identifier")
        if not set(stage.get("requires", [])) <= known:
            raise ForgeError(f"Invalid dependency order: {stage['id']}")
        known.add(stage["id"])
        if stage.get("status") not in ("ready", "pending"):
            raise ForgeError("Invalid stage status")
        for package in stage.get("packages", []):
            if not re.fullmatch(r"[a-z0-9][a-z0-9@+_.-]*", package):
                raise ForgeError(f"Invalid package name: {package}")
        for item in stage.get("files", []):
            source = relative_path(item["source"])
            target = relative_path(item["target"])
            if source.parts[0] not in ("configs", "forge"):
                raise ForgeError("Source must be inside configs/ or forge/")
            if target.parts[0] not in (".config", ".local") or len(target.parts) < 2:
                raise ForgeError("Config destination must be inside .config/ or .local/")
            if str(target) in targets:
                raise ForgeError(f"Duplicate config destination: {target}")
            targets.add(str(target))
            candidate = (root / source).resolve()
            if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
                raise ForgeError(f"Missing or unsafe config: {source}")
    return data


def select_stages(manifest, requested):
    stages = {s["id"]: s for s in manifest["stages"]}
    selected = set()

    def add(name):
        if name not in stages:
            raise ForgeError(f"Unknown stage: {name}")
        stage = stages[name]
        if stage["status"] != "ready":
            raise ForgeError(f"Stage {name} is not released yet")
        if name in selected:
            return
        for dependency in stage.get("requires", []):
            add(dependency)
        selected.add(name)

    names = requested or [s["id"] for s in stages.values() if s["status"] == "ready"]
    for name in names:
        add(name)
    return [s for s in stages.values() if s["id"] in selected]


def make_plan(manifest, requested):
    stages = select_stages(manifest, requested)
    packages = list(dict.fromkeys(p for s in stages for p in s.get("packages", [])))
    return {
        "project": manifest["name"],
        "release": manifest["release"],
        "stages": [s["id"] for s in stages],
        "packages": packages,
        "files": [f for s in stages for f in s.get("files", [])],
        "commands": [["sudo", "pacman", "-Syu", "--needed", "--", *packages]] if packages else [],
        "pending": [s["id"] for s in manifest["stages"] if s["status"] != "ready"],
    }
