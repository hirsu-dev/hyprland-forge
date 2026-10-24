import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

from .boot_art import render
from .manifest import ForgeError


def esp_uuid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}", value):
        raise ForgeError("Use the FAT filesystem UUID of each EFI partition, such as ABCD-1234")
    return value.upper()


def password_hash(password, salt=None):
    if len(password) < 12 or len(password) > 128 or not password.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ForgeError("Use a separate 12-128 character printable ASCII boot password; firmware uses a US keyboard")
    salt = salt if salt is not None else secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000)
    return "grub.pbkdf2.sha512.100000." + salt.hex().upper() + "." + digest.hex().upper()


def configuration(forge_uuid, windows_uuid, hashed):
    forge_uuid, windows_uuid = esp_uuid(forge_uuid), esp_uuid(windows_uuid)
    if not re.fullmatch(r"grub\.pbkdf2\.sha512\.100000\.[0-9A-F]{64}\.[0-9A-F]{128}", hashed):
        raise ForgeError("Invalid boot password hash")
    return f'''insmod all_video
insmod gfxterm
insmod png
insmod part_gpt
insmod fat
insmod search_fs_uuid
insmod chain
insmod password_pbkdf2
loadfont (memdisk)/boot/grub/forge.pf2
loadfont (memdisk)/boot/grub/terminal.pf2
set gfxmode=1920x1080,1280x720,1024x768,auto
set gfxpayload=keep
terminal_output gfxterm
set color_normal=yellow/black
set color_highlight=black/yellow
set superusers=forge
export superusers
password_pbkdf2 forge {hashed}
set theme=(memdisk)/boot/grub/startup.txt
export theme
set default=0
set timeout=1
menuentry 'Initialize access' --unrestricted {{
    while true; do
        clear
        echo 'FORGE / LOCAL ACCESS'
        echo 'Boot username: forge'
        echo 'Use your separate boot password.'
        if authenticate forge; then
            configfile (memdisk)/boot/grub/selector.cfg
        fi
        echo 'Access denied. Try again.'
    done
}}
'''


def selection_configuration(forge_uuid, windows_uuid):
    forge_uuid, windows_uuid = esp_uuid(forge_uuid), esp_uuid(windows_uuid)
    return f'''set theme=(memdisk)/boot/grub/theme.txt
export theme
set timeout=-1
set default=0
menuentry 'Forge OS' --class forge --users forge {{
    if search --no-floppy --fs-uuid --set=forge_esp {forge_uuid}; then
        if [ -f ($forge_esp)/EFI/systemd/systemd-bootx64.efi ]; then
            if chainloader ($forge_esp)/EFI/systemd/systemd-bootx64.efi; then
                boot
            fi
        fi
    fi
    echo 'Forge systemd-boot was not found. No disk was changed.'
    sleep --interruptible 10
}}
menuentry 'Windows 11' --class windows --users forge {{
    if search --no-floppy --fs-uuid --set=windows_esp {windows_uuid}; then
        if [ -f ($windows_esp)/EFI/Microsoft/Boot/bootmgfw.efi ]; then
            if chainloader ($windows_esp)/EFI/Microsoft/Boot/bootmgfw.efi; then
                boot
            fi
        fi
    fi
    echo 'Windows Boot Manager was not found. No disk was changed.'
    sleep --interruptible 10
}}
'''


def theme(font, terminal=None, startup=False):
    terminal = terminal or font
    if not all(re.fullmatch(r"[a-zA-Z0-9 _-]{1,100}", name) for name in (font, terminal)):
        raise ForgeError("Invalid GRUB font identity")
    base = f'''title-text: ""
desktop-image: "{'auth.png' if startup else 'selector.png'}"
desktop-image-scale-method: "stretch"
desktop-color: "#100d16"
terminal-font: "{terminal}"
terminal-left: "5%"
terminal-top: "47%"
terminal-width: "38%"
terminal-height: "41%"
'''
    if startup:
        return base + '''+ progress_bar {
    id = "__timeout__"
    left = 6%
    top = 54%
    width = 35%
    height = 3
    show_text = false
    fg_color = "#74f7ef"
    bg_color = "#693642"
}
'''
    return base + f'''
+ boot_menu {{
    left = 6%
    top = 52%
    width = 35%
    height = 20%
    item_font = "{font}"
    item_color = "#f4edf5"
    selected_item_color = "#100d16"
    item_height = 82
    item_padding = 14
    item_spacing = 18
    icon_width = 0
    icon_height = 0
    selected_item_pixmap_style = "select_*.png"
}}
'''


def font_name(path):
    data = path.read_bytes()
    offset = 0
    while offset + 8 <= len(data):
        tag = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "big")
        offset += 8
        if tag == b"NAME":
            return data[offset:offset + size].rstrip(b"\0").decode("ascii")
        offset += size
    raise ForgeError("The generated GRUB font has no name")


def source_assets():
    source = Path(__file__).resolve().parent.parent / "configs/boot"
    return source if source.is_dir() else Path.home() / ".local/share/hyprland-forge/boot"


