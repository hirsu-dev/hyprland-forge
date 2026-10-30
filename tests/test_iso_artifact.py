import hashlib
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('iso_fetch', ROOT / 'iso/fetch_artifact.py')
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class IsoArtifactTests(unittest.TestCase):
    def make_archive(self, data=b'ISO test payload', expected=None, extra=None):
        name = 'forge-experimental-20261030-x86_64.iso'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr(name, data)
            archive.writestr('SHA256SUMS', (expected or hashlib.sha256(data).hexdigest()) + '  ./' + name + '\n')
            archive.writestr('build-packages.txt', 'linux 7\n')
            if extra:
                archive.writestr(extra, 'unexpected')
        stream.seek(0)
        return zipfile.ZipFile(stream)

    def test_verified_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory, self.make_archive() as archive:
            output = Path(directory) / 'verified'
            result = fetcher.extract_verified(archive, output)
            self.assertEqual((output / result['file']).read_bytes(), b'ISO test payload')
            self.assertTrue(result['zip_crc_valid'])
            self.assertFalse(list(output.glob('*.partial')))

    def test_valid_zip_with_wrong_iso_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.make_archive(expected='0' * 64) as archive:
            output = Path(directory) / 'invalid'
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetcher.extract_verified(archive, output)
            self.assertFalse(list(output.glob('*.iso')))
            self.assertFalse(list(output.glob('*.partial')))

    def test_unexpected_files_and_path_traversal_are_rejected(self):
        for name in ('../outside', '/absolute.iso', 'another.iso'):
            with tempfile.TemporaryDirectory() as directory, self.make_archive(extra=name) as archive:
                output = Path(directory) / 'invalid'
                with self.assertRaises(ValueError):
                    fetcher.extract_verified(archive, output)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
