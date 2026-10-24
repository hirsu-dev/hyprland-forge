import os
import tempfile
import unittest
from pathlib import Path

from forge.everyday import initialize_defaults
from forge.manifest import ForgeError


class EverydayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.data = self.home / "data"
        applications = self.data / "applications"
        applications.mkdir(parents=True)
        for name in ("thunar.desktop", "firefox.desktop", "mpv.desktop"):
            (applications / name).touch()
        self.environment = {"XDG_DATA_HOME": str(self.data), "XDG_DATA_DIRS": ""}
        self.target = self.home / ".config/mimeapps.list"

    def test_fresh_defaults_reference_only_installed_apps(self):
        self.assertTrue(initialize_defaults(self.home, self.environment))
        value = self.target.read_text()
        self.assertIn("inode/directory=thunar.desktop;", value)
        self.assertIn("video/mp4=mpv.desktop;", value)
        self.assertNotIn("application/pdf", value)
        self.assertFalse(initialize_defaults(self.home, self.environment))
        self.assertEqual(value, self.target.read_text())
        self.assertEqual(list(self.target.parent.glob(".forge-defaults-*")), [])

    def test_existing_user_and_legacy_choices_are_preserved(self):
        for relative in (".config/mimeapps.list", ".config/hyprland-mimeapps.list", "data/applications/mimeapps.list"):
            with self.subTest(relative=relative):
                path = self.home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("[Default Applications]\ntext/html=my-browser.desktop;\n")
                self.assertFalse(initialize_defaults(self.home, self.environment))
                self.assertIn("my-browser.desktop", path.read_text())
                path.unlink()

    def test_empty_app_inventory_and_external_config_are_not_written(self):
        self.assertFalse(initialize_defaults(self.home, {"XDG_DATA_DIRS": str(self.home / "missing")}))
        self.assertFalse(self.target.exists())
        self.assertFalse(initialize_defaults(self.home, {**self.environment, "XDG_CONFIG_HOME": str(self.home.parent / "elsewhere")}))
        self.assertFalse(initialize_defaults(self.home, {**self.environment, "XDG_CONFIG_HOME": "relative"}))

    def test_custom_xdg_locations_are_respected(self):
        self.assertTrue(initialize_defaults(self.home, {**self.environment, "XDG_CONFIG_HOME": str(self.home / "settings")}))
        self.assertTrue((self.home / "settings/mimeapps.list").is_file())
        self.assertFalse(self.target.exists())

    @unittest.skipUnless(os.name == "posix", "Unix symlink behavior")
    def test_symlinked_config_is_refused(self):
        location = self.home / "redirect"
        location.mkdir()
        (self.home / ".config").symlink_to(location, target_is_directory=True)
        with self.assertRaises(ForgeError):
            initialize_defaults(self.home, self.environment)
        self.assertFalse((location / "mimeapps.list").exists())
