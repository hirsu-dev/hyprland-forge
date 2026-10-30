import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forge.iso_apps import flatpak_commands, selection
from forge.iso_install import base, finish, guard, keyboard_settings, mounted_target, options, package_plan, windows_menu
from forge.manifest import ForgeError, load_manifest
from forge.hardware import resolve_plan
from forge.setup import with_gaming
from forge.iso_assets import install_boot_assets


ROOT = Path(__file__).resolve().parent.parent


class IsoInstallationTests(unittest.TestCase):
    def test_reduced_motion_is_applied_to_boot_and_login(self):
        try:
            import PIL
        except ImportError:
            self.skipTest('Boot asset rendering requires Pillow')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('forge.iso_assets.subprocess.run') as run:
                install_boot_assets(root, ROOT, False)
            self.assertIn('Motion=false', (root / 'usr/share/sddm/themes/forge/theme.conf').read_text())
            self.assertIn('motion = 0;', (root / 'usr/share/plymouth/themes/forge/forge.script').read_text())
            self.assertTrue((root / 'boot/grub/themes/forge/background.png').is_file())
            self.assertEqual(run.call_args.args[0][:2], ['arch-chroot', str(root)])

    def test_keyboard_layouts_and_variants_are_preserved(self):
        value = keyboard_settings('fr', 'oss', 'us', '', 'grp:alt_shift_toggle')
        self.assertEqual(value, {'kb_layout': 'fr,us', 'kb_variant': 'oss,', 'kb_options': 'grp:alt_shift_toggle'})
        for values in (('us\");os.execute("id")', ''), ('', ''), ('us', None)):
            with self.assertRaises(ForgeError):
                keyboard_settings(*values)

    def test_desktop_installation_records_deployment_and_protected_boot_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            (root / 'etc/passwd').write_text('forge:x:1000:1000:Forge:/home/forge:/bin/bash\n')
            home = root / 'home/forge'
            home.mkdir(parents=True)
            settings = {'gaming': True, 'motion': False, 'apps': ['brave', 'equicord']}
            device = {'virtual': 'qemu', 'gpus': set(), 'cpu': ''}
            with patch('forge.iso_install.subprocess.run') as run, patch('forge.iso_install.os.chown', create=True) as chown, patch('forge.iso_install.find_windows', return_value=['ABCD-1234']), patch('forge.iso_assets.install_boot_assets'):
                finish(root, ROOT, settings, device, 'forge', keyboard_settings('fr', 'oss'))
            state = json.loads((home / '.local/state/hyprland-forge/setup.json').read_text())
            self.assertEqual(state['profile'], 'virtual-machine')
            self.assertEqual(state['apps'], settings['apps'])
            self.assertFalse(json.loads((home / '.config/forge/interface.json').read_text())['motion'])
            self.assertTrue((home / '.local/bin/forge-session').is_file())
            self.assertTrue((home / '.local/state/hyprland-forge/transactions' / state['transaction'] / 'files.json').is_file())
            self.assertIn('ABCD-1234', (root / 'etc/grub.d/41_forge_windows').read_text())
            self.assertIn('"fr"', (home / '.config/hypr/forge/installation.lua').read_text())
            self.assertIn('"oss"', (home / '.config/hypr/forge/installation.lua').read_text())
            self.assertTrue(all(call.args[1:] == (1000, 1000) for call in chown.call_args_list))
            self.assertTrue(all(str(path).startswith(str(root)) for call in chown.call_args_list for path in call.args[:1]))
            self.assertTrue(all(call.args[0][:3] == ['systemctl', '--root', str(root)] for call in run.call_args_list))

    def test_intel_iso_upgrade_preserves_matching_driver_selection(self):
        plan = {'stages': ['hardware'], 'packages': ['amd-ucode', 'nvidia-open-dkms', 'nvidia-utils', 'vulkan-radeon', 'mesa']}
        device = {'gpus': [{'vendor': '0x8086'}], 'kernels': ['linux'], 'secure_boot': False, 'cpu': 'intel'}
        with patch('forge.hardware.platform.system', return_value='Linux'), patch('forge.hardware.Path.is_file', return_value=True), patch('forge.hardware.virtualization', return_value=''), patch('forge.hardware.inventory', return_value=device), patch('forge.hardware.verify_services'):
            result = resolve_plan(plan, apply=True, profile='auto')
        self.assertIn('intel-ucode', result['packages'])
        self.assertIn('vulkan-intel', result['packages'])
        self.assertNotIn('nvidia-utils', result['packages'])
        self.assertFalse(any('nvidia' in service for service in result['services']))
        with_gaming(result, ROOT)
        self.assertIn('lib32-vulkan-intel', result['packages'])
        self.assertNotIn('lib32-nvidia-utils', result['packages'])
        self.assertNotIn('lib32-vulkan-radeon', result['packages'])

    def test_auto_profile_denies_unknown_environment(self):
        with patch('forge.hardware.platform.system', return_value='Linux'), patch('forge.hardware.Path.is_file', return_value=True), patch('forge.hardware.virtualization', return_value=None):
            with self.assertRaises(ForgeError):
                resolve_plan({'stages': ['hardware'], 'packages': []}, apply=True, profile='auto')

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
