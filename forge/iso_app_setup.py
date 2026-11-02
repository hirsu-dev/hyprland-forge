import argparse
import json
import os
import platform
import stat
import subprocess
import sys
import time
from pathlib import Path

from .iso_apps import selection
from .manifest import ForgeError
from .storage import atomic_write


STATE = Path('/var/lib/hyprland-forge/optional-apps.json')
LOG = STATE.with_suffix('.log')
SERVICE = '''[Unit]
Description=Forge optional app downloads
Wants=network-online.target
After=network-online.target
ConditionPathExists=/var/lib/hyprland-forge/optional-apps.json
ConditionPathExists=!/etc/forge-live
StartLimitIntervalSec=3600
StartLimitBurst=3

[Service]
Type=exec
WorkingDirectory=/opt/hyprland-forge
ExecStart=/usr/bin/python -m forge.iso_app_setup --install
Restart=on-failure
RestartSec=120
TimeoutStopSec=15
KillMode=control-group
Nice=10
IOSchedulingClass=idle

[Install]
WantedBy=multi-user.target
'''
DESKTOP = '''[Desktop Entry]
Type=Application
Name=Forge App Setup
Comment=View and retry selected app downloads
Exec=kitty --title "Forge App Setup" --directory /opt/hyprland-forge python -m forge.iso_app_setup
Icon=system-software-install
Categories=System;Settings;
Terminal=false
'''


def save(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + '\n').encode(), 0o644)


def prepare(root, values):
    apps = [app['id'] for app in selection(values) if 'flatpak' in app]
    if not apps:
        return
    path = root / STATE.relative_to('/')
    save(path, {'schema': 1, 'apps': apps, 'status': 'pending', 'results': {}})
    atomic_write(root / 'etc/systemd/system/forge-app-setup.service', SERVICE.encode(), 0o644)
    atomic_write(root / 'usr/share/applications/forge-app-setup.desktop', DESKTOP.encode(), 0o644)


def install_pending(path=STATE, log=LOG, run=subprocess.run):
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('schema') != 1:
        raise ForgeError('App setup state is invalid.')
    apps = selection(value.get('apps'))
    if any('flatpak' not in app for app in apps):
        raise ForgeError('App setup contains an unsupported selection.')
    value.update(status='running', results={})
    save(path, value)
    log.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a', buffering=1) as stream:
        def command(arguments, timeout):
            stream.write('\n' + ' '.join(arguments) + '\n')
            stream.flush()
            result = run(arguments, stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=timeout)
            if result.returncode:
                raise ForgeError('Download command failed with exit status ' + str(result.returncode) + '.')
        try:
            missing = []
            for app in apps:
                result = run(['flatpak', 'info', '--system', app['flatpak']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=30)
                if result.returncode == 0:
                    value['results'][app['id']] = {'status': 'installed'}
                else:
                    missing.append(app)
            save(path, value)
            if missing:
                command(['flatpak', 'remote-add', '--system', '--if-not-exists', 'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'], 120)
            for app in missing:
                value['current'] = app['id']
                save(path, value)
                try:
                    command(['flatpak', 'install', '--system', '--assumeyes', '--noninteractive', 'flathub', app['flatpak']], 1200)
                    command(['flatpak', 'info', '--system', app['flatpak']], 30)
                    value['results'][app['id']] = {'status': 'installed'}
                except (ForgeError, OSError, subprocess.SubprocessError) as error:
                    stream.write(str(error) + '\n')
                    value['results'][app['id']] = {'status': 'retry-needed', 'error': str(error)[:600]}
                save(path, value)
        except (ForgeError, OSError, subprocess.SubprocessError) as error:
            stream.write(str(error) + '\n')
            value['error'] = str(error)[:600]
        value.pop('current', None)
        complete = all(value['results'].get(app['id'], {}).get('status') == 'installed' for app in apps)
        value['status'] = 'complete' if complete else 'retry-needed'
        if complete:
            value.pop('error', None)
        save(path, value)
    return complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('Forge App Setup runs on Linux.')
    if args.install:
        if os.geteuid() != 0 or Path('/etc/forge-live').exists():
            parser.error('App downloads run after booting the installed Forge system.')
        for path in (STATE, STATE.parent):
            info = path.lstat()
            if path.is_symlink() or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                parser.error('App setup state must belong to root and be protected from other users.')
        import fcntl
        descriptor = os.open(STATE.with_suffix('.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            return 0 if install_pending() else 1
    while STATE.is_file():
        value = json.loads(STATE.read_text())
        print('\033[2J\033[HForge App Setup\n')
        for app in selection(value['apps']):
            result = value.get('results', {}).get(app['id'], {})
            print(app['name'] + ': ' + result.get('status', 'waiting'))
        if value.get('current'):
            print('\nDownloading: ' + value['current'])
        if value['status'] == 'complete':
            print('\nYour selected apps are installed.')
            input('Press Enter to close.')
            return 0
        if value['status'] == 'retry-needed':
            print('\nSome downloads need another attempt. Your OS is installed.')
            print('Details: sudo journalctl -u forge-app-setup.service and ' + str(LOG))
            if input('Retry now? [y/N] ').strip().lower() not in ('y', 'yes'):
                return 0
            result = subprocess.run(['pkexec', 'systemctl', 'reset-failed', 'forge-app-setup.service'])
            if result.returncode:
                return result.returncode
            result = subprocess.run(['pkexec', 'systemctl', 'restart', 'forge-app-setup.service'])
            if result.returncode:
                return result.returncode
        else:
            print('\nDownloads continue in the background. Ctrl+C closes this view.')
        time.sleep(3)
    print('No optional app downloads are queued.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
