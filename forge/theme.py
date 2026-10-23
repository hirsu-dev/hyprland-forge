import argparse
import colorsys
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .manifest import ForgeError
from .runtime import execute, lock, preflight, restore
from .storage import atomic_write, safe_target


PRESETS = {"overdrive": "#fcee0a", "redline": "#ff4d61", "icewire": "#74f7ef", "monolith": "#e9e1ec", "sage": "#b5c9a8", "ocean": "#9dbbd1", "plum": "#c6afd2", "ember": "#dec49a"}
BASE = {"background": "#100d16", "surface": "#1d141f", "raised": "#2b1b2a", "text": "#f4edf5", "muted": "#bdaab8", "line": "#693642", "cyan": "#74f7ef", "danger": "#ff4d61"}


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ForgeError("Accent must be a six-digit hex color")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def hex_color(channels):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in channels)


def palette(accent):
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb(accent))
    result = dict(BASE)
    result["accent"] = hex_color(colorsys.hls_to_rgb(hue, max(0.5, lightness), saturation))
    def luminance(color):
        return sum(weight * (channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4) for weight, channel in zip((0.2126, 0.7152, 0.0722), rgb(color)))
    lightness = luminance(result["accent"])
    dark_contrast = (lightness + 0.05) / (luminance(BASE["background"]) + 0.05)
    light_contrast = (luminance(BASE["text"]) + 0.05) / (lightness + 0.05)
    result["accentText"] = BASE["background"] if dark_contrast >= light_contrast else BASE["text"]
    return result


def sample_image(path):
    from PIL import Image, ImageOps
    try:
        source = Image.open(path)
    except Image.DecompressionBombError as exc:
        raise ForgeError("Wallpaper exceeds the sampling safety limit") from exc
    with source:
        if source.width * source.height > 40_000_000:
            raise ForgeError("Wallpaper exceeds the 40-megapixel sampling limit")
        source.draft("RGB", (256, 256))
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((128, 128))
        colors = image.quantize(colors=12).convert("RGB").getcolors(128 * 128) or []
    if not colors:
        raise ForgeError("Could not sample image colors")
    def score(item):
        count, channels = item
        _, lightness, saturation = colorsys.rgb_to_hls(*(c / 255 for c in channels))
        return count * (0.15 + saturation) * (1 - abs(lightness - 0.5))
    return hex_color(c / 255 for c in max(colors, key=score)[1])


def render(accent):
    colors = palette(accent)
    border = colors["accent"][1:] + "ff"
    return {
        ".config/forge/theme.json": json.dumps(colors, indent=2) + "\n",
        ".config/hypr/forge/colors.lua": 'hl.config({ general = { col = { active_border = "rgba(' + border + ')", inactive_border = "rgba(693642ff)" } } })\n',
        ".config/kitty/forge-colors.conf": "\n".join(f"{key} {value}" for key, value in {
            "background": colors["background"], "foreground": colors["text"], "cursor": colors["accent"],
            "selection_background": colors["accent"], "selection_foreground": colors["accentText"],
            "active_tab_background": colors["accent"], "active_tab_foreground": colors["accentText"],
        }.items()) + "\n",
        ".config/fuzzel/forge-colors.ini": "[colors]\n" + "\n".join(f"{key}={value[1:]}ff" for key, value in {
            "background": colors["background"], "text": colors["text"], "match": colors["accent"],
            "selection": colors["accent"], "selection-text": colors["accentText"],
            "selection-match": colors["background"], "border": colors["line"],
        }.items()) + "\n",
    }


def apply_files(payload, user_root, state_root):
    try:
        state_relative = str((state_root / "install.lock").relative_to(user_root)).replace("\\", "/")
    except ValueError as exc:
        raise ForgeError("Transaction storage must be inside home") from exc
    safe_target(user_root, state_relative)
    safe_target(user_root, ".local/state/hyprland-forge/install.lock")
    for target in payload:
        safe_target(user_root, target)
    with tempfile.TemporaryDirectory(prefix="forge-theme-") as directory:
        source_root = Path(directory)
        files = []
        for index, (target, content) in enumerate(payload.items()):
            source = f"configs/{index}"
            atomic_write(source_root / source, content.encode("utf-8"), 0o644)
            files.append({"source": source, "target": target})
        with lock(user_root / ".local/state/hyprland-forge"):
            return execute({"commands": [], "files": files}, source_root, user_root, state_root)


def apply_theme(accent, user_root, state_root):
    return apply_files(render(accent), user_root, state_root)


def interface_payload(user_root, motion=None, effects=None):
    target = safe_target(user_root, ".config/forge/interface.json")
    settings = {"motion": True, "effects": True}
    if target.exists():
        if target.stat().st_size > 8192:
            raise ForgeError("Interface preferences exceed the size limit")
        current = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(current, dict) or any(key not in settings or not isinstance(value, bool) for key, value in current.items()):
            raise ForgeError("Invalid interface preferences")
        settings.update(current)
    if motion is not None:
        settings["motion"] = motion == "on"
    if effects is not None:
        settings["effects"] = effects == "on"
    return {".config/forge/interface.json": json.dumps(settings, indent=2) + "\n"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-appearance")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--preset", choices=PRESETS, default=None)
    source.add_argument("--accent")
    source.add_argument("--wallpaper", type=Path)
    source.add_argument("--motion", choices=("on", "off"))
    source.add_argument("--effects", choices=("on", "off"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", metavar="TRANSACTION")
    mode.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.rollback and (args.accent or args.preset or args.wallpaper or args.motion or args.effects):
            raise ForgeError("Rollback cannot be combined with an accent or wallpaper")
        accent = args.accent or PRESETS[args.preset or "overdrive"]
        if args.wallpaper:
            accent = sample_image(args.wallpaper)
        payload = interface_payload(Path.home(), args.motion, args.effects) if args.motion or args.effects else render(accent)
        if not args.apply and not args.rollback:
            print(json.dumps(payload, indent=2))
            return 0
        preflight()
        user_root = Path.home()
        state_root = user_root / ".local/state/hyprland-forge/themes"
        if args.rollback:
            safe_target(user_root, ".local/state/hyprland-forge/install.lock")
            with lock(user_root / ".local/state/hyprland-forge"):
                conflicts = restore(args.rollback, user_root, state_root)
            if conflicts:
                raise ForgeError("Kept edited files: " + ", ".join(conflicts))
            print("Appearance restored")
        else:
            print("Appearance saved: " + apply_files(payload, user_root, state_root))
        for command in (["hyprctl", "reload"],):
            try:
                subprocess.run(command, check=False, capture_output=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return 0
    except (ForgeError, OSError, ValueError, ImportError, subprocess.CalledProcessError) as exc:
        print(f"Forge appearance: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
