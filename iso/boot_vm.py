import argparse
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path


def boot(image, output, seconds=240):
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
    accelerated = Path('/dev/kvm').exists()
    command = ['qemu-system-x86_64', '-enable-kvm'] if accelerated else ['qemu-system-x86_64', '-accel', 'tcg,thread=multi']
    command += ['-machine', 'q35', '-m', '3072', '-smp', '2', '-cpu', 'host' if accelerated else 'max', '-drive', f'if=pflash,format=raw,readonly=on,file={firmware}', '-drive', f'if=pflash,format=raw,file={variables}', '-cdrom', str(image), '-boot', 'd', '-drive', f'file={disk},format=qcow2,if=virtio', '-netdev', 'user,id=forge', '-device', 'virtio-net-pci,netdev=forge', '-vga', 'virtio', '-display', 'none', '-qmp', f'unix:{monitor},server=on,wait=off', '-serial', 'file:' + str(output / 'serial.log')]
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
                    connection.settimeout(10)
                    connection.connect(str(monitor))
                    stream = connection.makefile('rwb', buffering=0)
                    stream.readline()
                    def qmp(name, arguments=None):
                        stream.write((json.dumps({'execute': name, 'arguments': arguments or {}}) + '\n').encode())
                        while True:
                            value = json.loads(stream.readline())
                            if 'error' in value:
                                raise RuntimeError(str(value['error']))
                            if 'return' in value:
                                return value['return']
                    qmp('qmp_capabilities')
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
                    (output / 'result.json').write_text(json.dumps({'uefi_boot_observed_seconds': seconds, 'guest_status': qmp('query-status'), 'installation_executed': False, 'windows_dual_boot_tested': False}, indent=2))
                    qmp('quit')
                process.wait(timeout=20)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    boot(args.image, args.output)
