import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .manifest import ForgeError, load_manifest, make_plan
from .storage import Deployment, atomic_write, write_json
from .iso_apps import flatpak_commands, selection


SOURCE = Path('/opt/hyprland-forge')
OPTIONS = Path('/run/forge-installer/options.json')


def options(path=OPTIONS):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 4096:
        raise ForgeError('Return to the Forge welcome screen and choose your installation options.')
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != {'gaming', 'motion', 'apps'} or any(type(value[key]) is not bool for key in ('gaming', 'motion')):
        raise ForgeError('Installation options are invalid.')
    selection(value['apps'])
    return value


def guard(source=SOURCE):
    if platform.system() != 'Linux' or os.geteuid() != 0:
        raise ForgeError('The graphical installer runs only from the Forge live USB.')
    if not Path('/etc/forge-live').is_file() or not Path('/run/archiso/bootmnt').is_mount():
        raise ForgeError('Boot the Forge USB before installing.')
    if not Path('/sys/firmware/efi').is_dir():
        raise ForgeError('Restart the USB in UEFI mode before installing.')
    for variable in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        data = variable.read_bytes()
        if len(data) < 5 or data[4] != 0:
            raise ForgeError('This experimental installer requires Secure Boot to be disabled.')
    state = json.loads((source / 'iso/state.json').read_text())
    if state.get('disk_execution_enabled') is not True:
        virtual = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True, text=True, timeout=5)
        if virtual.returncode != 0 or virtual.stdout.strip() not in ('kvm', 'qemu', 'oracle') or 'forge.install_test=1' not in Path('/proc/cmdline').read_text().split():
            raise ForgeError('This ISO is a preview. Installation is restricted to explicitly enabled virtual-machine tests.')
    return options()


def mounted_target(value):
    if not isinstance(value, str):
        raise ForgeError('The installation target is missing.')
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.parent != Path('/tmp') or not re.fullmatch(r'calamares-root-[a-zA-Z0-9_-]+', path.name):
        raise ForgeError('The installation target is invalid.')
    if path.resolve() != path or not path.is_mount():
        raise ForgeError('The selected installation filesystem is not mounted.')
    return path


def hardware():
    cpu = Path('/proc/cpuinfo').read_text()
    vendors = set()
    for path in Path('/sys/bus/pci/devices').glob('*'):
        try:
            if int((path / 'class').read_text().strip(), 16) >> 16 == 3:
                vendors.add((path / 'vendor').read_text().strip())
        except (OSError, ValueError):
            continue
    result = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True, text=True, timeout=5)
    return {'cpu': 'amd' if 'AuthenticAMD' in cpu else 'intel' if 'GenuineIntel' in cpu else '', 'gpus': vendors, 'virtual': result.stdout.strip() if result.returncode == 0 else ''}


def package_plan(manifest, device, gaming, apps=None):
    packages = set(make_plan(manifest, None)['packages'])
    packages.difference_update({'amd-ucode', 'nvidia-open-dkms', 'nvidia-utils', 'nvidia-prime', 'egl-wayland', 'vulkan-radeon'})
    packages.update({'base', 'linux', 'linux-firmware', 'sudo', 'sddm', 'weston', 'ttf-dejavu', 'grub', 'efibootmgr', 'dosfstools', 'btrfs-progs', 'plymouth', 'python-pillow'})
    virtual = bool(device['virtual'])
    if virtual:
        packages.add('vulkan-swrast')
        if device['virtual'] == 'oracle':
            packages.add('virtualbox-guest-utils')
    else:
        if device['cpu']:
            packages.add(device['cpu'] + '-ucode')
        if '0x1002' in device['gpus']:
            packages.add('vulkan-radeon')
        if '0x8086' in device['gpus']:
            packages.add('vulkan-intel')
        if '0x10de' in device['gpus']:
            packages.update({'linux-headers', 'nvidia-open-dkms', 'nvidia-utils', 'nvidia-prime', 'egl-wayland'})
    if gaming:
        packages.update({'steam', 'lutris', 'lib32-mesa', 'lib32-vulkan-icd-loader', 'lib32-gamemode', 'lib32-mangohud'})
        for native, compat in (('vulkan-radeon', 'lib32-vulkan-radeon'), ('vulkan-intel', 'lib32-vulkan-intel'), ('nvidia-utils', 'lib32-nvidia-utils'), ('vulkan-swrast', 'lib32-vulkan-swrast')):
            if native in packages:
                packages.add(compat)
    selected = selection(apps or [])
    packages.update(app['package'] for app in selected if 'package' in app)
    if any('flatpak' in app for app in selected):
        packages.add('flatpak')
    return sorted(packages)


