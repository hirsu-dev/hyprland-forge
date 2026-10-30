import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.iso_apps import flatpak_commands, selection
from forge.iso_install import base, finish, guard, mounted_target, options, package_plan, windows_menu
from forge.manifest import ForgeError, load_manifest


ROOT = Path(__file__).resolve().parent.parent


class IsoInstallationTests(unittest.TestCase):
    def test_existing_system_is_refused_before_installing_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            sentinel = root / 'etc/passwd'
            sentinel.write_text('existing-account')
            with patch('forge.iso_install.subprocess.run') as run:
                with self.assertRaises(ForgeError):
                    base(root, ROOT, {'gaming': False, 'motion': True, 'apps': []}, {'virtual': 'qemu'})
                run.assert_not_called()
            self.assertEqual(sentinel.read_text(), 'existing-account')

    def test_guard_denies_non_live_hosts_without_running_commands(self):
        with patch('forge.iso_install.platform.system', return_value='Linux'), patch('forge.iso_install.os.geteuid', return_value=0, create=True), patch('forge.iso_install.Path.is_file', return_value=False), patch('forge.iso_install.subprocess.run') as run:
            with self.assertRaises(ForgeError):
                guard(ROOT)
            run.assert_not_called()

    def test_guard_denies_windows_without_accessing_disks(self):
        with patch('forge.iso_install.platform.system', return_value='Windows'), patch('forge.iso_install.subprocess.run') as run:
            with self.assertRaises(ForgeError):
                guard(ROOT)
            run.assert_not_called()

    def test_target_rejects_host_paths_and_unmounted_directories(self):
        for value in (None, '/', '/home/forge', '/tmp', '/tmp/../', '/tmp/calamares-root-nonexistent', 'C:/Windows', '/mnt/windows'):
            with self.subTest(value=value), self.assertRaises(ForgeError):
                mounted_target(value)

    def test_options_are_strict_and_do_not_accept_arbitrary_app_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'options.json'
            valid = {'gaming': True, 'motion': False, 'apps': ['brave', 'equicord']}
            path.write_text(json.dumps(valid))
            self.assertEqual(options(path), valid)
            for invalid in ({**valid, 'gaming': 'yes'}, {**valid, 'apps': ['--command=sh']}, {**valid, 'apps': ['brave', 'brave']}, {**valid, 'apps': ['discord', 'equicord']}, {**valid, 'apps': None}, {**valid, 'extra': True}):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ForgeError):
                    options(path)

    def test_virtual_machine_does_not_receive_physical_gpu_drivers(self):
        manifest = load_manifest(ROOT)
        packages = package_plan(manifest, {'cpu': 'amd', 'gpus': {'0x10de'}, 'virtual': 'oracle'}, True, ['brave'])
        self.assertNotIn('nvidia-open-dkms', packages)
        self.assertNotIn('lib32-nvidia-utils', packages)
        self.assertNotIn('amd-ucode', packages)
        self.assertIn('virtualbox-guest-utils', packages)
        self.assertIn('lib32-vulkan-swrast', packages)
        self.assertIn('flatpak', packages)

    def test_native_gpu_and_microcode_packages_follow_hardware(self):
        manifest = load_manifest(ROOT)
        intel = package_plan(manifest, {'cpu': 'intel', 'gpus': {'0x8086'}, 'virtual': ''}, False)
        nvidia = package_plan(manifest, {'cpu': 'amd', 'gpus': {'0x1002', '0x10de'}, 'virtual': ''}, True)
        self.assertIn('intel-ucode', intel)
        self.assertIn('vulkan-intel', intel)
        self.assertNotIn('nvidia-utils', intel)
        self.assertNotIn('steam', intel)
        self.assertIn('linux-headers', nvidia)
        self.assertIn('nvidia-open-dkms', nvidia)
        self.assertIn('lib32-vulkan-radeon', nvidia)
        self.assertIn('lib32-nvidia-utils', nvidia)

    def test_app_installation_uses_only_catalogue_commands(self):
        commands = flatpak_commands(['brave', 'equicord', 'spotify'])
        self.assertEqual(commands[-1][-3:], ['com.brave.Browser', 'io.github.equicord.equibop', 'com.spotify.Client'])
        self.assertEqual(flatpak_commands(['obs']), [])
        for values in (['brave; touch /tmp/bad'], ['https://example.com/unknown.flatpakref'], ['discord', 'equicord']):
            with self.assertRaises(ForgeError):
                flatpak_commands(values)
        self.assertEqual(selection([]), [])

    def test_native_app_choices_add_packages(self):
        packages = package_plan(load_manifest(ROOT), {'cpu': '', 'gpus': set(), 'virtual': 'qemu'}, False, ['obs', 'libreoffice', 'keepassxc'])
        self.assertTrue({'obs-studio', 'libreoffice-fresh', 'keepassxc'} <= set(packages))
        self.assertNotIn('flatpak', packages)

    def test_windows_chainloader_uses_validated_uuid_without_disk_writes(self):
        menu = windows_menu(['1234-ABCD', '1234-ABCD'])
        self.assertEqual(menu.count('menuentry '), 1)
        self.assertIn('chainloader /EFI/Microsoft/Boot/bootmgfw.efi', menu)
        self.assertIn('search --no-floppy --fs-uuid --set=root 1234-ABCD', menu)
        for value in ('', '1234-ABCD;reboot', '$(id)', '../windows', None):
            with self.subTest(value=value), self.assertRaises((ForgeError, TypeError)):
                windows_menu([value])

    def test_desktop_installation_rejects_root_account_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            (root / 'etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\n')
            with patch('forge.iso_install.subprocess.run') as run:
                with self.assertRaises(ForgeError):
                    finish(root, ROOT, {'gaming': False, 'motion': True, 'apps': []}, {'virtual': 'qemu', 'gpus': set()}, 'root')
                run.assert_not_called()
            self.assertFalse((root / 'home').exists())


if __name__ == '__main__':
    unittest.main()
