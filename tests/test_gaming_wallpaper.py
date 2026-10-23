import json
import os
import tempfile
import unittest
from pathlib import Path

from forge.control import DEFAULTS, GAME, LIVE, validate
from forge.gaming import active_games, command as game_command
from forge.manifest import ForgeError
from forge.wallpaper import library, live_command, renderer_status, static_other, validate_project


class GamingWallpaperTests(unittest.TestCase):
    def test_compatible_defaults(self):
        value = validate({})
        self.assertFalse(value["liveWallpaper"]["enabled"])
        self.assertTrue(value["liveWallpaper"]["pauseOnGaming"])
        self.assertTrue(value["liveWallpaper"]["silent"])
        self.assertEqual(value["liveWallpaper"]["fps"], 30)
        self.assertEqual(value["gameOptions"]["fps"], 120)
        self.assertFalse(value["gameOptions"]["gamescope"])

    def test_invalid_live_settings(self):
        for patch in ({"fps": True}, {"fps": 240}, {"enabled": 1}, {"project": "relative"}, {"output": "bad;cmd"}, {"silent": "yes"}, {"assets": "/tmp/\nbad"}):
            with self.subTest(patch=patch), self.assertRaises(ForgeError):
                validate({"liveWallpaper": {**LIVE, **patch}})

    def test_invalid_game_settings(self):
        for patch in ({"fps": 0}, {"width": "1920"}, {"height": 1}, {"overlay": 1}, {"unknown": True}):
            with self.subTest(patch=patch), self.assertRaises(ForgeError):
                validate({"gameOptions": {**GAME, **patch}})

    def test_game_command_does_not_use_shell(self):
        value = game_command(["game", "literal; text"], {**GAME, "overlay": True, "gamescope": True}, False, lambda name: "/usr/bin/" + name)
        self.assertIn("prime-run", value)
        self.assertIn("gamemoderun", value)
        self.assertIn("mangohud", value)
        self.assertIn("gamescope", value)
        self.assertIn("literal; text", value)
        self.assertNotIn("sh", value)
        self.assertEqual(value[value.index("-r") + 1], "120")

    def test_vm_does_not_request_gpu_offload_or_governor_changes(self):
        value = game_command(["true"], GAME, True, lambda name: name)
        self.assertNotIn("prime-run", value)
        self.assertNotIn("gamemoderun", value)
        self.assertIn("systemd-inhibit", value)

    def test_optional_game_tools_must_be_installed(self):
        with self.assertRaises(ForgeError):
            game_command(["game"], {**GAME, "overlay": True}, True, lambda name: None)

    def test_only_owned_compatible_project_types_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {**LIVE, "project": str(root), "assets": str(root)}
            for kind in ("scene", "video", "web"):
                (root / "project.json").write_text(json.dumps({"type": kind}))
                self.assertEqual(validate_project(value)["type"], kind)
            for data in ({"type": "application"}, [], {"type": "unknown"}):
                (root / "project.json").write_text(json.dumps(data))
                with self.assertRaises(ForgeError):
                    validate_project(value)

    def test_live_renderer_command_is_capped_muted_and_fullscreen_pausable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.json").write_text('{"type":"scene"}')
            value = live_command({**LIVE, "project": str(root), "assets": str(root)}, "HDMI-A-1", lambda name: "/usr/bin/" + name)
            self.assertEqual(value[value.index("--fps") + 1], "30")
            self.assertIn("--silent", value)
            self.assertIn("--no-audio-processing", value)
            self.assertNotIn("--no-fullscreen-pause", value)

    def test_missing_renderer_is_reported(self):
        self.assertFalse(renderer_status(lambda name: None)["installed"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.json").write_text('{"type":"video"}')
            with self.assertRaises(ForgeError):
                live_command({**LIVE, "project": str(root), "assets": str(root)}, "HDMI-A-1", lambda name: None)

    def test_library_discovers_standard_steam_assets_and_workshop(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            steamapps = home / ".local/share/Steam/steamapps"
            assets = steamapps / "common/wallpaper_engine/assets"
            assets.mkdir(parents=True)
            project = steamapps / "workshop/content/431960/123"
            project.mkdir(parents=True)
            (project / "project.json").write_text('{"type":"scene","title":"Forge wallpaper"}')
            value = library(home)
            self.assertIn(str(assets.resolve()), value["wallpaperAssets"])
            self.assertEqual(value["wallpaperProjects"][0]["title"], "Forge wallpaper")

    def test_no_live_output_is_covered_by_static_background(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.assertIsNone(static_other(home, DEFAULTS, []))
            value = static_other(home, DEFAULTS, ["eDP-1"])
            self.assertIn("eDP-1", value)
            self.assertNotIn("HDMI-A-1", value)

    def test_stale_game_marker_does_not_pause_wallpaper(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            marker = home / ".local/state/hyprland-forge/games/1.json"
            marker.parent.mkdir(parents=True)
            marker.write_text('{"pid":1,"start":"not-real"}')
            self.assertFalse(active_games(home, home / "proc"))

    @unittest.skipUnless(os.name == "posix", "Linux process lifetime tracking required")
    def test_game_marker_detects_real_process_and_rejects_pid_reuse(self):
        from forge.gaming import process_start
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            marker = home / ".local/state/hyprland-forge/games/current.json"
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"pid": os.getpid(), "start": process_start(os.getpid())}))
            self.assertTrue(active_games(home))
            marker.write_text(json.dumps({"pid": os.getpid(), "start": "old"}))
            self.assertFalse(active_games(home))


if __name__ == "__main__":
    unittest.main()
