import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge import VERSION
from forge.bundle import build_bundle
from forge.manifest import ForgeError
from forge.releases import latest, main, read_url, select_release, status, unpack_release


ROOT = Path(__file__).resolve().parent.parent


def release(tag, prerelease=False):
    return {"tag_name": tag, "draft": False, "prerelease": prerelease, "assets": [{"name": "hyprland-forge-" + tag[1:] + ".tar.gz", "digest": "sha256:" + "a" * 64}]}


def archive_bytes(payloads, extra=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, data in payloads.items():
            member = tarfile.TarInfo("hyprland-forge/" + name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if extra:
            archive.addfile(extra)
    return output.getvalue()


class ReleaseTests(unittest.TestCase):
    def test_one_link_installer_and_desktop_updater_choose_the_same_channel(self):
        script = (ROOT / "install-online.sh").read_text(encoding="utf-8")
        selector = script.split("release_info=\"$(python3 -c '\n", 1)[1].split("\n' <<<", 1)[0]
        items = [release("v2.0.0", True), release("v1.2.0"), release("v1.10.0")]
        for channel in ("recommended", "stable", "preview"):
            result = subprocess.run([sys.executable, "-c", selector], input=json.dumps(items), text=True, capture_output=True, env={**os.environ, "FORGE_RELEASE_CHANNEL": channel})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split()[0], select_release(items, channel)["tag"])

    def test_recommended_prefers_stable_and_preview_explicitly_includes_candidates(self):
        items = [release("v1.2.0"), release("v2.0.0", True), release("v1.10.0")]
        self.assertEqual(select_release(items)["version"], "1.10.0")
        self.assertEqual(select_release(items, "preview")["version"], "2.0.0")
        self.assertEqual(select_release(items, "stable")["version"], "1.10.0")

    def test_recommended_fallback_and_unavailable_stable_are_explicit(self):
        items = [release("v0.17.0", True)]
        self.assertTrue(select_release(items)["prerelease"])
        with self.assertRaisesRegex(ForgeError, "No verified release"):
            select_release(items, "stable")

    def test_drafts_invalid_tags_and_missing_digests_never_become_updates(self):
        draft = {**release("v999.0.0"), "draft": True}
        items = [draft, release("v../secret"), release("v1.0.0")]
        self.assertEqual(select_release(items)["version"], "1.0.0")
        for assets in ([], [{"name": "hyprland-forge-1.0.0.tar.gz"}], release("v1.0.0")["assets"] * 2):
            with self.subTest(assets=assets), self.assertRaises(ForgeError):
                select_release([{**release("v1.0.0"), "assets": assets}])

    def test_status_compares_numeric_versions_without_proposing_a_downgrade(self):
        for tag, expected in (("v99.0.0", True), ("v" + VERSION, False), ("v0.1.0", False)):
            self.assertEqual(status(reader=lambda *_: json.dumps([release(tag)]).encode())["updateAvailable"], expected)

    def test_transport_is_bounded_and_errors_are_readable(self):
        class Response(io.BytesIO):
            pass
        with self.assertRaisesRegex(ForgeError, "size limit"):
            read_url("https://example.test", 3, opener=lambda *a, **k: Response(b"1234"))
        def offline(*args, **kwargs):
            raise OSError("offline")
        with self.assertRaisesRegex(ForgeError, "unavailable"):
            read_url("https://example.test", 3, opener=offline)
        with self.assertRaisesRegex(ForgeError, "invalid metadata"):
            latest(reader=lambda *_: b"<html>offline</html>")

    def test_verified_bundle_unpacks_without_executing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = build_bundle(ROOT, root / "built", "a" * 40)
            data = archive.read_bytes()
            selected = {"version": VERSION, "url": "fixture", "sha256": hashlib.sha256(data).hexdigest()}
            with patch("forge.releases.subprocess.run", side_effect=AssertionError("inspection must not execute")):
                unpacked = unpack_release(selected, root, reader=lambda *_: data)
            self.assertTrue((unpacked / "install.sh").is_file())
            self.assertEqual(json.loads((unpacked / "build.json").read_text())["revision"], "a" * 40)

    def test_modified_download_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ForgeError, "checksum"):
                unpack_release({"url": "fixture", "sha256": "a" * 64}, root, reader=lambda *_: b"changed")
            self.assertEqual(list(root.iterdir()), [])

    def test_links_path_traversal_and_oversized_members_are_rejected(self):
        unsafe = tarfile.TarInfo("hyprland-forge/link")
        unsafe.type = tarfile.SYMTYPE
        unsafe.linkname = "../../outside"
        huge = tarfile.TarInfo("hyprland-forge/huge")
        huge.size = 33 * 1024 ** 2
        for data in (archive_bytes({}, unsafe), archive_bytes({"../../outside": b"keep"}), archive_bytes({}, huge)):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                selected = {"url": "fixture", "sha256": hashlib.sha256(data).hexdigest()}
                with self.assertRaises(ForgeError):
                    unpack_release(selected, root, reader=lambda *_: data)
                self.assertFalse((root / "unpacked").exists())

    def test_unchecked_files_and_wrong_release_identity_are_rejected(self):
        base = {"build.json": json.dumps({"version": VERSION, "revision": "a" * 40}).encode(), "project.json": json.dumps({"release": VERSION}).encode(), "install.sh": b"exit 81\n"}
        checks = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in base.items()).encode()
        payloads = {**base, "SHA256SUMS": checks}
        for extra, selected_version in (({"unchecked": b"extra"}, VERSION), ({}, "99.0.0")):
            data = archive_bytes({**payloads, **extra})
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ForgeError):
                unpack_release({"version": selected_version, "url": "fixture", "sha256": hashlib.sha256(data).hexdigest()}, Path(directory), reader=lambda *_: data)

    def test_apply_requires_terminal_and_current_release_does_not_install(self):
        with patch("forge.releases.preflight"), patch("forge.releases.sys.stdin.isatty", return_value=False), patch("forge.releases.latest") as lookup:
            self.assertEqual(main(["--apply"]), 1)
            lookup.assert_not_called()
        selected = select_release([release("v" + VERSION)])
        with patch("forge.releases.preflight"), patch("forge.releases.sys.stdin.isatty", return_value=True), patch("forge.releases.latest", return_value=selected), patch("forge.releases.subprocess.run") as command:
            self.assertEqual(main(["--apply"]), 0)
            command.assert_not_called()

    def test_apply_hands_verified_candidate_to_interactive_setup(self):
        selected = select_release([release("v99.0.0")])
        with tempfile.TemporaryDirectory() as directory, patch("forge.releases.preflight"), patch("forge.releases.sys.stdin.isatty", return_value=True), patch("forge.releases.latest", return_value=selected), patch("forge.releases.unpack_release", return_value=Path(directory)), patch("forge.releases.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as command:
            self.assertEqual(main(["--apply"]), 0)
            self.assertEqual(command.call_args.args[0], ["bash", str(Path(directory) / "install.sh"), "--setup"])
            self.assertEqual(command.call_args.kwargs["env"]["PYTHONPATH"], "")


if __name__ == "__main__":
    unittest.main()
