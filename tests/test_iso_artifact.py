import hashlib
import importlib.util
import io
import ssl
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('iso_fetch', ROOT / 'iso/fetch_artifact.py')
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class IsoArtifactTests(unittest.TestCase):
    def remote(self, payload=b'ISO bytes'):
        remote = object.__new__(fetcher.RemoteArchive)
        remote.url, remote.position, remote.size = 'https://artifacts.blob.core.windows.net/test', 0, len(payload)
        response = io.BytesIO(payload)
        response.status = 206
        response.headers = {'Content-Range': f'bytes 0-{len(payload)-1}/{len(payload)}'}
        return remote, response

    def test_throttled_range_is_retried_without_advancing_or_duplicating_bytes(self):
        remote, response = self.remote()
        error = urllib.error.HTTPError(remote.url, 503, 'Server Busy', {'Retry-After': '2'}, None)
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=[error, response]) as request, patch.object(fetcher.time, 'sleep') as sleep:
            self.assertEqual(remote.read(9), b'ISO bytes')
        self.assertEqual(remote.position, 9)
        self.assertEqual(request.call_args_list[0].args[0].get_header('Range'), request.call_args_list[1].args[0].get_header('Range'))
        sleep.assert_called_once_with(2)

    def test_incomplete_range_is_retried_before_returning_any_bytes(self):
        remote, response = self.remote()
        _, short = self.remote(b'ISO')
        short.headers = response.headers
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=[short, response]), patch.object(fetcher.time, 'sleep'):
            self.assertEqual(remote.read(9), b'ISO bytes')
        self.assertEqual(remote.position, 9)

    def test_throttling_retries_are_bounded_and_authorization_is_not_retried(self):
        for code, attempts in ((503, 6), (403, 1)):
            remote, _ = self.remote()
            error = urllib.error.HTTPError(remote.url, code, 'Unavailable', {}, None)
            with patch.object(fetcher.urllib.request, 'urlopen', side_effect=error) as request, patch.object(fetcher.time, 'sleep'), self.assertRaises(urllib.error.HTTPError):
                remote.read(9)
            self.assertEqual(request.call_count, attempts)
            self.assertEqual(remote.position, 0)

    def test_wrong_byte_range_is_rejected_without_retry(self):
        remote, response = self.remote()
        response.headers['Content-Range'] = 'bytes 1-9/10'
        with patch.object(fetcher.urllib.request, 'urlopen', return_value=response) as request, self.assertRaisesRegex(ValueError, 'unexpected byte range'):
            remote.read(9)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(remote.position, 0)

    def test_retry_after_http_date_is_respected(self):
        remote, response = self.remote()
        error = urllib.error.HTTPError(remote.url, 503, 'Busy', {'Retry-After': 'Thu, 01 Jan 1970 00:00:03 GMT'}, None)
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=[error, response]), patch.object(fetcher.time, 'sleep') as sleep, patch.object(fetcher.time, 'time', return_value=0):
            self.assertEqual(remote.read(9), b'ISO bytes')
        sleep.assert_called_once_with(3)

    def test_long_retry_after_stops_without_retrying_early(self):
        remote, _ = self.remote()
        error = urllib.error.HTTPError(remote.url, 503, 'Busy', {'Retry-After': '120'}, None)
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=error) as request, patch.object(fetcher.time, 'sleep') as sleep, self.assertRaises(urllib.error.HTTPError):
            remote.read(9)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()

    def test_wrapped_connection_reset_retries_the_same_range(self):
        remote, response = self.remote()
        error = urllib.error.URLError(ConnectionResetError('Connection reset'))
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=[error, response]), patch.object(fetcher.time, 'sleep'):
            self.assertEqual(remote.read(9), b'ISO bytes')
        self.assertEqual(remote.position, 9)

    def test_certificate_verification_failure_is_not_retried(self):
        remote, _ = self.remote()
        error = urllib.error.URLError(ssl.SSLCertVerificationError('Certificate verification failed'))
        with patch.object(fetcher.urllib.request, 'urlopen', side_effect=error) as request, patch.object(fetcher.time, 'sleep') as sleep, self.assertRaises(urllib.error.URLError):
            remote.read(9)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()

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
