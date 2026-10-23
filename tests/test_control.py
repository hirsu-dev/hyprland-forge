import contextlib
import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.control import ACTIONS, DEFAULTS, STATE, TARGET, apply, backups, dispatch, keybind, load, metrics, network, render, split_fields, validate, wifi_connect
from forge.manifest import ForgeError, load_manifest
from forge.runtime import restore
from forge.capture import destination, geometry, main as capture_main
from forge.wallpaper import command

ROOT = Path(__file__).resolve().parent.parent


class ControlTests(unittest.TestCase):
    def test_independent_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            value = load(home)
            value["wallpapers"]["default"] = "other"
            self.assertEqual(load(home), DEFAULTS)
            self.assertFalse((home / TARGET).exists())

    def test_invalid_preferences(self):
        for value in ([], None, {"extra": 2}, {"sensitivity": True}, {"sensitivity": 1.1}, {"naturalScroll": 1}, {"gaming": "yes"}, {"bindings": {}}, {"profiles": []}, {"profiles": {"../bad": {}}}, {"wallpapers": {"HDMI-1": "relative.png"}}, {"wallpapers": {"../bad": "/tmp/a.png"}}):
            with self.subTest(value=value), self.assertRaises((ForgeError, ValueError)):
                validate(value)

    def test_shortcuts_are_normalized_and_reserved(self):
        self.assertEqual(keybind("SHIFT + SUPER + t"), "SUPER + SHIFT + T")
        for value in ("Q", "SUPER + SUPER + T", "SUPER + x;reboot", "SUPER + a\n", "BAD + A"):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                keybind(value)
        for key in ("SUPER + q", "ALT + Tab", "SUPER + 1", "SUPER + CTRL + V"):
            with self.subTest(key=key), self.assertRaises(ForgeError):
                validate({"bindings": {**DEFAULTS["bindings"], "terminal": key}})
        with self.assertRaises(ForgeError):
            validate({"bindings": {name: "SUPER + T" for name in ACTIONS}})

    def test_lua_rendering_and_gaming_override(self):
        files = render(validate({"gaming": True}))
        self.assertIn('["enabled"] = false', files[".config/hypr/forge/preferences.lua"])
        self.assertTrue(files[".config/hypr/forge/shortcuts.lua"].startswith("return {"))
        self.assertNotIn("animations", render(validate({}))[".config/hypr/forge/preferences.lua"])

    def test_corrupt_or_oversized_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / TARGET
            path.parent.mkdir(parents=True)
            for content in ("bad", " " * 131073):
                path.write_text(content)
                with self.assertRaises((ForgeError, ValueError)):
                    load(home)
                self.assertEqual(path.read_text(), content)

    def test_apply_merges_rollback_and_conflicts(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.control.lock", side_effect=lambda path: contextlib.nullcontext()):
            home = Path(directory)
            runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "ok", "")
            first = apply(home, {"sensitivity": 0.3}, runner)
            second = apply(home, {"gaming": True}, runner)
            self.assertEqual(load(home)["sensitivity"], 0.3)
            self.assertTrue(load(home)["gaming"])
            self.assertEqual(len(backups(home)), 2)
            self.assertEqual(restore(second["transaction"], home, home / STATE), [])
            self.assertFalse(load(home)["gaming"])
            (home / TARGET).write_text("external edit")
            self.assertEqual(restore(first["transaction"], home, home / STATE), [TARGET])

    def test_failed_reload_rolls_back_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.control.lock", side_effect=lambda path: contextlib.nullcontext()):
            home = Path(directory)
            runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failure")
            with self.assertRaises(ForgeError):
                apply(home, {"gaming": True}, runner)
            self.assertEqual(load(home), DEFAULTS)

    def test_escaped_network_fields(self):
        self.assertEqual(split_fields(r"a\:b:c\\d:e"), ["a:b", "c\\d", "e"])
        def runner(command, **kwargs):
            result = r"*:Cafe\:Forge:AA\:BB\:CC\:DD\:EE\:FF:75:WPA2:wlan0" if "IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE" in command else "enabled" if command[1:] == ["radio", "wifi"] else ""
            return subprocess.CompletedProcess(command, 0, result, "")
        result = network(runner)
        self.assertEqual(result["networks"][0]["ssid"], "Cafe:Forge")
        self.assertEqual(result["networks"][0]["bssid"], "AA:BB:CC:DD:EE:FF")
        self.assertTrue(result["wifi"])

    def test_wifi_password_never_enters_arguments_and_is_removed(self):
        calls, secrets = [], []
        def runner(command, **kwargs):
            calls.append(command)
            if "passwd-file" in command:
                secret = Path(command[-1])
                self.assertIn("super-secret", secret.read_text())
                secrets.append(secret)
            return subprocess.CompletedProcess(command, 0, "", "")
        network_value = {"networks": [{"bssid": "AA:BB:CC:DD:EE:FF", "security": "WPA2", "ssid": "Forge", "device": "wlan0"}]}
        with patch("forge.control.network", return_value=network_value):
            wifi_connect({"bssid": "AA:BB:CC:DD:EE:FF", "password": "super-secret"}, runner)
        self.assertNotIn("super-secret", str(calls))
        self.assertTrue(secrets)
        self.assertFalse(secrets[0].exists())

    def test_wifi_rejects_unsupported_security_and_invalid_password(self):
        for security, password in (("WPA3", "super-secret"), ("WPA2 802.1X", "super-secret"), ("WPA2", "tiny"), ("WPA2", "bad\nsecret")):
            with self.subTest(security=security), patch("forge.control.network", return_value={"networks": [{"bssid": "aa", "security": security}]}), self.assertRaises(ForgeError):
                wifi_connect({"bssid": "aa", "password": password})

    def test_mutating_requests_need_preflight(self):
        with patch("forge.control.preflight", side_effect=ForgeError("blocked")):
            for action in ("save", "wifi-power", "restore", "bluetooth-power", "connection-up"):
                with self.subTest(action=action), self.assertRaisesRegex(ForgeError, "blocked"):
                    dispatch({"action": action}, Path("unused"))

    def test_invalid_requests_are_refused(self):
        with patch("forge.control.preflight"):
            for request in ([], {}, {"action": "connection-up", "uuid": "--bad"}, {"action": "bluetooth-connect", "address": "bad"}, {"action": "wifi-power", "enabled": "yes"}):
                with self.subTest(request=request), self.assertRaises(ForgeError):
                    dispatch(request, Path("unused"))

    def test_update_preview_uses_only_checkupdates(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 2, "", "")
        self.assertEqual(dispatch({"action": "updates"}, Path("unused"), runner)["updates"], [])
        self.assertEqual(calls, [["checkupdates"]])

    def test_cpu_memory_metrics_and_missing_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 400 kB\n")
            (root / "stat").write_text("cpu 10 0 10 60 20 0 0 0 0 0\n")
            def missing(*args, **kwargs):
                raise FileNotFoundError()
            value = metrics(root, root, missing)
            self.assertEqual((value["cpuTotal"], value["cpuIdle"], value["memoryUsed"]), (100, 80, 600))
            self.assertIsNone(value["gpu"])

    def test_capture_geometry_and_cancellation(self):
        runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "-10,0 100x200\n", "")
        self.assertEqual(geometry("region", runner), ["-g", "-10,0 100x200"])
        self.assertEqual(geometry("desktop", runner), [])
        self.assertIsNone(geometry("region", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "")))
        with self.assertRaises(ForgeError):
            geometry("invalid", runner)

    def test_capture_paths_unique_and_under_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            first, second = destination(home), destination(home)
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, home / "Pictures/Forge")
            self.assertEqual(destination(home, True).suffix, ".mp4")

    def test_wallpaper_arguments_do_not_invoke_a_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            image = home / "image ; literal.png"
            image.touch()
            arguments = command(home, {"wallpapers": {"HDMI-1": str(image)}})
            self.assertIn(str(image), arguments)
            self.assertNotIn("sh", arguments)

    def test_all_new_assets_are_deployed(self):
        manifest = load_manifest(ROOT)
        sources = {entry["source"] for stage in manifest["stages"] for entry in stage["files"]}
        for name in ("Alerts", "Hub", "Hud", "Overview", "NotificationCard", "NotificationPopups"):
            self.assertIn("configs/quickshell/forge/" + name + ".qml", sources)
        for name in ("control", "capture", "wallpaper"):
            self.assertIn("forge/" + name + ".py", sources)

    def test_python_entrypoints_parse(self):
        for path in (ROOT / "configs/bin").iterdir():
            if path.read_text().startswith("#!/usr/bin/env python3"):
                ast.parse(path.read_text(), filename=str(path))

    def test_clipboard_daemon_does_not_inherit_capture_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.png"
            def runner(arguments, **kwargs):
                if arguments[0] == "grim":
                    output.write_bytes(b"fixture")
                elif arguments[0] == "wl-copy":
                    self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
                    self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
                return subprocess.CompletedProcess(arguments, 0, "", "")
            with patch("forge.capture.sys.platform", "linux"), patch("forge.capture.os.geteuid", return_value=1000, create=True), patch("forge.capture.geometry", return_value=[]), patch("forge.capture.destination", return_value=output), patch("forge.capture.time.sleep"), patch("forge.capture.subprocess.run", side_effect=runner), contextlib.redirect_stdout(__import__("io").StringIO()):
                self.assertEqual(capture_main([]), 0)


if __name__ == "__main__":
    unittest.main()
