import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def prepare(source, profile, repository):
    source, profile, repository = (Path(p).resolve() for p in (source, profile, repository))
    root = profile / "airootfs"
    if not (profile / "profiledef.sh").is_file() or not (repository / "forge.db.tar.gz").is_file():
        raise ValueError("An archiso releng profile and a built installer repository are required")
    overlay = source / "iso/profile/airootfs"
    shutil.copytree(overlay, root, dirs_exist_ok=True)
    with (profile / "pacman.conf").open("a") as stream:
        stream.write(f"\n[forge]\nSigLevel = Optional\nServer = file://{repository}\n")
    packages = set((profile / "packages.x86_64").read_text().splitlines())
    packages.update("calamares xorg-server xorg-xinit openbox pyside6 qt6-wayland qt6-svg networkmanager network-manager-applet nm-connection-editor python-yaml arch-install-scripts rsync grub os-prober efibootmgr gptfdisk dosfstools btrfs-progs e2fsprogs squashfs-tools ttf-jetbrains-mono-nerd noto-fonts plymouth python-pillow".split())
    (profile / "packages.x86_64").write_text("\n".join(sorted(packages)) + "\n")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    with (profile / "profiledef.sh").open("a") as stream:
        stream.write(f'\niso_name="forge-experimental"\niso_label="FORGE_{stamp}"\niso_publisher="Hirsu <https://github.com/hirsu-dev/hyprland-forge>"\niso_application="Forge Graphical Installer"\niso_version="{stamp}"\nfile_permissions+=(\n["/usr/local/bin/forge-live-session"]="0:0:0755"\n)\n')
    destination = root / "opt/hyprland-forge"
    destination.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(source), "archive", "HEAD"], check=True, capture_output=True).stdout
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination, filter="data")
    revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (destination / "build.json").write_text(json.dumps({"revision": revision, "channel": "experimental-iso"}) + "\n")
    modules = root / "etc/calamares/modules"
    for name in ("forgeguard", "forgebase", "forgefinish"):
        target = modules / name
        target.mkdir(parents=True)
        (target / "module.desc").write_text(f"---\ntype: job\nname: {name}\ninterface: python\nscript: main.py\n")
        action = {"forgeguard": "guard", "forgebase": "base", "forgefinish": "finish"}[name]
        (target / "main.py").write_text('import sys\nsys.path.insert(0, "/opt/hyprland-forge")\nfrom forge.iso_install import calamares_job\n\ndef run():\n    return calamares_job("' + action + '")\n')
    system = root / "etc/systemd/system"
    for name in ("systemd-networkd.service", "systemd-resolved.service", "iwd.service", "sshd.service"):
        target = system / name
        if target.is_symlink():
            target.unlink()
        target.symlink_to("/dev/null")
    for name in ("NetworkManager.service",):
        target = system / "multi-user.target.wants" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to("/usr/lib/systemd/system/" + name)
    for path in profile.glob("grub/*.cfg"):
        text = path.read_text().replace("Arch Linux install medium", "Forge graphical installer")
        path.write_text(text)


if __name__ == "__main__":
    prepare(*sys.argv[1:])
