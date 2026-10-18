import contextlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from forge import desktop_settings as settings
from forge.manifest import ForgeError


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name)
        self.connected = [{"name": "HDMI-A-1", "width": 1920, "height": 1080, "refreshRate": 120, "availableModes": ["1920x1080@120.00Hz", "1920x1080@60.00Hz"]}, {"name": "eDP-1", "availableModes": ["1920x1080@60.00Hz"]}]
        self.active_mode = "caelestia"
        self.runner = Mock(side_effect=self.respond)
        self.value = settings.current(self.home, self.connected, self.runner)
        self.spawn = Mock()
        self.guard = patch.object(settings, "lock", lambda _: contextlib.nullcontext())
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def apply(self):
        return settings.apply(self.value, self.home, self.connected, self.runner, self.spawn)

    def respond(self, command, **kwargs):
        if command[1] == "repl":
            return SimpleNamespace(stdout=self.active_mode + "\n")
        if command[1] == "reload":
            path = self.home / ".config/hypr/tiling.local.lua"
            self.active_mode = json.loads(path.read_text().removeprefix("return ")) if path.exists() else "caelestia"
        return SimpleNamespace(stdout="ok\n")

    def test_defaults_and_advertised_modes(self):
        self.assertEqual(self.value["primary"], "HDMI-A-1")
        self.assertEqual(self.value["tiling"], "caelestia")
        self.assertIn("1920x1080@120.00", settings.modes(self.connected[0]))
        self.assertEqual(settings.validate(self.value, self.connected), self.value)

    def test_validation(self):
        for field, invalid in (("mode", "5000x5000@900"), ("name", 'HDMI\"'), ("scale", float("nan")), ("scale", float("inf")), ("scale", True), ("scale", 5), ("x", 1.5), ("y", -32769), ("rotation", True), ("rotation", 4), ("vrr", 3), ("enabled", 1)):
            value = copy.deepcopy(self.value)
            value["outputs"][0][field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ForgeError):
                settings.validate(value, self.connected)

    def test_main_cannot_be_disabled(self):
        self.value["outputs"][0]["enabled"] = False
        with self.assertRaises(ForgeError):
            self.apply()
        self.value["primary"] = "eDP-1"
        settings.validate(self.value, self.connected)

    def test_stale_or_duplicate_outputs_rejected(self):
        for outputs in (self.value["outputs"][:1], self.value["outputs"] * 2):
            with self.assertRaises(ForgeError):
                settings.validate(dict(self.value, outputs=outputs), self.connected)

    def test_render_and_rollback(self):
        original = self.home / ".config/hypr/monitors.local.lua"
        original.parent.mkdir(parents=True)
        original.write_text('return { internal_position = "left" }\n')
        pending = self.apply()
        self.assertIn('["outputs"]', original.read_text())
        self.assertIn('"disabled"] = false', original.read_text())
        self.spawn.assert_called_once()
        self.assertTrue(self.spawn.call_args.kwargs["start_new_session"])
        self.assertEqual(settings.finish(self.home, pending["id"], False, self.runner)["status"], "reverted")
        self.assertEqual(original.read_text(), 'return { internal_position = "left" }\n')
        self.assertFalse((self.home / ".config/forge/desktop.json").exists())
        self.assertIsNone(settings.read_pending(self.home))

    def test_confirm_prevents_watchdog_rollback(self):
        pending = self.apply()
        self.assertEqual(settings.finish(self.home, pending["id"], True, self.runner)["status"], "kept")
        self.assertEqual(settings.finish(self.home, pending["id"], False, self.runner)["status"], "unchanged")
        self.assertTrue((self.home / ".config/forge/desktop.json").exists())

    def test_expired_confirmation_reverts(self):
        pending = self.apply()
        with patch.object(settings.time, "time", return_value=pending["deadline"] + 1):
            self.assertEqual(settings.finish(self.home, pending["id"], True, self.runner)["status"], "reverted")

    def test_second_preview_is_rejected(self):
        self.apply()
        with self.assertRaises(ForgeError):
            self.apply()

    def test_failed_watchdog_spawn_restores_files(self):
        self.spawn.side_effect = OSError("Cannot spawn watchdog")
        with self.assertRaises(OSError):
            self.apply()
        self.assertFalse((self.home / ".config/forge/desktop.json").exists())
        self.assertIsNone(settings.read_pending(self.home))

    def test_failed_reload_restores_files(self):
        replies = iter((SimpleNamespace(stdout="error"), SimpleNamespace(stdout="ok")))
        self.runner.side_effect = lambda command, **kwargs: next(replies) if command[1] == "reload" else self.respond(command, **kwargs)
        with self.assertRaises(ForgeError):
            self.apply()
        self.assertIsNone(settings.read_pending(self.home))
        self.assertFalse((self.home / ".config/forge/desktop.json").exists())

    def test_mode_change_dispatches_and_persists(self):
        self.value["tiling"] = "windows"
        pending = self.apply()
        self.assertTrue(pending["mode_changed"])
        self.assertEqual(self.runner.call_args.args[0][1], "dispatch")
        self.assertEqual(settings.current(self.home, self.connected, self.runner)["tiling"], "windows")

    def test_external_edits_are_preserved(self):
        pending = self.apply()
        path = self.home / ".config/hypr/monitors.local.lua"
        path.write_text("return {}\n")
        outcome = settings.finish(self.home, pending["id"], False, self.runner)
        self.assertEqual(outcome["status"], "reverted-with-conflicts")
        self.assertEqual(outcome["conflicts"], [".config/hypr/monitors.local.lua"])
        self.assertEqual(path.read_text(), "return {}\n")
        self.assertIsNone(settings.read_pending(self.home))
        self.assertEqual(settings.read_result(self.home), outcome)
        self.assertEqual(self.runner.call_args.args[0], ["hyprctl", "reload"])
        self.apply()
        self.assertIsNone(settings.read_result(self.home))

    def test_watchdog_result_survives_shell_restart(self):
        pending = self.apply()
        outcome = settings.finish(self.home, pending["id"], False, self.runner)
        self.assertEqual(settings.read_result(self.home), outcome)
        self.assertEqual(outcome["status"], "reverted")

    def test_confirm_records_kept_result(self):
        pending = self.apply()
        settings.finish(self.home, pending["id"], True, self.runner)
        self.assertEqual(settings.read_result(self.home)["status"], "kept")

    def test_unknown_preview_is_ignored(self):
        pending = self.apply()
        self.assertEqual(settings.finish(self.home, "unknown", False, self.runner)["status"], "unchanged")
        self.assertEqual(settings.read_pending(self.home)["id"], pending["id"])

    def test_watchdog_retries_busy_lock(self):
        pending = self.apply()
        with patch.object(settings.time, "time", return_value=pending["deadline"] + 1), patch.object(settings.time, "sleep") as sleep, patch.object(settings, "finish", side_effect=[ForgeError("Another Forge operation is running"), {"status": "reverted"}]) as finish:
            self.assertEqual(settings.watch(self.home, pending["id"])["status"], "reverted")
            self.assertEqual(finish.call_count, 2)
            sleep.assert_called_once_with(1)

    def test_current_preserves_actual_refresh(self):
        self.assertEqual(self.value["outputs"][0]["mode"], "1920x1080@120.00")

    def test_query_reflects_external_scale_changes(self):
        self.apply()
        self.connected[0]["scale"] = 1.5
        self.assertEqual(settings.current(self.home, self.connected, self.runner)["outputs"][0]["scale"], 1.5)

    def test_unplugged_display_preferences_and_primary_survive_apply(self):
        self.value["outputs"][0].update(x=-1920, y=100, rotation=2, vrr=2)
        first = self.apply()
        settings.finish(self.home, first["id"], True, self.runner)
        laptop = self.connected[1:]
        draft = settings.current(self.home, laptop, self.runner)
        self.assertEqual([item["name"] for item in draft["outputs"]], ["eDP-1"])
        self.assertEqual(draft["primary"], "eDP-1")
        draft["tiling"] = "windows"
        second = settings.apply(draft, self.home, laptop, self.runner, self.spawn)
        stored = settings.saved_settings(self.home)
        self.assertEqual(stored["primary"], "HDMI-A-1")
        self.assertEqual(stored["outputs"][0], self.value["outputs"][0])
        self.assertIn('HDMI-A-1', (self.home / ".config/hypr/monitors.local.lua").read_text())
        self.assertEqual(settings.current(self.home, self.connected, self.runner)["primary"], "HDMI-A-1")
        settings.finish(self.home, second["id"], False, self.runner)
        self.assertEqual(settings.saved_settings(self.home), self.value)

    def test_connected_main_display_can_be_changed(self):
        first = self.apply()
        settings.finish(self.home, first["id"], True, self.runner)
        self.value["primary"] = "eDP-1"
        self.apply()
        self.assertEqual(settings.saved_settings(self.home)["primary"], "eDP-1")

    def test_preserved_tiling_edit_overrides_stale_json(self):
        self.value["tiling"] = "windows"
        first = self.apply()
        settings.finish(self.home, first["id"], True, self.runner)
        self.value["tiling"] = "caelestia"
        second = self.apply()
        path = self.home / ".config/hypr/tiling.local.lua"
        path.write_text('return "caelestia"\n\n')
        result = settings.finish(self.home, second["id"], False, self.runner)
        self.assertEqual(result["status"], "reverted-with-conflicts")
        self.assertEqual(settings.saved_settings(self.home)["tiling"], "windows")
        self.assertEqual(settings.current(self.home, self.connected, self.runner)["tiling"], "caelestia")
        self.value["tiling"] = "windows"
        third = self.apply()
        self.assertTrue(third["mode_changed"])
        self.assertEqual(self.runner.call_args.args[0][1], "dispatch")

    def test_unknown_active_mode_blocks_changes(self):
        self.active_mode = "unavailable"
        with self.assertRaisesRegex(ForgeError, "active Forge tiling"):
            self.apply()
        self.spawn.assert_not_called()
        self.assertFalse((self.home / ".config/forge/desktop.json").exists())

    def test_corrupt_remembered_output_is_not_rewritten(self):
        first = self.apply()
        settings.finish(self.home, first["id"], True, self.runner)
        path = self.home / ".config/forge/desktop.json"
        invalid = copy.deepcopy(self.value)
        invalid["outputs"][0]["scale"] = 99
        path.write_text(json.dumps(invalid))
        with self.assertRaises(ForgeError):
            self.apply()
        self.assertEqual(json.loads(path.read_text()), invalid)
