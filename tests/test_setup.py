import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import patch

from forge.bootstrap import allow_sudo, enable_multilib
from forge.live import configuration, first_login, stage_command
from forge.manifest import ForgeError, load_manifest, make_plan
from forge.setup import LoggedRunner, cache_installer, confirm, run, with_gaming


ROOT = Path(__file__).resolve().parent.parent


class SetupTests(unittest.TestCase):
    def test_invalid_answer_reprompts_and_empty_uses_default(self):
        answers = iter(["maybe", "YES", ""])
        self.assertTrue(confirm("Continue?", reader=lambda _: next(answers)))
        self.assertFalse(confirm("Restart?", default=False, reader=lambda _: next(answers)))

    def test_cancel_has_no_sudo_or_home_writes(self):
        with tempfile.TemporaryDirectory() as directory, patch("forge.setup.sys.stdin.isatty", return_value=True), patch("forge.setup.preflight"), patch("forge.setup.virtualization", return_value="oracle"), patch("forge.setup.resolve_plan", side_effect=lambda p, **k: {**p, "profile": "virtual-machine"}), patch("forge.setup.resolve_login", side_effect=lambda p, **k: p), patch("builtins.input", return_value="n"), patch("forge.setup.subprocess.run") as process, patch("forge.setup.Path.home", return_value=Path(directory)):
            self.assertEqual(run(ROOT), 0)
            process.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_headless_setup_never_prepares_system(self):
        with patch("forge.setup.sys.stdin.isatty", return_value=False), patch("forge.setup.preflight") as preflight:
            with self.assertRaisesRegex(ForgeError, "interactive"):
                run(ROOT)
            preflight.assert_not_called()

    def test_gaming_preserves_kernel_headers_and_prepares_multilib_first(self):
        plan = {"packages": ["linux-lts-headers"], "profile": "laptop"}
        result = with_gaming(plan, ROOT)
        self.assertIn("linux-lts-headers", result["packages"])
        self.assertIn("lib32-nvidia-utils", result["packages"])
        self.assertEqual(result["commands"][0][-1], "--multilib")
        self.assertEqual(result["commands"][1][:3], ["sudo", "pacman", "-Syu"])

    def test_vm_gaming_excludes_physical_gpu_libraries(self):
        result = with_gaming({"packages": [], "profile": "virtual-machine"}, ROOT)
        self.assertNotIn("lib32-nvidia-utils", result["packages"])
        self.assertIn("lib32-mesa", result["packages"])
        self.assertIn("vulkan-swrast", result["packages"])
        self.assertIn("lib32-vulkan-swrast", result["packages"])

    def test_cached_installer_is_complete_without_checkout_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = cache_installer(ROOT, Path(directory), load_manifest(ROOT))
            self.assertTrue((target / "forge/setup.py").is_file())
            self.assertTrue((target / "install-online.sh").is_file())
            self.assertFalse((target / ".git").exists())
            self.assertEqual(load_manifest(target)["release"], load_manifest(ROOT)["release"])

    def test_multilib_preserves_and_backs_up_existing_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conf = root / "pacman.conf"
            original = "[options]\nSigLevel = Required\n[core]\nInclude = /etc/pacman.d/mirrorlist\n"
            conf.write_text(original)
            backup = enable_multilib(conf, root / "backups")
            self.assertEqual(backup.read_text(), original)
            self.assertTrue(conf.read_text().startswith(original))
            self.assertIsNone(enable_multilib(conf, root / "backups"))
            self.assertEqual(len(list((root / "backups").iterdir())), 1)

    def test_custom_active_multilib_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pacman.conf"
            original = "[multilib]\nServer = https://custom.example/$repo/os/$arch\n"
            path.write_text(original)
            self.assertIsNone(enable_multilib(path, Path(directory) / "backups"))
            self.assertEqual(path.read_text(), original)

    def test_invalid_sudo_rule_is_never_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sudoers.d"
            with self.assertRaises(subprocess.CalledProcessError):
                allow_sudo("forge", root, runner=lambda c, **k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, c)))
            self.assertEqual(list(root.iterdir()), [])
            for name in ("root;reboot", "-bad", "../escape", "name\nALL"):
                with self.assertRaises(ValueError):
                    allow_sudo(name, root)

    def test_live_seed_does_not_choose_or_wipe_any_disk(self):
        version = "0.14.0"
        url = f"https://github.com/hirsu-dev/hyprland-forge/releases/download/v{version}/hyprland-forge-{version}.tar.gz"
        seed = configuration(version, url, "a" * 64)
        self.assertNotIn("disk_config", seed)
        self.assertNotIn("auth_config", seed)
        self.assertNotIn("silent", seed)
        self.assertEqual(seed["network_config"], {"type": "nm"})
        self.assertIn("sudo", seed["packages"])
        with self.assertRaises(ForgeError):
            stage_command(version, "https://wrong.example/a", "a" * 64)

    def test_first_login_is_only_for_a_local_normal_user_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = first_login(Path("/opt/hyprland-forge-0.14.0"), root)
            self.assertIn("SSH_CONNECTION", script.read_text())
            self.assertIn("setup-complete", script.read_text())
            self.assertEqual(first_login(Path("/opt/hyprland-forge-0.14.0"), root), script)
            script.write_text("existing configuration")
            with self.assertRaises(ForgeError):
                first_login(Path("/opt/hyprland-forge-0.14.0"), root)

    @unittest.skipUnless(sys.platform == "linux", "POSIX links required")
    def test_system_config_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.write_text("keep")
            link = root / "pacman.conf"
            link.symlink_to(real)
            with self.assertRaises(ValueError):
                enable_multilib(link, root / "backup")
            self.assertEqual(real.read_text(), "keep")

    def test_package_failure_is_logged_and_raised(self):
        stream = io.StringIO()
        class Process:
            stdout = ["package conflict\n"]
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def wait(self): return 1
        with patch("forge.setup.subprocess.Popen", return_value=Process()):
            with self.assertRaises(subprocess.CalledProcessError):
                LoggedRunner(stream)(["sudo", "pacman", "-Syu", "--needed", "--", "hyprland"], check=True)
        self.assertIn("package conflict", stream.getvalue())

    def test_guided_install_publishes_success_only_after_deployment(self):
        self.guided_install(False)

    def test_failed_guided_install_keeps_log_without_success_marker(self):
        self.guided_install(True)

    def guided_install(self, fail):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            home = Path(directory)
            def runner(command, **kwargs):
                if fail and "pacman" in command:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0, "", "")
            for name, kwargs in [
                ("forge.setup.sys.stdin.isatty", {"return_value": True}),
                ("forge.setup.preflight", {}),
                ("forge.setup.resolve_plan", {"side_effect": lambda p, **k: {**p, "profile": "virtual-machine"}}),
                ("forge.setup.resolve_login", {"side_effect": lambda p, **k: p}),
                ("forge.setup.Path.home", {"return_value": home}),
                ("forge.setup.lock", {"side_effect": lambda _: nullcontext()}),
                ("forge.setup.LoggedRunner", {"return_value": runner}),
                ("forge.setup.subprocess.run", {"side_effect": runner}),
                ("builtins.input", {"side_effect": ["y", "n", "n"]}),
            ]:
                stack.enter_context(patch(name, **kwargs))
            if fail:
                with self.assertRaises(subprocess.CalledProcessError):
                    run(ROOT, "virtual-machine")
            else:
                self.assertEqual(run(ROOT, "virtual-machine"), 0)
            state = home / ".local/state/hyprland-forge"
            self.assertEqual((state / "setup-complete").exists(), not fail)
            records = list((state / "transactions").glob("*/transaction.json"))
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0].read_text())["status"], "failed" if fail else "complete")
            self.assertTrue(list((state / "logs").glob("*.log")))
            self.assertEqual((home / ".config/hypr/hyprland.lua").exists(), not fail)


