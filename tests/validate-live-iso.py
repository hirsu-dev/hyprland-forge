import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path


def command(arguments, environment=None):
    result = subprocess.run(arguments, env=environment, capture_output=True, text=True, timeout=30)
    return {'exit_code': result.returncode, 'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}


def main():
    report = {'scope': 'live-ISO-in-disposable-QEMU', 'installation_executed': False, 'physical_hardware_tested': False, 'result': 'running'}
    try:
        assert os.geteuid() == 0 and Path('/etc/forge-live').is_file()
        assert Path('/run/archiso/bootmnt').is_mount()
        virtual = command(['systemd-detect-virt', '--vm'])
        assert virtual['stdout'] in ('qemu', 'kvm'), virtual
        source = Path('/opt/hyprland-forge')
        report['build'] = json.loads((source / 'build.json').read_text())
        report['state'] = json.loads((source / 'iso/state.json').read_text())['disk_execution_enabled']
        report['theme_hashes'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (source / 'iso/boot/sddm').glob('*.qml')}
        environment = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/root/.Xauthority', 'QT_QUICK_BACKEND': 'software', 'QT_QUICK_CONTROLS_STYLE': 'Basic'}
        for path in (Path('/var/log/Xorg.0.log'), Path('/root/.local/share/xorg/Xorg.0.log')):
            if path.is_file():
                match = re.search(r'using VT number (\d+)', path.read_text(errors='replace'), re.I)
                if match:
                    report['graphical_vt'] = int(match[1])
                    subprocess.run(['chvt', match[1]], check=True, timeout=10)
                    break
        assert report.get('graphical_vt'), 'The live graphical session VT could not be identified'
        report['screen'] = command(['xset', 'q'], environment)
        report['inhibitors'] = command(['systemd-inhibit', '--list', '--no-pager'])
        report['network'] = command(['nmcli', '-t', '-f', 'STATE', 'general'])
        report['mounted_filesystems'] = command(['findmnt', '-rn', '-o', 'SOURCE,TARGET'])
        report['failed_services'] = command(['systemctl', '--failed', '--plain', '--no-legend', '--no-pager'])
        report['failed_units'] = [line.split()[0] for line in report['failed_services']['stdout'].splitlines() if line.strip()]
        report['kernel'] = command(['uname', '-r'])['stdout']
        with urllib.request.urlopen('https://archlinux.org/', timeout=30) as response:
            report['HTTPS_access'] = response.status
        assert report['screen']['exit_code'] == 0, report['screen']
        assert re.search(r'timeout:\s+0\b', report['screen']['stdout']), report['screen']
        assert 'DPMS is Disabled' in report['screen']['stdout'] or 'does not have the DPMS Extension' in report['screen']['stdout'], report['screen']
        inhibitors = report['inhibitors']['stdout']
        assert 'Forge Setup' in inhibitors and 'sleep:idle:handle-lid-switch' in inhibitors, report['inhibitors']
        assert report['HTTPS_access'] == 200
        assert not any(line.startswith(('/dev/vda', '/dev/sda')) for line in report['mounted_filesystems']['stdout'].splitlines())
        sys.path.insert(0, str(source))
        from forge.iso_install import guard
        from forge.manifest import ForgeError
        try:
            guard()
        except ForgeError as error:
            report['unconfigured_installation_guard'] = str(error)
        else:
            raise AssertionError('Installation accepted a missing setup selection')
        with Path('/tmp/forge-live-calamares.log').open('w') as stream:
            process = subprocess.Popen(['calamares', '-d'], env=environment, stdout=stream, stderr=subprocess.STDOUT)
            try:
                time.sleep(10)
                assert process.poll() is None, Path('/tmp/forge-live-calamares.log').read_text(errors='replace')[-4000:]
                print('FORGE_ISO_INSTALLER_READY', flush=True)
                time.sleep(12)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)
        report['graphical_installer_opened'] = True
        log = Path('/tmp/forge-live-calamares.log').read_text(errors='replace')
        assert not any(text.lower() in log.lower() for text in ('Failed to load module', 'Cannot load module', 'Failed to load branding', 'No valid configuration file')), log[-4000:]
        assert not report['failed_units'], report['failed_units']
        report['result'] = 'passed'
    except BaseException as error:
        report.update(result='failed', error=str(error), traceback=traceback.format_exc())
    print('FORGE_ISO_REPORT=' + json.dumps(report), flush=True)
    return 0 if report['result'] == 'passed' else 1


raise SystemExit(main())
