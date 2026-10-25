import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import VERSION
from .manifest import ForgeError, relative_path
from .runtime import preflight


REPOSITORY = "hrushikbarani-hub/hyprland-forge"
API = "https://api.github.com/repos/" + REPOSITORY + "/releases?per_page=100"
MAX_ARCHIVE = 32 * 1024 ** 2


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", value):
        raise ForgeError("Invalid Forge release version")
    return tuple(map(int, value.split(".")))


def select_release(items, channel="recommended"):
    if channel not in ("recommended", "stable", "preview") or not isinstance(items, list):
        raise ForgeError("Invalid release channel or metadata")
    candidates = []
    for item in items:
        if not isinstance(item, dict) or item.get("draft") is not False or type(item.get("prerelease")) is not bool:
            continue
        tag = item.get("tag_name", "")
        if not isinstance(tag, str) or not re.fullmatch(r"v[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", tag):
            continue
        candidates.append(item)
    stable = [item for item in candidates if not item["prerelease"]]
    pool = stable if channel == "stable" or channel == "recommended" and stable else candidates
    if not pool:
        raise ForgeError("No verified release is available for this channel")
    selected = max(pool, key=lambda item: version(item["tag_name"][1:]))
    tag = selected["tag_name"]
    name = "hyprland-forge-" + tag[1:] + ".tar.gz"
    assets = selected.get("assets")
    if not isinstance(assets, list):
        raise ForgeError("Release assets are unavailable")
    assets = [item for item in assets if isinstance(item, dict) and item.get("name") == name]
    if len(assets) != 1 or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(assets[0].get("digest", ""))):
        raise ForgeError("Release checksum is unavailable")
    return {"version": tag[1:], "tag": tag, "prerelease": selected["prerelease"], "sha256": assets[0]["digest"][7:], "url": "https://github.com/" + REPOSITORY + "/releases/download/" + tag + "/" + name}


def read_url(url, maximum, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Hyprland-Forge/" + VERSION})
    try:
        with opener(request, timeout=20) as response:
            value = response.read(maximum + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise ForgeError("Release server unavailable; retry when connected") from exc
    if len(value) > maximum:
        raise ForgeError("Release download exceeds the size limit")
    return value


def latest(channel="recommended", reader=read_url):
    try:
        return select_release(json.loads(reader(API, 2 * 1024 ** 2)), channel)
    except (ValueError, UnicodeError) as exc:
        raise ForgeError("Release server returned invalid metadata") from exc


def release_status(selected, channel="recommended"):
    return {"installed": VERSION, "available": selected["version"], "updateAvailable": version(selected["version"]) > version(VERSION), "prerelease": selected["prerelease"], "channel": channel}


def status(channel="recommended", reader=read_url):
    return release_status(latest(channel, reader), channel)


def unpack_release(selected, directory, reader=read_url):
    content = reader(selected["url"], MAX_ARCHIVE)
    if hashlib.sha256(content).hexdigest() != selected["sha256"]:
        raise ForgeError("Release checksum verification failed")
    archive = directory / "release.tar.gz"
    archive.write_bytes(content)
    target = directory / "unpacked"
    try:
        with tarfile.open(archive, "r:gz") as source:
            members = []
            names = set()
            total = 0
            for member in source:
                path = relative_path(member.name)
                total += member.size
                if not member.isfile() or str(path) != member.name or path.parts[0] != "hyprland-forge" or len(path.parts) < 2 or member.name in names or len(members) >= 1024 or total > MAX_ARCHIVE:
                    raise ForgeError("Unsafe release archive")
                names.add(member.name)
                members.append(member)
            source.extractall(target, members=members, filter="data")
        root = target / "hyprland-forge"
        checks = {}
        for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, name = line.split("  ", 1)
            path = relative_path(name)
            if str(path) != name or name in checks or not re.fullmatch(r"[0-9a-f]{64}", expected) or hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
                raise ForgeError("Release file integrity verification failed")
            checks[name] = expected
        if names != {"hyprland-forge/" + name for name in (*checks, "SHA256SUMS")}:
            raise ForgeError("Release contains unchecked files")
        build = json.loads((root / "build.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "project.json").read_text(encoding="utf-8"))
        if not isinstance(build, dict) or not isinstance(manifest, dict) or build.get("version") != selected["version"] or manifest.get("release") != selected["version"] or not re.fullmatch(r"[0-9a-f]{40}", str(build.get("revision", ""))) or not (root / "install.sh").is_file():
            raise ForgeError("Release identity does not match its download")
        return root
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        raise ForgeError("Release archive failed validation") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-update desktop")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--channel", choices=("recommended", "stable", "preview"), default="recommended")
    args = parser.parse_args(argv)
    try:
        if args.apply:
            preflight()
            if not sys.stdin.isatty():
                raise ForgeError("Desktop updates require an interactive terminal")
        selected = latest(args.channel)
        if not args.apply:
            print(json.dumps(release_status(selected, args.channel), indent=2))
            return 0
        if version(selected["version"]) <= version(VERSION):
            print("Forge " + VERSION + " is current for this channel.")
            return 0
        print("Forge " + selected["version"] + (" / prerelease" if selected["prerelease"] else " / stable"))
        print("Your interface, theme, taskbar and personal overrides will be kept.")
        with tempfile.TemporaryDirectory(prefix="forge-upgrade-") as directory:
            root = unpack_release(selected, Path(directory))
            return subprocess.run(["bash", str(root / "install.sh"), "--setup"], cwd=root, env={**os.environ, "PYTHONPATH": ""}, check=False).returncode
    except (ForgeError, OSError, ValueError) as exc:
        print("Forge update: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