@unittest.skipUnless(sys.platform == "linux" and Path("/etc/arch-release").is_file(), "Arch shell required")
class BootstrapTerminalTests(unittest.TestCase):
    def test_piped_default_bootstrap_restores_terminal_input(self):
        import fcntl
        import hashlib
        import pty
        import tarfile
        import termios
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package/hyprland-forge"
            package.mkdir(parents=True)
            (package / "install.sh").write_text('#!/bin/bash\n[[ -t 0 ]] || exit 81\nprintf "TTY_OK %s\\n" "$*"\n')
            archive = root / "fixture.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                output.add(package, arcname="hyprland-forge")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps([{"tag_name": "v0.14.0", "assets": [{"name": "hyprland-forge-0.14.0.tar.gz", "digest": "sha256:" + digest}]}]))
            binaries = root / "bin"
            binaries.mkdir()
            (binaries / "curl").write_text('#!/bin/bash\nif [[ "$*" == *api.github.com* ]]; then cat "$FIXTURE_ROOT/metadata.json"; else cp "$FIXTURE_ROOT/fixture.tar.gz" "${@: -1}"; fi\n')
            for name in ("sudo", "pacman"):
                (binaries / name).write_text('#!/bin/bash\nexit 87\n')
            for script in binaries.iterdir():
                script.chmod(0o755)
            master, slave = pty.openpty()
            def session():
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            command = 'cat "$BOOTSTRAP" | bash -s -- --profile virtual-machine'
            process = subprocess.Popen(["bash", "-c", command], stdin=slave, stdout=slave, stderr=slave, preexec_fn=session, env={**os.environ, "PATH": str(binaries) + ":" + os.environ["PATH"], "FIXTURE_ROOT": str(root), "BOOTSTRAP": str(ROOT / "install-online.sh")})
            os.close(slave)
            try:
                self.assertEqual(process.wait(timeout=20), 0)
                output = b""
                while True:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                self.assertIn(b"TTY_OK --setup --profile virtual-machine", output)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)


if __name__ == "__main__":
    unittest.main()