def windows_menu(entries):
    lines = []
    for identifier in sorted(set(entries)):
        if not re.fullmatch(r'[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}', identifier):
            raise ForgeError('Windows EFI filesystem identity is invalid.')
        lines.extend(['menuentry "Windows Boot Manager" {', '    insmod part_gpt', '    insmod fat', f'    search --no-floppy --fs-uuid --set=root {identifier}', '    chainloader /EFI/Microsoft/Boot/bootmgfw.efi', '}'])
    return '#!/bin/sh\nexec cat <<\'FORGE_WINDOWS\'\n' + '\n'.join(lines) + '\nFORGE_WINDOWS\n'


def find_windows():
    tree = json.loads(subprocess.run(['lsblk', '--json', '--paths', '--output', 'PATH,TYPE,FSTYPE,UUID,PARTTYPE'], check=True, capture_output=True, text=True).stdout)
    found = []
    def visit(nodes):
        for node in nodes:
            yield node
            yield from visit(node.get('children', []))
    for node in visit(tree['blockdevices']):
        if node.get('type') != 'part' or node.get('fstype') != 'vfat' or str(node.get('parttype', '')).lower() != 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b':
            continue
        device = node['path']
        if not re.fullmatch(r'/dev/[a-zA-Z0-9_/-]+', device):
            raise ForgeError('Unexpected EFI partition device.')
        with tempfile.TemporaryDirectory(prefix='forge-efi-') as directory:
            result = subprocess.run(['mount', '-o', 'ro,nosuid,nodev,noexec', '--', device, directory], capture_output=True, text=True)
            if result.returncode:
                raise ForgeError('Could not inspect an EFI partition; Windows boot detection needs review.')
            try:
                if (Path(directory) / 'EFI/Microsoft/Boot/bootmgfw.efi').is_file():
                    found.append(node['uuid'])
            finally:
                subprocess.run(['umount', '--', directory], check=True)
    return found


def base(root, source, settings, device):
    manifest = load_manifest(source)
    packages = package_plan(manifest, device, settings['gaming'], settings['apps'])
    with tempfile.TemporaryDirectory(prefix='forge-pacman-') as directory:
        config = Path(directory) / 'pacman.conf'
        text = Path('/etc/pacman.conf').read_text()
        if settings['gaming'] and not re.search(r'^\s*\[multilib\]\s*$', text, re.MULTILINE):
            text += '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n'
        config.write_text(text)
        subprocess.run(['pacstrap', '-K', '-C', str(config), str(root), *packages], check=True)
    if settings['gaming']:
        from .bootstrap import enable_multilib
        enable_multilib(root / 'etc/pacman.conf', root / 'var/lib/hyprland-forge/system')
    for command in flatpak_commands(settings['apps']):
        subprocess.run(['arch-chroot', str(root), *command], check=True)
    target_source = root / 'opt/hyprland-forge'
    if target_source.exists():
        raise ForgeError('The target already contains an installer. Choose an empty installation filesystem.')
    shutil.copytree(source, target_source, ignore=shutil.ignore_patterns('.git', '__pycache__', 'test-results', '.cache'))
    write_json(root / 'var/lib/hyprland-forge/iso-install.json', {'phase': 'base-complete', 'settings': settings, 'packages': packages, 'hardware': {**device, 'gpus': sorted(device['gpus'])}})


