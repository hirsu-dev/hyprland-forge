import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from forge.iso_app_setup import STATE, install_pending, prepare
from forge.iso_install import base
from forge.manifest import ForgeError


ROOT = Path(__file__).resolve().parents[1]


@patch.object(os, 'O_NOFOLLOW', getattr(os, 'O_NOFOLLOW', 0), create=True)
class DeferredAppsTests(unittest.TestCase):
    def test_OS_base_queues_apps_without_running_downloads_in_chroot(self):
        original = Path.read_text
        def read(path, *args, **kwargs):
            return '[options]\n' if path == Path('/etc/pacman.conf') else original(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(Path, 'read_text', autospec=True, side_effect=read), patch('forge.iso_install.shutil.copytree'), patch('forge.iso_install.subprocess.run') as run:
                base(root, ROOT, {'gaming': False, 'motion': True, 'apps': ['brave', 'equicord', 'spotify']}, {'virtual': 'qemu', 'cpu': '', 'gpus': set()})
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'pacstrap')
            state = json.loads((root / STATE.relative_to('/')).read_text())
            self.assertEqual(state['apps'], ['brave', 'equicord', 'spotify'])
            self.assertEqual(state['status'], 'pending')
            unit = (root / 'etc/systemd/system/forge-app-setup.service').read_text()
            self.assertIn('Type=exec', unit)
            self.assertIn('Restart=on-failure', unit)
            self.assertIn('StartLimitBurst=3', unit)
            self.assertTrue((root / 'usr/share/applications/forge-app-setup.desktop').is_file())
            self.assertEqual(json.loads((root / 'var/lib/hyprland-forge/iso-install.json').read_text())['phase'], 'base-complete')

    def test_native_only_selection_has_no_flatpak_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root, ['obs', 'vlc'])
            self.assertEqual(list(root.iterdir()), [])

    def test_failed_app_is_retained_and_retry_skips_installed_apps(self):
        installed = set()
        calls = []
        fail = True
        def run(arguments, **kwargs):
            calls.append(arguments)
            if arguments[1] == 'info':
                return SimpleNamespace(returncode=0 if arguments[-1] in installed else 1)
            if arguments[1] == 'install':
                if fail and arguments[-1] == 'com.spotify.Client':
                    kwargs['stdout'].write('test download error: network interrupted\n')
                    return SimpleNamespace(returncode=1)
                installed.add(arguments[-1])
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root, ['brave', 'equicord', 'spotify'])
            state = root / STATE.relative_to('/')
            log = root / 'download.log'
            self.assertFalse(install_pending(state, log, run))
            value = json.loads(state.read_text())
            self.assertEqual(value['status'], 'retry-needed')
            self.assertEqual(value['results']['brave']['status'], 'installed')
            self.assertEqual(value['results']['spotify']['status'], 'retry-needed')
            self.assertIn('network interrupted', log.read_text())
            calls.clear()
            fail = False
            self.assertTrue(install_pending(state, log, run))
            self.assertEqual([call[-1] for call in calls if call[1] == 'install'], ['com.spotify.Client'])
            self.assertEqual(json.loads(state.read_text())['status'], 'complete')
            calls.clear()
            installed.clear()
            self.assertTrue(install_pending(state, log, run))
            self.assertEqual(calls, [])

    def test_remote_failure_and_timeout_preserve_selection_for_retry(self):
        for failure in (SimpleNamespace(returncode=1), subprocess.TimeoutExpired('flatpak', 120)):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                prepare(root, ['spotify'])
                state = root / STATE.relative_to('/')
                with patch('subprocess.run', side_effect=[SimpleNamespace(returncode=1), failure]) as run:
                    self.assertFalse(install_pending(state, root / 'download.log', run))
                value = json.loads(state.read_text())
                self.assertEqual(value['apps'], ['spotify'])
                self.assertEqual(value['status'], 'retry-needed')

    def test_untrusted_app_selection_is_rejected_without_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state.json'
            for apps in (['--command=touch /tmp/bad'], ['spotify', 'spotify'], ['obs']):
                state.write_text(json.dumps({'schema': 1, 'apps': apps}))
                with self.subTest(apps=apps), patch('subprocess.run') as run:
                    with self.assertRaises(ForgeError):
                        install_pending(state, root / 'log', run)
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
