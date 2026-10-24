import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.boot import build, configuration, esp_uuid, font_name, main, password_hash, theme
from forge.manifest import ForgeError


class BootTests(unittest.TestCase):
    def test_uuid_validation_prevents_grub_injection(self):
        self.assertEqual(esp_uuid("abcd-1234"), "ABCD-1234")
        for value in (None, "", "/dev/nvme0n1p1", "abcd-1234;reboot", "ABCD-1234\n", "1234", "${root}"):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                esp_uuid(value)

    def test_hash_uses_grub_pbkdf2_and_random_salts(self):
        password = "a-distinct-test-password"
        salt = bytes(range(32))
        result = password_hash(password, salt)
        self.assertEqual(result.split(".")[-1], hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000).hex().upper())
        self.assertNotIn(password, result)
        self.assertNotEqual(password_hash(password), password_hash(password))

    def test_boot_password_keyboard_and_length_constraints(self):
        for password in ("short", "x" * 129, "password-with-\n", "password-with-\x7f", "password-with-ä"):
            with self.subTest(password=password), self.assertRaises(ForgeError):
                password_hash(password)

    def test_menu_stays_behind_authentication(self):
        result = configuration("1234-abcd", "5678-ef01", password_hash("test-boot-password"))
        self.assertLess(result.index("if authenticate forge"), result.index("menuentry"))
        self.assertIn("while true; do", result)
        self.assertIn("--users forge", result)
        self.assertNotIn("--unrestricted", result)
        self.assertIn("set timeout=-1", result)
        self.assertNotIn("test-boot-password", result)
        self.assertIn("/EFI/Microsoft/Boot/bootmgfw.efi", result)
        self.assertIn("/EFI/systemd/systemd-bootx64.efi", result)
        self.assertNotIn("efibootmgr", result)
        self.assertNotIn("grub-install", result)

    def test_missing_loader_cannot_accidentally_boot_previous_kernel(self):
        result = configuration("1234-abcd", "5678-ef01", password_hash("test-boot-password"))
        self.assertEqual(result.count("                boot\n            fi"), 2)
        self.assertEqual(result.count("No disk was changed"), 2)

    def test_hash_and_font_name_reject_script_content(self):
        with self.assertRaises(ForgeError):
            configuration("1234-abcd", "5678-ef01", "injected\nreboot")
        with self.assertRaises(ForgeError):
            theme('font"\n+ label {}')

    def test_grub_font_name_is_read_from_binary_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "font.pf2"
            path.write_bytes(b"FILE\x00\x00\x00\x04PFF2NAME\x00\x00\x00\x15ForgeMono Regular 28\x00")
            self.assertEqual(font_name(path), "ForgeMono Regular 28")
            path.write_bytes(b"not a valid font")
            with self.assertRaises(ForgeError):
                font_name(path)

    def test_build_requires_tools_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.boot.shutil.which", return_value=None):
            output = Path(directory) / "output"
            with self.assertRaisesRegex(ForgeError, "grub"):
                build(output, "1234-abcd", "5678-ef01", password_hash("test-boot-password"))
            self.assertFalse(output.exists())

    def test_noninteractive_build_never_reads_password(self):
        with patch("sys.argv", ["forge-boot", "--output", "unused", "--forge-uuid", "1234-abcd", "--windows-uuid", "5678-ef01"]), patch("forge.boot.sys.stdin.isatty", return_value=False), patch("forge.boot.getpass.getpass") as password, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(), 1)
            password.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow required")
    def test_build_stages_only_new_files_and_hash_not_plaintext(self):
        def runner(command, **kwargs):
            if command[0] == "grub-mkfont":
                target = next(value.split("=", 1)[1] for value in command if value.startswith("--output="))
                Path(target).write_bytes(b"FILE\x00\x00\x00\x04PFF2NAME\x00\x00\x00\x15ForgeMono Regular 28\x00")
            if command[0] == "grub-mkstandalone":
                target = next(value.split("=", 1)[1] for value in command if value.startswith("--output="))
                Path(target).write_bytes(b"fixture-efi")
            return subprocess.CompletedProcess(command, 0, "", "")
        with tempfile.TemporaryDirectory() as directory, patch("forge.boot.shutil.which", return_value="fixture"):
            root = Path(directory)
            output = build(root / "new", "1234-abcd", "5678-ef01", password_hash("test-secret-boot-password"), runner=runner)
            self.assertEqual((output / "EFI/Forge/forge-x64.efi").read_bytes(), b"fixture-efi")
            self.assertTrue((output / "sddm/forge-overdrive/Main.qml").is_file())
            self.assertNotIn("test-secret-boot-password", (output / "grub.cfg").read_text())
            plan = json.loads((output / "plan.json").read_text())
            self.assertFalse(plan["boot_order_changed"])
            self.assertEqual(plan["activation"], "not-installed")
            with self.assertRaisesRegex(ForgeError, "existing"):
                build(output, "1234-abcd", "5678-ef01", password_hash("test-secret-boot-password"), runner=runner)
            self.assertEqual([path.name for path in root.iterdir()], ["new"])

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow required")
    def test_failed_build_does_not_publish_partial_package(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.boot.shutil.which", return_value="fixture"):
            root = Path(directory)
            with self.assertRaises(subprocess.CalledProcessError):
                build(root / "new", "1234-abcd", "5678-ef01", password_hash("test-secret-boot-password"), runner=lambda command, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, command)))
            self.assertEqual(list(root.iterdir()), [])

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow required")
    def test_original_artwork_and_preview_render(self):
        from PIL import Image
        from forge.boot_art import render
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render(root)
            for name in ("auth.png", "selector.png", "design-preview.png"):
                with Image.open(root / name) as image:
                    self.assertEqual(image.size, (1920, 1080))
            self.assertNotEqual((root / "selector.png").read_bytes(), (root / "design-preview.png").read_bytes())
            self.assertEqual(len(list(root.glob("select_*.png"))), 9)


if __name__ == "__main__":
    unittest.main()
