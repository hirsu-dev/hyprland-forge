import argparse
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path


def boot(image, output, seconds=240, memory=2304, expected_revision=None):
    image, output = image.resolve(), output.resolve()
    if not image.is_file() or image.suffix != '.iso' or output.exists():
        raise ValueError('Supply an ISO and a new directory for this disposable VM.')
    output.mkdir(parents=True)
    firmware = next((p for p in sorted(Path('/usr/share/edk2').rglob('OVMF_CODE*.fd')) if 'secboot' not in p.name and p.with_name(p.name.replace('CODE', 'VARS')).is_file()), None)
    if not firmware:
        raise ValueError('UEFI firmware is missing.')
    monitor = output / 'qmp.sock'
    variables = output / 'OVMF_VARS.fd'
    shutil.copyfile(firmware.with_name(firmware.name.replace('CODE', 'VARS')), variables)
    disk = output / 'disposable.qcow2'
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(disk), '64G'], check=True)
    command = ['qemu-system-x86_64', '-accel', 'tcg,thread=multi']
    command += ['-machine', 'q35', '-m', str(memory), '-smp', '2', '-cpu', 'max', '-drive', f'if=pflash,format=raw,readonly=on,file={firmware}', '-drive', f'if=pflash,format=raw,file={variables}', '-cdrom', str(image), '-boot', 'd', '-drive', f'file={disk},format=qcow2,if=virtio', '-netdev', 'user,id=forge', '-device', 'virtio-net-pci,netdev=forge', '-vga', 'std', '-display', 'none', '-qmp', f'unix:{monitor},server=on,wait=off', '-serial', 'file:' + str(output / 'serial.log')]
    probe = Path(__file__).resolve().parents[1] / 'tests/validate-live-iso.py'
    command += ['-fw_cfg', 'name=opt/forge,file=' + str(probe)]
    with (output / 'qemu.log').open('wb') as log:
        with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as process:
            try:
                for _ in range(100):
                    if monitor.exists():
                        break
                    if process.poll() is not None:
                        raise RuntimeError('The disposable VM could not start: ' + (output / 'qemu.log').read_text(errors='replace')[:2000])
                    time.sleep(0.1)
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(60)
                    connection.connect(str(monitor))
                    stream = connection.makefile('rwb', buffering=0)
                    if not stream.readline():
                        raise RuntimeError('The VM monitor closed before its greeting.')
                    def qmp(name, arguments=None):
                        stream.write((json.dumps({'execute': name, 'arguments': arguments or {}}) + '\n').encode())
                        while True:
                            line = stream.readline()
                            if not line:
                                raise RuntimeError('The VM monitor connection closed.')
                            value = json.loads(line)
                            if 'error' in value:
                                raise RuntimeError(str(value['error']))
                            if 'return' in value:
                                return value['return']
                    qmp('qmp_capabilities')
                    def key(*names):
                        qmp('send-key', {'keys': [{'type': 'qcode', 'data': name} for name in names], 'hold-time': 30})
                        time.sleep(.08)
                    def type_line(text):
                        punctuation = {' ': ('spc',), '/': ('slash',), '_': ('shift', 'minus'), '-': ('minus',), '.': ('dot',), '>': ('shift', 'dot'), '&': ('shift', '7')}
                        for character in text:
                            key(*(punctuation[character] if character in punctuation else ('shift', character.lower()) if character.isupper() else (character,)))
                        key('ret')
                    start = time.monotonic()
                    for interval in (45, 120, seconds):
                        while time.monotonic() - start < interval:
                            if process.poll() is not None:
                                raise RuntimeError('The disposable VM exited during boot.')
                            time.sleep(2)
                        target = output / f'boot-{interval}.ppm'
                        qmp('screendump', {'filename': str(target)})
                        from PIL import Image
                        with Image.open(target) as capture:
                            capture.save(target.with_suffix('.png'))
                        target.unlink()
                    key('ctrl', 'alt', 'f3')
                    time.sleep(3)
                    type_line('root')
                    time.sleep(3)
                    type_line('modprobe qemu_fw_cfg')
                    time.sleep(1)
                    type_line('python /sys/firmware/qemu_fw_cfg/by_name/opt/forge/raw >/dev/ttyS0 2>&1')
                    deadline = time.monotonic() + 150
                    captured = False
                    guest = None
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError('The disposable VM exited during the live check')
                        serial = (output / 'serial.log').read_text(errors='replace')
                        if 'FORGE_ISO_INSTALLER_READY' in serial and not captured:
                            target = output / 'live-installer.ppm'
                            qmp('screendump', {'filename': str(target)})
                            with Image.open(target) as capture:
                                capture.save(target.with_suffix('.png'))
                            target.unlink()
                            captured = True
                        marker = next((line.partition('FORGE_ISO_REPORT=')[2] for line in serial.splitlines(keepends=True) if line.endswith('\n') and 'FORGE_ISO_REPORT=' in line), None)
                        if marker:
                            guest = json.loads(marker)
                            (output / 'live-check.json').write_text(json.dumps(guest, indent=2) + '\n')
                            break
                        time.sleep(1)
                    if guest is None:
                        target = output / 'probe-failure.ppm'
                        qmp('screendump', {'filename': str(target)})
                        with Image.open(target) as capture:
                            capture.save(target.with_suffix('.png'))
                        target.unlink()
                        raise RuntimeError('The guest did not return the live check: ' + serial[-3000:])
                    if guest['result'] != 'passed':
                        raise RuntimeError('Live ISO check failed: ' + guest.get('error', 'unknown failure'))
                    if expected_revision and not guest['build']['revision'].startswith(expected_revision):
                        raise RuntimeError('The tested ISO has an unexpected source revision')
                    (output / 'result.json').write_text(json.dumps({'uefi_boot_observed_seconds': seconds, 'memory_mb': memory, 'acceleration': 'tcg', 'guest_status': qmp('query-status'), 'installation_executed': False, 'windows_dual_boot_tested': False, 'live_check': guest['result'], 'image_revision': guest['build']['revision']}, indent=2))
                    qmp('quit')
                process.wait(timeout=20)
            except BaseException as error:
                memory_info = {}
                for name in ('memory.max', 'memory.events', 'memory.peak'):
                    path = Path('/sys/fs/cgroup') / name
                    if path.is_file():
                        memory_info[name] = path.read_text()
                data = {'error': str(error), 'qemu_returncode': process.poll(), 'memory_mb': memory, 'memory_info': memory_info}
                (output / 'failure.json').write_text(json.dumps(data, indent=2))
                print(json.dumps(data), flush=True)
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--memory', type=int, default=2304)
    parser.add_argument('--expected-revision')
    args = parser.parse_args()
    if not 1024 <= args.memory <= 8192:
        parser.error('The test VM needs between 1024 and 8192 MiB of RAM.')
    boot(args.image, args.output, memory=args.memory, expected_revision=args.expected_revision)
