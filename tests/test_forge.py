import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.__main__ import main
from forge.manifest import ForgeError, load_manifest, make_plan, relative_path, select_stages
from forge.runtime import execute, preflight, restore
from forge.storage import Deployment, safe_target, write_json


ROOT = Path(__file__).resolve().parent.parent


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(ROOT)

    def test_default_plan_has_no_unreleased_stages(self):
        plan = make_plan(self.manifest, None)
        self.assertTrue(plan["stages"])
        self.assertFalse(set(plan["stages"]) & set(plan["pending"]))
        self.assertEqual(plan["commands"][0][:5], ["sudo", "pacman", "-Syu", "--needed", "--"])
        self.assertNotIn("--noconfirm", plan["commands"][0])

    def test_pending_stage_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        next(stage for stage in manifest["stages"] if stage["id"] == "shell")["status"] = "pending"
        with self.assertRaisesRegex(ForgeError, "not released"):
            select_stages(manifest, ["shell"])

    def test_unknown_stage_is_rejected(self):
        with self.assertRaisesRegex(ForgeError, "Unknown"):
            select_stages(self.manifest, ["unknown"])

    def test_dependencies_are_selected_once_in_order(self):
        manifest = copy.deepcopy(self.manifest)
        for stage in manifest["stages"]:
            stage["status"] = "ready"
        selected = select_stages(manifest, ["shell", "base", "shell"])
        self.assertEqual([s["id"] for s in selected], ["base", "hardware", "compositor", "shell"])

    def test_unsafe_paths_are_rejected(self):
        for value in ("../secret", "/etc/shadow", "C:/Windows", ".config/../../x", "x\\y", "", "./x", "x\ny", "x\x00y"):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                relative_path(value)

    def test_invalid_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = copy.deepcopy(self.manifest)
            for stage in manifest["stages"]:
                stage["files"] = []
            manifest["stages"][0]["packages"].append("--overwrite=*")
            write_json(Path(folder) / "project.json", manifest)
            with self.assertRaisesRegex(ForgeError, "package"):
                load_manifest(Path(folder))

    def test_dependency_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = copy.deepcopy(self.manifest)
            for stage in manifest["stages"]:
                stage["files"] = []
            manifest["stages"][0]["requires"] = ["shell"]
            write_json(Path(folder) / "project.json", manifest)
            with self.assertRaisesRegex(ForgeError, "dependency"):
                load_manifest(Path(folder))

    def test_plan_is_read_only_and_runs_on_host(self):
        result = subprocess.run([sys.executable, "-m", "forge", "--plan", "--json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["project"], "hyprland-forge")

    def test_apply_is_refused_on_non_linux(self):
        with patch("forge.runtime.platform.system", return_value="Windows"):
            with self.assertRaisesRegex(ForgeError, "Arch Linux"):
                preflight()

    def test_apply_as_root_is_refused(self):
        with patch("forge.runtime.platform.system", return_value="Linux"), patch("forge.runtime.platform.machine", return_value="x86_64"), patch("forge.runtime.os.geteuid", return_value=0, create=True):
            with self.assertRaisesRegex(ForgeError, "normal user"):
                preflight()


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.user = self.root / "user"
        self.state = self.user / ".local/state/hyprland-forge"
        self.transaction = self.state / "transactions/test"
        self.user.mkdir()
        (self.source / "configs").mkdir(parents=True)
        (self.source / "configs/example").write_text("new content", encoding="utf-8")
        self.files = [{"source": "configs/example", "target": ".config/forge/example"}]
        self.target = self.user / self.files[0]["target"]

    def existing(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text("original content", encoding="utf-8")

    def test_replace_backup_and_restore(self):
        self.existing()
        deployment = Deployment(self.user, self.transaction)
        deployment.apply(self.files, self.source)
        self.assertEqual(self.target.read_text(), "new content")
        self.assertEqual((self.transaction / "backup/0").read_text(), "original content")
        self.assertEqual(deployment.rollback(), [])
        self.assertEqual(self.target.read_text(), "original content")
        self.assertEqual(deployment.rollback(), [])

    def test_fresh_file_removed_by_rollback(self):
        deployment = Deployment(self.user, self.transaction)
        deployment.apply(self.files, self.source)
        self.assertTrue(self.target.is_file())
        deployment.rollback()
        self.assertFalse(self.target.exists())

    def test_existing_identical_file_not_claimed(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text("new content", encoding="utf-8")
        deployment = Deployment(self.user, self.transaction)
        deployment.apply(self.files, self.source)
        self.assertEqual(deployment.entries, [])
        deployment.rollback()
        self.assertEqual(self.target.read_text(), "new content")

    def test_user_edits_survive_rollback(self):
        self.existing()
        deployment = Deployment(self.user, self.transaction)
        deployment.apply(self.files, self.source)
        self.target.write_text("my changes", encoding="utf-8")
        self.assertEqual(deployment.rollback(), [self.files[0]["target"]])
        self.assertEqual(self.target.read_text(), "my changes")

    def test_corrupt_backup_is_refused(self):
        self.existing()
        deployment = Deployment(self.user, self.transaction)
        deployment.apply(self.files, self.source)
        (self.transaction / "backup/0").write_text("corrupt", encoding="utf-8")
        with self.assertRaisesRegex(ForgeError, "integrity"):
            deployment.rollback()
        self.assertEqual(self.target.read_text(), "new content")

    def test_rollback_after_reloading_journal(self):
        self.existing()
        Deployment(self.user, self.transaction).apply(self.files, self.source)
        self.assertEqual(Deployment(self.user, self.transaction).rollback(), [])
        self.assertEqual(self.target.read_text(), "original content")

    def test_escape_target_is_refused(self):
        with self.assertRaises(ForgeError):
            safe_target(self.user, "../outside")

    def test_directory_target_is_refused(self):
        self.target.mkdir(parents=True)
        with self.assertRaisesRegex(ForgeError, "regular file"):
            Deployment(self.user, self.transaction).apply(self.files, self.source)

    def test_symlink_parent_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.user / ".config").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation requires OS privileges")
        with self.assertRaises(ForgeError):
            Deployment(self.user, self.transaction).apply(self.files, self.source)
        self.assertEqual(list(outside.iterdir()), [])

    def test_all_targets_preflight_before_first_write(self):
        bad_target = self.user / ".config/bad"
        bad_target.mkdir(parents=True)
        files = self.files + [{"source": "configs/example", "target": ".config/bad"}]
        with self.assertRaises(ForgeError):
            Deployment(self.user, self.transaction).apply(files, self.source)
        self.assertFalse(self.target.exists())

    def test_source_escape_is_refused(self):
        with self.assertRaises(ForgeError):
            Deployment(self.user, self.transaction).apply([{"source": "../outside", "target": ".config/x"}], self.source)

    def test_failure_between_journal_and_write_restores_safely(self):
        self.existing()
        deployment = Deployment(self.user, self.transaction)
        from forge.storage import atomic_write

        def fail_target(path, content, mode=0o600):
            if path == self.target:
                raise OSError("simulated write failure")
            atomic_write(path, content, mode)

        with patch("forge.storage.atomic_write", side_effect=fail_target):
            with self.assertRaises(OSError):
                deployment.apply(self.files, self.source)
        self.assertEqual(deployment.rollback(), [])
        self.assertEqual(self.target.read_text(), "original content")

    def test_failed_package_transaction_does_not_deploy_files(self):
        self.existing()
        plan = {"commands": [["pacman", "-Syu"]], "files": self.files}

        def failed(command, check):
            raise subprocess.CalledProcessError(1, command)

        with self.assertRaises(subprocess.CalledProcessError):
            execute(plan, self.source, self.user, self.state, runner=failed)
        records = list((self.state / "transactions").glob("*/transaction.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_text())["status"], "failed")
        self.assertEqual(self.target.read_text(), "original content")
        self.assertFalse((self.state / "latest.json").exists())

    def test_transaction_completion_and_restore(self):
        self.existing()
        commands = []
        plan = {"commands": [["pacman", "-Syu"]], "files": self.files}
        transaction_id = execute(plan, self.source, self.user, self.state, runner=lambda command, check: commands.append(command))
        self.assertEqual(commands, plan["commands"])
        self.assertEqual(json.loads((self.state / "latest.json").read_text())["id"], transaction_id)
        self.assertEqual(restore(transaction_id, self.user, self.state), [])
        self.assertEqual(self.target.read_text(), "original content")

    def test_restore_rejects_path_traversal(self):
        with self.assertRaises(ForgeError):
            restore("../../outside", self.user, self.state)

    def test_execute_refuses_state_outside_home(self):
        with self.assertRaises(ForgeError):
            execute({"commands": [], "files": self.files}, self.source, self.user, self.root / "outside")
        self.assertFalse((self.root / "outside").exists())

    def test_restore_refuses_linked_transaction_records(self):
        transaction_id = execute({"commands": [], "files": self.files}, self.source, self.user, self.state)
        record = self.state / "transactions" / transaction_id / "transaction.json"
        outside = self.root / "outside.json"
        outside.write_bytes(record.read_bytes())
        try:
            link = self.root / "check-link"
            link.symlink_to(outside)
            link.unlink()
        except OSError:
            self.skipTest("Symlinks unavailable")
        record.unlink()
        record.symlink_to(outside)
        with self.assertRaises(ForgeError):
            restore(transaction_id, self.user, self.state)
        self.assertEqual(self.target.read_text(), "new content")


if __name__ == "__main__":
    unittest.main()
