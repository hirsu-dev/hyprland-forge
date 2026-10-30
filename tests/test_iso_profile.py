import shutil
import tempfile
import unittest
from pathlib import Path

from iso.prepare import prepare


ROOT = Path(__file__).resolve().parents[1]
RELENG = Path('/usr/share/archiso/configs/releng')


@unittest.skipUnless((RELENG / 'profiledef.sh').is_file(), 'Native Archiso profile is required')
class LiveProfileTests(unittest.TestCase):
    def test_live_network_owner_and_graphical_power_prerequisites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'profile'
            shutil.copytree(RELENG, profile, symlinks=True)
            repository = root / 'repository'
            repository.mkdir()
            (repository / 'forge.db.tar.gz').touch()
            prepare(ROOT, profile, repository)
            system = profile / 'airootfs/etc/systemd/system'
            for name in ('systemd-networkd.service', 'systemd-networkd.socket', 'systemd-resolved.service', 'iwd.service'):
                self.assertTrue((system / name).is_symlink())
                self.assertEqual((system / name).readlink(), Path('/dev/null'))
            self.assertEqual((system / 'multi-user.target.wants/NetworkManager.service').readlink(), Path('/usr/lib/systemd/system/NetworkManager.service'))
            resolver = profile / 'airootfs/etc/resolv.conf'
            self.assertTrue(resolver.is_file())
            self.assertFalse(resolver.is_symlink())
            packages = set((profile / 'packages.x86_64').read_text().splitlines())
            self.assertTrue({'networkmanager', 'wpa_supplicant', 'calamares', 'pyside6', 'xorg-xset'} <= packages)


if __name__ == '__main__':
    unittest.main()
