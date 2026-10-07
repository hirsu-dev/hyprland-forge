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


PRESETS = {"sage": "#b5c9a8", "ocean": "#9dbbd1", "plum": "#c6afd2", "ember": "#dec49a"}
BASE = {"background": "#11171f", "surface": "#1b242d", "raised": "#27323b", "text": "#e1e7ea", "muted": "#9daab3", "line": "#39454d"}


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ForgeError("Accent must be a six-digit hex color")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def hex_color(channels):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in channels)


def palette(accent):
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb(accent))
    result = dict(BASE)
    result["accent"] = hex_color(colorsys.hls_to_rgb(hue, max(0.72, min(0.82, lightness)), min(0.6, max(0.22, saturation))))
    result["accentText"] = "#142018"
    return result


def sample_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as source:
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
        ".config/hypr/forge/colors.lua": 'hl.config({ general = { col = { active_border = "rgba(' + border + ')", inactive_border = "rgba(39454dff)" } } })\n',
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


def apply_theme(accent, user_root, state_root):
    payload = render(accent)
    safe_target(user_root, ".local/state/hyprland-forge/themes/install.lock")
    for target in payload:
        safe_target(user_root, target)
    with tempfile.TemporaryDirectory(prefix="forge-theme-") as directory:
        source_root = Path(directory)
        files = []
        for index, (target, content) in enumerate(payload.items()):
            source = f"configs/{index}"
            atomic_write(source_root / source, content.encode("utf-8"), 0o644)
            files.append({"source": source, "target": target})
        with lock(state_root):
            return execute({"commands": [], "files": files}, source_root, user_root, state_root)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forge-appearance")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--preset", choices=PRESETS, default=None)
    source.add_argument("--accent")
    source.add_argument("--wallpaper", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", metavar="TRANSACTION")
    mode.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.rollback and (args.accent or args.preset or args.wallpaper):
            raise ForgeError("Rollback cannot be combined with an accent or wallpaper")
        accent = args.accent or PRESETS[args.preset or "sage"]
        if args.wallpaper:
            accent = sample_image(args.wallpaper)
        if not args.apply and not args.rollback:
            print(json.dumps(render(accent), indent=2))
            return 0
        preflight()
        user_root = Path.home()
        state_root = user_root / ".local/state/hyprland-forge/themes"
        if args.rollback:
            safe_target(user_root, ".local/state/hyprland-forge/themes/install.lock")
            with lock(state_root):
                conflicts = restore(args.rollback, user_root, state_root)
            if conflicts:
                raise ForgeError("Kept edited files: " + ", ".join(conflicts))
            print("Appearance restored")
        else:
            print("Appearance saved: " + apply_theme(accent, user_root, state_root))
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
