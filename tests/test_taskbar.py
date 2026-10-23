import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.manifest import ForgeError
from forge.runtime import lock, restore
from forge.taskbar import DEFAULTS, STATE, TARGET, app_id, apply, load, main, update, validate

ROOT = Path(__file__).resolve().parent.parent


class TaskbarTests(unittest.TestCase):
    def test_default_asset_matches(self):
        self.assertEqual(json.loads((ROOT / "configs/forge/taskbar.json").read_text()), DEFAULTS)

    def test_missing_config_uses_independent_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            value = load(home)
            value["pins"].append("other")
            self.assertEqual(load(home), DEFAULTS)
            self.assertFalse((home / TARGET).exists())

    def test_invalid_preferences_are_refused(self):
        for value in (None, [], {"unknown": True}, {"enabled": 1}, {"primaryOnly": "yes"}, {"showTitles": None}, {"currentMonitorOnly": 0}, {"pins": "kitty"}, {"pins": list("abcdefghijklm")}, {"pins": ["../bad"]}):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                validate(value)

    def test_identifiers_cannot_be_commands_or_paths(self):
        for value in ("", None, "x/y", "x;reboot", "a\nb", "a b", "../app", "x" * 129):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                app_id(value)
        self.assertEqual(app_id("Org.Example.App.DESKTOP"), "org.example.app")

    def test_partial_updates_preserve_other_values(self):
        value = update(DEFAULTS, {"showTitles": False})
        self.assertFalse(value["showTitles"])
        self.assertEqual(value["pins"], DEFAULTS["pins"])
        self.assertTrue(value["enabled"])

    def test_pins_are_deduplicated_and_removable(self):
        value = update(DEFAULTS, pin="Kitty.desktop")
        self.assertEqual(value["pins"], DEFAULTS["pins"])
        value = update(value, pin="org.example.App")
        self.assertIn("org.example.app", value["pins"])
        self.assertNotIn("kitty", update(value, unpin="kitty.desktop")["pins"])
        self.assertEqual(update(value, unpin="missing"), value)

    def test_pin_limit_is_enforced_after_append(self):
        value = validate({"pins": ["app" + str(index) for index in range(12)]})
        with self.assertRaises(ForgeError):
            update(value, pin="another")

    def test_patch_must_be_an_object(self):
        for value in (False, [], 1, "enabled"):
            with self.assertRaises(ForgeError):
                update(DEFAULTS, value)

    def test_corrupt_or_oversized_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            target = home / TARGET
            target.parent.mkdir(parents=True)
            for content in ("not json", " " * 16385, '{"pins":[2]}'):
                target.write_text(content)
                with self.assertRaises((ForgeError, ValueError)):
                    load(home)
                self.assertEqual(target.read_text(), content)

    def test_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch("forge.taskbar.lock", side_effect=lambda path: contextlib.nullcontext()):
                result = apply(home, {"showTitles": False}, pin="example")
            self.assertFalse(load(home)["showTitles"])
            self.assertIn("example", load(home)["pins"])
            self.assertEqual(restore(result["transaction"], home, home / STATE), [])
            self.assertFalse((home / TARGET).exists())

    def test_consecutive_updates_merge_current_state(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch("forge.taskbar.lock", side_effect=lambda path: contextlib.nullcontext()):
                first = apply(home, {"primaryOnly": True})
                second = apply(home, {"showTitles": False})
            self.assertTrue(load(home)["primaryOnly"])
            self.assertFalse(load(home)["showTitles"])
            self.assertEqual(restore(second["transaction"], home, home / STATE), [])
            self.assertTrue(load(home)["showTitles"])
            self.assertTrue(load(home)["primaryOnly"])
            self.assertEqual(restore(first["transaction"], home, home / STATE), [])

    def test_rollback_preserves_external_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch("forge.taskbar.lock", side_effect=lambda path: contextlib.nullcontext()):
                result = apply(home, {"enabled": False})
            (home / TARGET).write_text("manually edited")
            self.assertEqual(restore(result["transaction"], home, home / STATE), [TARGET])

    def test_symlink_config_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            target = home / TARGET
            target.parent.mkdir(parents=True)
            other = home / "other.json"
            other.write_text("{}")
            try:
                target.symlink_to(other)
            except OSError:
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ForgeError):
                load(home)

    def test_destination_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / TARGET).mkdir(parents=True)
            with self.assertRaises(ForgeError):
                apply(home, {"enabled": False})

    def test_cli_plan_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.taskbar.Path.home", return_value=Path(directory)):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(["--set", '{"enabled":false}', "--plan"]), 0)
            self.assertFalse(json.loads(stream.getvalue())["settings"]["enabled"])
            self.assertFalse((Path(directory) / TARGET).exists())

    def test_windows_apply_is_refused(self):
        with patch("forge.runtime.platform.system", return_value="Windows"), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--pin", "kitty", "--apply"]), 1)

    def test_invalid_cli_mutations_are_refused(self):
        for args in (["--set", "bad"], ["--set", "null"], ["--set", "false"], ["--rollback", "no"], ["--query", "--apply"], ["--apply"]):
            with patch("forge.taskbar.preflight"), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)

    @unittest.skipUnless(sys.platform == "linux", "Linux file locking required")
    def test_shared_installer_lock_is_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with lock(home / ".local/state/hyprland-forge"), self.assertRaises(ForgeError):
                apply(home, {"enabled": False})
            self.assertFalse((home / TARGET).exists())


if __name__ == "__main__":
    unittest.main()
