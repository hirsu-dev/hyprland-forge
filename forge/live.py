import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from .manifest import ForgeError, load_manifest
from .setup import confirm
from .storage import atomic_write


REPOSITORY = "hirsu-dev/hyprland-forge"


def release_asset(version):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ForgeError("Invalid installer release")
    request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/v{version}", headers={"Accept": "application/vnd.github+json", "User-Agent": "hyprland-forge"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    name = f"hyprland-forge-{version}.tar.gz"
    for asset in data.get("assets", []):
        if asset.get("name") == name and re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest", "")):
            return f"https://github.com/{REPOSITORY}/releases/download/v{version}/{name}", asset["digest"][7:]
    raise ForgeError("This release does not have a verified installation archive")


def stage_command(version, url, digest):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ForgeError("Invalid staging identity")
    expected = f"https://github.com/{REPOSITORY}/releases/download/v{version}/hyprland-forge-{version}.tar.gz"
    if url != expected:
        raise ForgeError("Unexpected installation archive URL")
    target = "/opt/hyprland-forge-" + version
    return "\n".join([
        "set -eu",
        'forge_stage="$(mktemp -d -t forge-stage-XXXXXXXX)"',
        "trap 'rm -r -- \"$forge_stage\"' EXIT",
        "curl -fsSL --retry 2 " + shlex.quote(url) + ' -o "$forge_stage/release.tar.gz"',
        "printf '%s  %s\\n' " + digest + ' "$forge_stage/release.tar.gz" | sha256sum --check --status',
        'tar -xzf "$forge_stage/release.tar.gz" -C "$forge_stage"',
        "test ! -e " + target + " && test ! -L " + target,
        'mv -- "$forge_stage/hyprland-forge" ' + target,
        "chmod -R a+rX " + target,
        "cd -- " + target,
        "python3 -m forge.live --stage",
    ])


def configuration(version, url, digest):
    return {
        "archinstall-language": "English",
        "hostname": "forge",
        "kernels": ["linux"],
        "locale_config": {"kb_layout": "us", "sys_enc": "UTF-8", "sys_lang": "en_US"},
        "timezone": "America/New_York",
        "ntp": True,
        "network_config": {"type": "nm"},
        "packages": ["curl", "python", "sudo", "networkmanager"],
        "services": ["NetworkManager"],
        "profile_config": {"profile": {"main": "Minimal"}},
        "bootloader_config": {"bootloader": "Systemd-boot", "uki": False, "removable": False},
        "custom_commands": [stage_command(version, url, digest)],
    }


def first_login(source_root, root=Path("/")):
    source_root = Path(source_root)
    if not re.fullmatch(r"/opt/hyprland-forge-[0-9]+\.[0-9]+\.[0-9]+", source_root.as_posix()):
        raise ForgeError("Unexpected first-login installer directory")
    target = root / "etc/profile.d/forge-setup.sh"
    if target.parent.is_symlink() or target.is_symlink():
        raise ForgeError("Unsafe first-login configuration")
    script = "\n".join([
        'if [ -t 0 ] && [ "$(id -u)" -ge 1000 ] && [ "$(id -u)" -lt 65534 ] && [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}${SSH_CONNECTION:-}" ] && [ ! -f "$HOME/.local/state/hyprland-forge/setup-complete" ]; then',
        '    printf "\\nFinish installing your Forge desktop.\\n"',
        "    bash " + source_root.as_posix() + "/install.sh --setup || printf '%s\\n' 'Forge setup stopped. Run the installer again to retry.'",
        "fi",
        "",
    ])
    if target.exists() and target.read_text() != script:
        raise ForgeError("An existing first-login installer needs review")
    atomic_write(target, script.encode(), mode=0o644)
    return target


def run(source_root):
    if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() != 0 or not Path("/run/archiso").is_dir():
        raise ForgeError("Use the official x86_64 Arch installation USB for base installation")
    if not sys.stdin.isatty():
        raise ForgeError("The Arch installer needs an interactive terminal")
    if not shutil.which("archinstall"):
        raise ForgeError("Use a current official Arch ISO containing archinstall")
    manifest = load_manifest(source_root)
    print("\nHYPRLAND FORGE — ARCH INSTALLATION\n")
    print("Base defaults are prepared: kernel, locale, time zone, networking and setup tools.")
    print("Choose your disk layout and a sudo-enabled user in Arch's installation screen.")
    print("For Windows dual boot, choose manual partitioning and use only unallocated space.")
    print("Use a separate Linux EFI partition of at least 1 GiB; keep the Windows EFI partition intact.")
    print("Your first normal-user login will offer to finish the Forge desktop automatically.")
    print("If the machine returns to Windows, select Arch Linux in your firmware's one-time boot menu.")
    if not confirm("Open the Arch installer with Forge defaults?"):
        return 0
    url, digest = release_asset(manifest["release"])
    with tempfile.TemporaryDirectory(prefix="forge-arch-") as directory:
        config = Path(directory) / "forge.json"
        config.write_text(json.dumps(configuration(manifest["release"], url, digest)))
        config.chmod(0o600)
        subprocess.run(["archinstall", "--config", str(config)], check=True)
    print("After a successful base installation, boot Arch and sign in as your normal user.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args(argv)
    source_root = Path(__file__).resolve().parent.parent
    try:
        if args.stage:
            if platform.system() != "Linux" or os.geteuid() != 0 or not Path("/etc/arch-release").is_file() or subprocess.run(["systemd-detect-virt", "--chroot"], capture_output=True).returncode != 0:
                raise ForgeError("First-login staging runs only inside the Arch target chroot")
            first_login(source_root)
            return 0
        return run(source_root)
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Forge: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Forge: cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
