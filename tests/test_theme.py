import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.manifest import ForgeError
from forge.runtime import restore
from forge.theme import PRESETS, apply_theme, main, palette, render, rgb, sample_image


ROOT = Path(__file__).resolve().parent.parent


class ThemeTests(unittest.TestCase):
    def test_rejects_invalid_accents(self):
        for accent in (None, "red", "#fff", "#000000\n", '#aabbcc); os.execute("x")', "#zzzzzz"):
            with self.subTest(accent=accent), self.assertRaises(ForgeError):
                render(accent)

    def test_presets_are_coherent_and_safe(self):
        for accent in PRESETS.values():
            colors = palette(accent)
            for color in colors.values():
                rgb(color)
            files = render(accent)
            self.assertEqual(len(files), 4)
            self.assertEqual(json.loads(files[".config/forge/theme.json"]), colors)
            self.assertIn(colors["accent"][1:] + "ff", files[".config/hypr/forge/colors.lua"])
            self.assertIn(colors["accent"], files[".config/kitty/forge-colors.conf"])
            self.assertIn(colors["accent"][1:] + "ff", files[".config/fuzzel/forge-colors.ini"])

    def test_default_assets_match_generator(self):
        for target, content in render(PRESETS["sage"]).items():
            source = ROOT / "configs" / target.removeprefix(".config/")
            self.assertEqual(source.read_text(encoding="utf-8"), content)

    def test_cli_plan_is_read_only(self):
        result = subprocess.run([sys.executable, "-m", "forge.theme", "--plan", "--preset", "plum"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), render(PRESETS["plum"]))

    def test_non_arch_apply_is_refused(self):
        with patch("forge.runtime.platform.system", return_value="Windows"), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--apply"]), 1)

    def test_apply_and_restore_preserve_original(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            state = user / ".local/state/hyprland-forge/themes"
            target = user / ".config/forge/theme.json"
            target.parent.mkdir(parents=True)
            target.write_text("original")
            with patch("forge.theme.lock", side_effect=lambda path: contextlib.nullcontext()):
                transaction = apply_theme(PRESETS["ocean"], user, state)
            self.assertEqual(json.loads(target.read_text()), palette(PRESETS["ocean"]))
            self.assertEqual(restore(transaction, user, state), [])
            self.assertEqual(target.read_text(), "original")
            self.assertFalse((user / ".config/kitty/forge-colors.conf").exists())

    def test_edits_survive_theme_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            state = user / ".local/state/hyprland-forge/themes"
            with patch("forge.theme.lock", side_effect=lambda path: contextlib.nullcontext()):
                transaction = apply_theme(PRESETS["plum"], user, state)
            target = user / ".config/forge/theme.json"
            target.write_text("edited")
            self.assertEqual(restore(transaction, user, state), [".config/forge/theme.json"])
            self.assertEqual(target.read_text(), "edited")

    def test_all_destinations_checked_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            state = user / ".local/state/hyprland-forge/themes"
            (user / ".config/kitty/forge-colors.conf").mkdir(parents=True)
            with self.assertRaises(ForgeError):
                apply_theme(PRESETS["sage"], user, state)
            self.assertFalse((user / ".config/forge/theme.json").exists())
            self.assertFalse(state.exists())

    def test_wallpaper_sampling(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow unavailable")
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sample.png"
            Image.new("RGB", (32, 32), (105, 190, 135)).save(image)
            self.assertEqual(sample_image(image), "#69be87")

    def test_theme_state_cannot_escape_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user = root / "home"
            user.mkdir()
            with self.assertRaises(ForgeError):
                apply_theme(PRESETS["sage"], user, root / "outside")
            self.assertFalse((root / "outside").exists())

    def test_theme_state_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user = root / "home"
            state = user / ".local/state/hyprland-forge/themes"
            state.parent.mkdir(parents=True)
            outside = root / "outside"
            outside.mkdir()
            try:
                state.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ForgeError):
                apply_theme(PRESETS["sage"], user, state)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