def finish(root, source, settings, device, username):
    if not isinstance(username, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        raise ForgeError('The installed account is invalid.')
    users = [line.split(':') for line in (root / 'etc/passwd').read_text().splitlines() if line.split(':')[0] == username]
    if len(users) != 1 or len(users[0]) != 7 or not 1000 <= int(users[0][2]) < 65534 or users[0][5] != '/home/' + username:
        raise ForgeError('A normal user account must be created before the desktop is installed.')
    uid, gid = int(users[0][2]), int(users[0][3])
    home = root / 'home' / username
    if not home.is_dir() or home.is_symlink() or not home.resolve().is_relative_to(root):
        raise ForgeError('The account home directory is unsafe.')
    manifest = load_manifest(source)
    plan = make_plan(manifest, None)
    if device['virtual']:
        plan['files'] = [{**item, 'source': 'configs/mpv/virtual-machine.conf'} if item['target'] == '.config/mpv/mpv.conf' else item for item in plan['files']]
    state = home / '.local/state/hyprland-forge'
    transaction = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    journal = state / 'transactions' / transaction
    journal.mkdir(parents=True, mode=0o700)
    Deployment(home, journal).apply(plan['files'], source)
    write_json(journal / 'transaction.json', {'id': transaction, 'status': 'complete', 'plan': plan, 'commands_completed': [], 'services_enabled': []})
    write_json(state / 'latest.json', {'id': transaction})
    write_json(state / 'setup.json', {'status': 'complete', 'release': manifest['release'], 'profile': 'virtual-machine' if device['virtual'] else 'iso-hardware', 'gaming': settings['gaming'], 'apps': settings['apps'], 'transaction': transaction, 'installer': '/opt/hyprland-forge'})
    atomic_write(state / 'setup-complete', (manifest['release'] + '\n').encode())
    interface = home / '.config/forge/interface.json'
    values = json.loads(interface.read_text())
    values['motion'] = settings['motion']
    write_json(interface, values)
    for path in [home, *home.rglob('*')]:
        if path.is_symlink():
            raise ForgeError('Unexpected symlink in the new account home.')
        os.chown(path, uid, gid)
    services = ['NetworkManager', 'bluetooth', 'power-profiles-daemon', 'fstrim.timer', 'sddm']
    if device['virtual'] == 'oracle':
        services.append('vboxservice')
    if not device['virtual'] and '0x10de' in device['gpus']:
        services.extend(['nvidia-suspend', 'nvidia-hibernate', 'nvidia-resume'])
    subprocess.run(['systemctl', '--root', str(root), 'enable', *services], check=True)
    subprocess.run(['systemctl', '--root', str(root), 'set-default', 'graphical.target'], check=True)
    atomic_write(root / 'etc/grub.d/41_forge_windows', windows_menu(find_windows()).encode(), 0o755)
    from .iso_assets import install_boot_assets
    install_boot_assets(root, source)
    write_json(root / 'var/lib/hyprland-forge/iso-install.json', {'phase': 'desktop-complete', 'release': manifest['release'], 'username': username, 'settings': settings})


def calamares_job(action):
    import libcalamares
    try:
        settings = guard()
        if action == 'guard':
            return None
        root = mounted_target(libcalamares.globalstorage.value('rootMountPoint'))
        device = hardware()
        if action == 'base':
            base(root, SOURCE, settings, device)
        elif action == 'finish':
            finish(root, SOURCE, settings, device, libcalamares.globalstorage.value('username'))
        else:
            raise ForgeError('Unknown installation task.')
    except (ForgeError, OSError, ValueError, subprocess.SubprocessError) as error:
        return ('Forge installation stopped', str(error))
    return None
