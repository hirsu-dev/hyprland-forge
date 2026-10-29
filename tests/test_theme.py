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
from forge.runtime import lock
from forge.theme import INTERFACE_DEFAULTS, PRESETS, apply_theme, interface_payload, main, palette, render, rgb, sample_image


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
        for target, content in render(PRESETS["ghostwire"]).items():
            source = ROOT / "configs" / target.removeprefix(".config/")
            self.assertEqual(source.read_text(encoding="utf-8"), content)

    def test_signal_presets_keep_their_identity(self):
        for name in ("overdrive", "redline", "icewire", "monolith"):
            self.assertEqual(palette(PRESETS[name])["accent"], PRESETS[name])
        self.assertEqual(palette(PRESETS["overdrive"])["background"], "#100d16")

    def test_ghostwire_has_a_coherent_cool_base_and_opacity_is_bounded(self):
        value = palette(PRESETS["ghostwire"])
        self.assertEqual(value["background"], "#10191f")
        self.assertEqual(value["line"], "#536d78")
        self.assertIn("536d78ff", render(PRESETS["ghostwire"])[".config/hypr/forge/colors.lua"])
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            self.assertEqual(json.loads(interface_payload(home, patch={"panelOpacity": 0.8})[".config/forge/interface.json"])["panelOpacity"], 0.8)
            for invalid in (0.69, 1.01, True, "0.9", float("nan")):
                with self.subTest(invalid=invalid), self.assertRaises(ForgeError):
                    interface_payload(home, patch={"panelOpacity": invalid})

    def test_interface_toggles_preserve_other_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            target = user / ".config/forge/interface.json"
            target.parent.mkdir(parents=True)
            target.write_text('{"motion": false, "effects": true}')
            payload = interface_payload(user, effects="off")
            self.assertEqual(json.loads(payload[".config/forge/interface.json"]), {**INTERFACE_DEFAULTS, "motion": False, "effects": False})
            self.assertEqual(json.loads(target.read_text()), {"motion": False, "effects": True})

    def test_interface_defaults_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            state = user / ".local/state/hyprland-forge/themes"
            payload = interface_payload(user, motion="off")
            self.assertEqual(json.loads(payload[".config/forge/interface.json"]), {**INTERFACE_DEFAULTS, "motion": False})
            from forge.theme import apply_files
            with patch("forge.theme.lock", side_effect=lambda path: contextlib.nullcontext()):
                transaction = apply_files(payload, user, state)
            self.assertEqual(restore(transaction, user, state), [])
            self.assertFalse((user / ".config/forge/interface.json").exists())

    def test_interface_rejects_invalid_existing_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            target = user / ".config/forge/interface.json"
            target.parent.mkdir(parents=True)
            for value in ('[]', '{"motion": "off"}', '{"effects": 0}', '{"unknown": true}', " " * 8193):
                target.write_text(value)
                with self.subTest(value=value[:30]), self.assertRaises((ForgeError, ValueError)):
                    interface_payload(user, motion="on")

    def test_interface_cli_conflicts_are_refused(self):
        for args in (["--motion", "off", "--preset", "overdrive"], ["--effects", "off", "--motion", "off"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--motion", "off", "--rollback", "example"]), 1)

    def test_interface_patch_migrates_legacy_and_preserves_values(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            target = user / ".config/forge/interface.json"
            target.parent.mkdir(parents=True)
            target.write_text('{"motion":false,"effects":true,"scale":1.25}')
            value = json.loads(interface_payload(user, patch={"spacing": 1.5, "jaggedness": 2, "ambient": False})[".config/forge/interface.json"])
            self.assertFalse(value["motion"])
            self.assertEqual(value["scale"], 1.25)
            self.assertEqual(value["spacing"], 1.5)
            self.assertEqual(value["jaggedness"], 2)
            self.assertFalse(value["ambient"])
            self.assertEqual(json.loads(target.read_text())["scale"], 1.25)

    def test_interface_patch_rejects_unbounded_or_mistyped_values(self):
        with tempfile.TemporaryDirectory() as directory:
            for patch_value in ([], {"scale": True}, {"scale": 0.1}, {"scale": 2}, {"spacing": "wide"}, {"intensity": float("nan")}, {"speed": float("inf")}, {"jaggedness": -1}, {"ambient": "on"}, {"extra": 1}):
                with self.subTest(value=patch_value), self.assertRaises(ForgeError):
                    interface_payload(Path(directory), patch=patch_value)

    def test_interface_cannot_read_through_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            target = user / ".config/forge/interface.json"
            target.parent.mkdir(parents=True)
            source = user / "original.json"
            source.write_text('{"motion": false}')
            try:
                target.symlink_to(source)
            except OSError:
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ForgeError):
                interface_payload(user, effects="off")

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

    @unittest.skipUnless(sys.platform == "linux", "Linux file locking required")
    def test_appearance_obeys_shared_installer_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory)
            state = user / ".local/state/hyprland-forge/themes"
            with lock(state.parent), self.assertRaises(ForgeError):
                apply_theme(PRESETS["sage"], user, state)
            self.assertFalse((user / ".config/forge/theme.json").exists())


if __name__ == "__main__":
    unittest.main()
