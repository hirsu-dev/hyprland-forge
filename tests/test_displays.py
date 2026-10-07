import contextlib
import io
import json
import unittest
from unittest.mock import patch

from forge.displays import main, render
from forge.manifest import ForgeError


class DisplaySettingsTests(unittest.TestCase):
    def test_default_options(self):
        value = render()[".config/hypr/monitors.local.lua"]
        self.assertIn('internal_position = "right"', value)
        self.assertIn('internal_scale = "auto"', value)

    def test_external_connector_and_scaling(self):
        value = render("HDMI-A-1", "left", "1.5")[".config/hypr/monitors.local.lua"]
        self.assertIn('external = "HDMI-A-1"', value)
        self.assertIn("internal_scale = 1.5", value)

    def test_invalid_connector_is_refused(self):
        for connector in ('HDMI"}; os.execute("bad")', "../eDP-1", "HDMI\n", "", "-1"):
            with self.subTest(connector=connector), self.assertRaises(ForgeError):
                render(connector)

    def test_invalid_scale_is_refused(self):
        for scale in ("nan", "inf", "0", "-1", "4", "wrong"):
            with self.subTest(scale=scale), self.assertRaises(ForgeError):
                render(scale=scale)

    def test_invalid_position_is_refused(self):
        with self.assertRaises(ForgeError):
            render(position="bad")

    def test_cli_plan(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--position", "above", "--plan"]), 0)
        self.assertEqual(json.loads(output.getvalue()), render(position="above"))

    def test_apply_refused_on_windows(self):
        with patch("forge.runtime.platform.system", return_value="Windows"), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--apply"]), 1)


if __name__ == "__main__":
    unittest.main()
