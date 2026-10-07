import subprocess
import unittest

from forge.clipboard import choose


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.history = b"7\timage preview\n6\t$(touch should-not-exist)\n"
        self.selection = b"7\timage preview\n"
        self.content = b"\x89PNG\x00\xff\n\n"
        self.calls = []
        self.cancelled = False
        self.decode_failure = False

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command == ["cliphist", "list"]:
            return subprocess.CompletedProcess(command, 0, self.history)
        if command[0] == "fuzzel":
            return subprocess.CompletedProcess(command, 1 if self.cancelled else 0, self.selection)
        if command == ["cliphist", "decode"]:
            if self.decode_failure:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0, self.content)
        return subprocess.CompletedProcess(command, 0, b"")

    def test_binary_and_whitespace_preserved(self):
        for content in (self.content, b"  first\nsecond\n\n"):
            self.content = content
            self.assertTrue(choose(self.runner))
            self.assertEqual(self.calls[-1][0], ["wl-copy"])
            self.assertEqual(self.calls[-1][1]["input"], content)

    def test_cancel_never_changes_clipboard(self):
        self.cancelled = True
        self.assertFalse(choose(self.runner))
        self.assertEqual(len(self.calls), 2)

    def test_empty_history_does_not_open_picker(self):
        self.history = b""
        self.assertFalse(choose(self.runner))
        self.assertEqual(len(self.calls), 1)

    def test_decode_failure_keeps_existing_clipboard(self):
        self.decode_failure = True
        with self.assertRaises(subprocess.CalledProcessError):
            choose(self.runner)
        self.assertNotIn(["wl-copy"], [command for command, _ in self.calls])

    def test_arbitrary_typed_selection_is_rejected(self):
        self.selection = b"999\tunknown\n"
        with self.assertRaises(ValueError):
            choose(self.runner)
        self.assertEqual(len(self.calls), 2)

    def test_shell_metacharacters_are_data(self):
        self.selection = b"6\t$(touch should-not-exist)\n"
        self.assertTrue(choose(self.runner))
        self.assertTrue(all(not kwargs.get("shell") for _, kwargs in self.calls))
        self.assertEqual(self.calls[-2][1]["input"], self.selection)


if __name__ == "__main__":
    unittest.main()
