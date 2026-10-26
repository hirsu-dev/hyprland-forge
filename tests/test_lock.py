import os
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class LockTests(unittest.TestCase):
    def test_wrapper_keeps_hardware_rendering_and_uses_software_only_in_vm(self):
        wrapper = Path(__file__).resolve().parent.parent / "configs/bin/forge-lock"
        for virtual, expected in (("oracle", "1"), (None, "keep")):
            with self.subTest(virtual=virtual), patch("forge.hardware.virtualization", return_value=virtual), patch("os.execvpe") as execute, patch.dict(os.environ, {"LIBGL_ALWAYS_SOFTWARE": "keep"}), patch.object(sys, "argv", ["forge-lock", "--no-fade-in"]), patch.object(sys, "path", list(sys.path)):
                runpy.run_path(str(wrapper), run_name="__main__")
                command, arguments, environment = execute.call_args.args
                self.assertEqual(command, "hyprlock")
                self.assertEqual(arguments, ["hyprlock", "--grace", "0", "--no-fade-in"])
                self.assertEqual(environment["LIBGL_ALWAYS_SOFTWARE"], expected)


if __name__ == "__main__":
    unittest.main()
