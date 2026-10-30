import argparse
import http.client
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from email.utils import parsedate_to_datetime
from pathlib import Path


REPOSITORY = 'hirsu-dev/hyprland-forge'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class RemoteArchive(io.RawIOBase):
    def __init__(self, url):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or not (parsed.hostname.endswith('.blob.core.windows.net') or parsed.hostname.endswith('.githubusercontent.com')):
            raise ValueError('Unexpected artifact download host')
        self.url, self.position = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as response:
            self.size = int(response.headers['Content-Length'])
        if not 0 < self.size <= 4 * 1024 ** 3:
            raise ValueError('Unexpected artifact size')

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position

    def read(self, size=-1):
        size = min(size if size >= 0 else self.size - self.position, self.size - self.position)
        if size <= 0:
            return b''
        request = urllib.request.Request(self.url, headers={'Range': f'bytes={self.position}-{self.position + size - 1}'})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    expected = f'bytes {self.position}-{self.position + size - 1}/{self.size}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('The artifact server returned an unexpected byte range')
                    data = response.read(size)
                    if len(data) != size:
                        raise http.client.IncompleteRead(data, size - len(data))
                break
            except (urllib.error.HTTPError, TimeoutError, ConnectionResetError, http.client.IncompleteRead) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                    raise
                if attempt == 5:
                    raise
                delay = 2 ** attempt
                if isinstance(error, urllib.error.HTTPError):
                    header = error.headers.get('Retry-After', '0')
                    try:
                        requested = float(header)
                    except (TypeError, ValueError):
                        try:
                            requested = parsedate_to_datetime(header).timestamp() - time.time()
                        except (TypeError, ValueError, OverflowError):
                            requested = 0
                    delay = max(delay, requested)
                if delay > 60:
                    raise
                print(f'Artifact transfer interrupted; retrying the same range in {delay:g}s', flush=True)
                time.sleep(delay)
        self.position += len(data)
        return data


def extract_verified(archive, output):
    names = archive.namelist()
    images = [name for name in names if re.fullmatch(r'forge-experimental-[0-9]{8}-x86_64\.iso', name)]
    if len(images) != 1 or set(names) != {'SHA256SUMS', 'build-packages.txt', images[0]} or len(names) != 3:
        raise ValueError('The artifact does not contain exactly one Forge ISO and its metadata')
    if archive.getinfo('SHA256SUMS').file_size > 1024 or archive.getinfo('build-packages.txt').file_size > 1024 * 1024:
        raise ValueError('Artifact metadata exceeds the size limit')
    manifest = archive.read('SHA256SUMS').decode('ascii')
    match = re.fullmatch(r'([a-f0-9]{64})  \./' + re.escape(images[0]) + r'\n', manifest)
    if not match:
        raise ValueError('The ISO checksum manifest is invalid')
    output = output.resolve()
    if output.exists():
        raise ValueError('Use a new directory for the verified artifact')
    output.mkdir(parents=True)
    temporary = output / (images[0] + '.partial')
    digest, total = hashlib.sha256(), 0
    try:
        with archive.open(images[0]) as source, temporary.open('xb') as destination:
            while chunk := source.read(8 * 1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                total += len(chunk)
                if total % (256 * 1024 * 1024) == 0:
                    print(f'Verified stream: {total} bytes received', flush=True)
        actual = digest.hexdigest()
        if actual != match[1]:
            raise ValueError('ISO checksum mismatch: expected ' + match[1] + ', received ' + actual)
        temporary.rename(output / images[0])
        (output / 'SHA256SUMS').write_text(manifest, encoding='ascii')
        (output / 'build-packages.txt').write_bytes(archive.read('build-packages.txt'))
        result = {'file': images[0], 'bytes': total, 'sha256': actual, 'zip_crc_valid': True}
        (output / 'artifact.json').write_text(json.dumps(result, indent=2))
        return result
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def fetch(run, output):
    token = os.environ.get('GH_TOKEN')
    if not token or run <= 0:
        raise ValueError('A GitHub Actions read token and run identity are required')
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'Forge-ISO-validation'}
    request = urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run}/artifacts?per_page=100', headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        artifacts = json.load(response)['artifacts']
    matches = [item for item in artifacts if item['name'] == 'forge-experimental-iso' and not item['expired']]
    if len(matches) != 1 or type(matches[0]['id']) is not int:
        raise ValueError('The requested run does not have one available ISO artifact')
    request = urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{matches[0]["id"]}/zip', headers=headers)
    try:
        urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
        raise ValueError('GitHub did not provide an artifact download location')
    except urllib.error.HTTPError as error:
        if error.code != 302:
            raise ValueError('Artifact access failed with HTTP ' + str(error.code)) from None
        location = error.headers['Location']
    with zipfile.ZipFile(RemoteArchive(location)) as archive:
        return extract_verified(archive, output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=int)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(fetch(args.run, args.output)), flush=True)
