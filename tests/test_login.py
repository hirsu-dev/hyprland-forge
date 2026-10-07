import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.login import configure, inventory, resolve_plan, verify_unchanged
from forge.manifest import ForgeError
from forge.runtime import execute, undo_target


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"stages": ["compositor"], "packages": ["hyprland"], "commands": [], "services": [], "files": []}
        self.data = {"state": "not-found", "manager": "", "target": "multi-user.target"}

    def runner(self, command, **kwargs):
        if command[1] == "show":
            return subprocess.CompletedProcess(command, 0, f"LoadState={self.data['state']}\nFragmentPath={self.data['manager']}\n")
        if command[1] == "get-default":
            return subprocess.CompletedProcess(command, 0, self.data["target"] + "\n")
        return subprocess.CompletedProcess(command, 1, "disabled\n")

    def test_inventory(self):
        self.assertEqual(inventory(self.runner), self.data)

    def test_inventory_failure_is_not_a_fresh_install(self):
        with self.assertRaises(ForgeError):
            inventory(lambda command, **kwargs: subprocess.CompletedProcess(command, 1, ""))

    def test_fresh_install_selects_sddm_and_graphical_target(self):
        plan = configure(self.plan, "auto", self.data)
        self.assertIn("sddm", plan["packages"])
        self.assertEqual(plan["services"], ["sddm.service"])
        self.assertEqual(plan["default_target"]["next"], "graphical.target")
        self.assertNotIn("--now", str(plan))
        self.assertNotIn("--force", str(plan))

    def test_graphical_target_needs_no_change(self):
        self.data["target"] = "graphical.target"
        self.assertNotIn("default_target", configure(self.plan, "auto", self.data))

    def test_existing_managers_and_masks_are_preserved(self):
        for state, manager in (("loaded", "/usr/lib/systemd/system/gdm.service"), ("loaded", "/usr/lib/systemd/system/sddm.service"), ("masked", "/dev/null")):
            with self.subTest(state=state, manager=manager):
                data = {**self.data, "state": state, "manager": manager}
                plan = configure(copy.deepcopy(self.plan), "auto", data)
                self.assertEqual(plan["login"]["action"], "preserve")
                self.assertEqual(plan["commands"], [])

    def test_explicit_sddm_never_replaces_other_manager(self):
        self.data.update(state="loaded", manager="/usr/lib/systemd/system/gdm.service")
        with self.assertRaisesRegex(ForgeError, "existing"):
            configure(self.plan, "sddm", self.data)

    def test_custom_default_target_is_preserved(self):
        self.data["target"] = "rescue.target"
        self.assertEqual(configure(self.plan, "auto", self.data)["login"]["action"], "preserve")
        with self.assertRaisesRegex(ForgeError, "custom"):
            configure(copy.deepcopy(self.plan), "sddm", self.data)

    def test_keep_and_base_modes_do_not_probe_host(self):
        with patch("forge.login.inventory", side_effect=AssertionError("must not probe")):
            self.assertNotIn("login", resolve_plan(self.plan, "keep"))
            self.plan["stages"] = ["base"]
            self.assertNotIn("login", resolve_plan(self.plan))

    def test_preview_is_not_executable(self):
        with patch("forge.login.platform.system", return_value="Windows"):
            plan = resolve_plan(self.plan)
        with self.assertRaisesRegex(ForgeError, "regenerate"):
            verify_unchanged(plan, self.runner)

    def test_changed_manager_is_rejected(self):
        plan = configure(self.plan, "auto", copy.deepcopy(self.data))
        self.data.update(state="loaded", manager="/usr/lib/systemd/system/gdm.service")
        with self.assertRaisesRegex(ForgeError, "changed"):
            verify_unchanged(plan, self.runner)

    def test_masked_sddm_is_rejected(self):
        plan = configure(self.plan, "auto", self.data)
        def runner(command, **kwargs):
            if command[1] == "is-enabled":
                return subprocess.CompletedProcess(command, 1, "masked\n")
            return self.runner(command, **kwargs)
        with self.assertRaisesRegex(ForgeError, "masked"):
            verify_unchanged(plan, runner)

    def test_success_enables_login_without_starting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            plan = configure(self.plan, "auto", copy.deepcopy(self.data))
            def runner(command, **kwargs):
                calls.append(command)
                if command[:3] == ["sudo", "systemctl", "set-default"]:
                    self.data["target"] = command[-1]
                return self.runner(command, **kwargs)
            transaction = execute(plan, root, root, root / "state", runner)
            record = json.loads((root / "state/transactions" / transaction / "transaction.json").read_text())
            self.assertEqual(record["status"], "complete")
            self.assertIn(["sudo", "systemctl", "enable", "sddm.service"], calls)
            self.assertEqual(self.data["target"], "graphical.target")
            self.assertFalse(any("--now" in command or "start" in command or "reboot" in command for command in calls))

    def test_failed_target_change_reverts_services_and_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            plan = configure(self.plan, "auto", copy.deepcopy(self.data))
            def runner(command, **kwargs):
                calls.append(command)
                if command[:3] == ["sudo", "systemctl", "set-default"]:
                    self.data["target"] = command[-1]
                    if command[-1] == "graphical.target":
                        raise subprocess.CalledProcessError(1, command)
                return self.runner(command, **kwargs)
            with self.assertRaises(subprocess.CalledProcessError):
                execute(plan, root, root, root / "state", runner)
            self.assertEqual(self.data["target"], "multi-user.target")
            self.assertIn(["sudo", "systemctl", "disable", "sddm.service"], calls)

    def test_rollback_preserves_external_target_changes(self):
        self.data["target"] = "rescue.target"
        self.assertTrue(undo_target({"previous": "multi-user.target", "next": "graphical.target"}, self.runner))
        self.assertEqual(self.data["target"], "rescue.target")


if __name__ == "__main__":
    unittest.main()
