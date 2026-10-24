import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from forge.bundle import build_bundle
from forge.manifest import ForgeError, load_manifest, make_plan
from forge.runtime import execute, restore


ROOT = Path(__file__).resolve().parent.parent


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.user = self.root / "home"
        self.user.mkdir()
        self.state = self.user / ".local/state/hyprland-forge"
        self.manifest = copy.deepcopy(load_manifest(ROOT))
        for stage in self.manifest["stages"]:
            stage["status"] = "ready"

    def test_whole_install_and_rollback(self):
        plan = make_plan(self.manifest, None)
        original = self.user / ".config/hypr/hyprland.lua"
        original.parent.mkdir(parents=True)
        original.write_text("original")
        calls = []
        transaction = execute(plan, ROOT, self.user, self.state, runner=lambda command, **kwargs: calls.append(command))
        self.assertEqual(calls, plan["commands"])
        for item in plan["files"]:
            self.assertEqual((self.user / item["target"]).read_bytes(), (ROOT / item["source"]).read_bytes())
        self.assertEqual(restore(transaction, self.user, self.state), [])
        self.assertEqual(original.read_text(), "original")
        self.assertEqual([path for path in self.user.rglob("*") if path.is_file() and not path.is_relative_to(self.state)], [original])

    def test_installed_appearance_entrypoint(self):
        execute(make_plan(self.manifest, None), ROOT, self.user, self.state, runner=lambda command, **kwargs: None)
        wrapper = self.user / ".local/bin/forge-appearance"
        import os
        result = subprocess.run([sys.executable, str(wrapper), "--preset", "ember", "--plan"], cwd=self.root, env={**os.environ, "HOME": str(self.user), "USERPROFILE": str(self.user)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)), 4)

    def source_copy(self):
        source = self.root / "source"
        source.mkdir()
        for directory in ("forge", "configs"):
            shutil.copytree(ROOT / directory, source / directory, ignore=shutil.ignore_patterns("__pycache__", "target"))
        for name in ("install.sh", "install-online.sh", "live.sh"):
            shutil.copy2(ROOT / name, source / name)
        (source / "project.json").write_text(json.dumps(self.manifest))
        return source

    def test_compositor_installs_all_session_imports_without_appearance(self):
        execute(make_plan(self.manifest, ["compositor"]), ROOT, self.user, self.state, runner=lambda *a, **k: None)
        library = self.user / ".local/lib/hyprland-forge"
        result = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import forge.session; from forge.hardware import virtualization", str(library)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundle_is_reproducible_and_checked(self):
        source = self.source_copy()
        first = build_bundle(source, self.root / "one", "a" * 40)
        second = build_bundle(source, self.root / "two", "a" * 40)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        checksum = first.with_name(first.name + ".sha256").read_text().split()[0]
        self.assertEqual(checksum, hashlib.sha256(first.read_bytes()).hexdigest())
        with tarfile.open(first) as archive:
            checksums = archive.extractfile("hyprland-forge/SHA256SUMS").read().decode().splitlines()
            for line in checksums:
                expected, name = line.split("  ", 1)
                self.assertEqual(expected, hashlib.sha256(archive.extractfile("hyprland-forge/" + name).read()).hexdigest())
            self.assertFalse(any(".git" in name or "__pycache__" in name for name in archive.getnames()))
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertEqual(member.mtime, 0)

    def test_bundle_rejects_unreleased_stages(self):
        source = self.source_copy()
        self.manifest["stages"][-1]["status"] = "pending"
        (source / "project.json").write_text(json.dumps(self.manifest))
        with self.assertRaises(ForgeError):
            build_bundle(source, self.root / "output", "a" * 40)

    def test_bundle_normalizes_windows_line_endings(self):
        source = self.source_copy()
        first = build_bundle(source, self.root / "one", "a" * 40)
        script = source / "install.sh"
        script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        second = build_bundle(source, self.root / "two", "a" * 40)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_bundle_restages_without_git(self):
        archive_path = build_bundle(self.source_copy(), self.root / "output", "a" * 40)
        unpacked = self.root / "unpacked"
        with tarfile.open(archive_path) as archive:
            archive.extractall(unpacked, filter="data")
        result = subprocess.run([sys.executable, "-m", "forge", "--plan", "--json"], cwd=unpacked / "hyprland-forge", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["pending"], [])
        self.assertIn("appearance", plan["stages"])

    @unittest.skipUnless(sys.platform == "linux", "Linux installer shell required")
    def test_installer_rejects_modified_bundle(self):
        archive_path = build_bundle(self.source_copy(), self.root / "output", "a" * 40)
        unpacked = self.root / "unpacked"
        with tarfile.open(archive_path) as archive:
            archive.extractall(unpacked, filter="data")
        bundle = unpacked / "hyprland-forge"
        clean = subprocess.run(["bash", "install.sh", "--plan", "--json"], cwd=bundle, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        (bundle / "configs/forge/theme.json").write_text("changed")
        modified = subprocess.run(["bash", "install.sh", "--plan", "--json"], cwd=bundle, capture_output=True, text=True)
        self.assertNotEqual(modified.returncode, 0)
        self.assertIn("integrity verification failed", modified.stdout)


if __name__ == "__main__":
    unittest.main()