def build(output, forge_uuid, windows_uuid, hashed, runner=subprocess.run):
    config = configuration(forge_uuid, windows_uuid, hashed)
    for command in ("grub-mkstandalone", "grub-mkfont", "grub-script-check"):
        if not shutil.which(command):
            raise ForgeError("Build this on Arch with the grub and python-pillow packages installed")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ForgeError("Choose a new output folder; existing files will not be replaced")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".forge-boot-", dir=output.parent) as temporary:
        stage = Path(temporary)
        stage.chmod(0o700)
        assets = stage / "grub"
        font = render(assets)
        runner(["grub-mkfont", "--name=ForgeMono", "--size=28", "--range=0x20-0x7e", "--output=" + str(assets / "forge.pf2"), str(font)], check=True, capture_output=True, text=True)
        runner(["grub-mkfont", "--name=ForgeTerm", "--size=14", "--range=0x20-0x7e", "--output=" + str(assets / "terminal.pf2"), str(font)], check=True, capture_output=True, text=True)
        menu_font, terminal_font = font_name(assets / "forge.pf2"), font_name(assets / "terminal.pf2")
        (assets / "theme.txt").write_text(theme(menu_font, terminal_font), encoding="utf-8", newline="\n")
        (assets / "startup.txt").write_text(theme(menu_font, terminal_font, startup=True), encoding="utf-8", newline="\n")
        (assets / "selector.cfg").write_text(selection_configuration(forge_uuid, windows_uuid), encoding="utf-8", newline="\n")
        config_path = stage / "grub.cfg"
        config_path.write_text(config, encoding="utf-8", newline="\n")
        config_path.chmod(0o600)
        runner(["grub-script-check", str(config_path)], check=True, capture_output=True, text=True)
        runner(["grub-script-check", str(assets / "selector.cfg")], check=True, capture_output=True, text=True)
        efi = stage / "EFI/Forge/forge-x64.efi"
        efi.parent.mkdir(parents=True)
        maps = ["boot/grub/grub.cfg=" + str(config_path)]
        maps.extend("boot/grub/" + p.name + "=" + str(p) for p in sorted(assets.iterdir()) if p.name != "design-preview.png")
        runner(["grub-mkstandalone", "--format=x86_64-efi", "--locales=", "--fonts=", "--output=" + str(efi), *maps], check=True, capture_output=True, text=True)
        efi.chmod(0o600)
        shutil.copytree(source_assets() / "sddm", stage / "sddm/forge-overdrive")
        (stage / "plan.json").write_text(json.dumps({"schema": 1, "forge_esp_uuid": esp_uuid(forge_uuid), "windows_esp_uuid": esp_uuid(windows_uuid), "activation": "not-installed", "boot_order_changed": False, "disk_changes": False, "forge_loader": "/EFI/systemd/systemd-bootx64.efi", "secure_boot": "unsigned-local-build-requires-review", "password_scope": "boot-menu-only-not-disk-encryption-or-OS-sign-in", "pre_os_animation": "static-themed-GRUB", "forge_login_animation": "QtQuick-SDDM"}, indent=2) + "\n", encoding="utf-8")
        os.rename(stage, output)
    return output


def main():
    parser = argparse.ArgumentParser(prog="forge-boot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--engine", choices=("native", "grub"), default="native")
    parser.add_argument("--forge-partuuid")
    parser.add_argument("--windows-partuuid")
    parser.add_argument("--forge-uuid")
    parser.add_argument("--windows-uuid")
    args = parser.parse_args()
    try:
        if args.render_only:
            if args.output.exists() or args.output.is_symlink():
                raise ForgeError("Choose a new output folder")
            if args.engine == "native":
                from .native_boot import preview
                preview(args.output)
            else:
                render(args.output)
        else:
            if args.engine == "native":
                from .native_boot import partition_id, provisioning, build as native_build
                partition_id(args.forge_partuuid)
                partition_id(args.windows_partuuid)
            else:
                esp_uuid(args.forge_uuid)
                esp_uuid(args.windows_uuid)
            if not sys.stdin.isatty():
                raise ForgeError("Boot password setup needs an interactive terminal")
            print("Prepare a boot package only. No firmware, partitions or current boot files will be changed.")
            print("Use a NEW boot password, separate from Windows, Linux and disk encryption passwords.")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                first = getpass.getpass("Boot password (12+ characters): ")
                second = getpass.getpass("Repeat boot password: ")
            if first != second:
                raise ForgeError("Passwords did not match")
            if args.engine == "native":
                provision = provisioning(first, args.forge_partuuid, args.windows_partuuid)
                del first, second
                native_build(args.output, provision)
            else:
                hashed = password_hash(first)
                del first, second
                build(args.output, args.forge_uuid, args.windows_uuid, hashed)
        print("Prepared: " + str(args.output))
        print("Not activated. Physical boot testing and a recovery path are required before installation.")
        return 0
    except (ForgeError, OSError, ValueError, ImportError, EOFError, getpass.GetPassWarning, subprocess.CalledProcessError) as exc:
        print("Forge boot: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
