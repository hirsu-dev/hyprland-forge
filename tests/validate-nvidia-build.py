import json
import os
import platform
import subprocess
from pathlib import Path

assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert platform.system() == 'Linux' and platform.machine() == 'x86_64'
assert os.geteuid() == 0 and Path('/etc/arch-release').is_file()
kernels = [path.parent.name for path in Path('/usr/lib/modules').glob('*/pkgbase') if path.read_text().strip() == 'linux']
assert len(kernels) == 1, kernels
kernel = kernels[0]
subprocess.run(['dkms', 'autoinstall', '-k', kernel], check=True)
subprocess.run(['depmod', '-a', kernel], check=True)
modules = []
for name in ('nvidia', 'nvidia_drm', 'nvidia_modeset', 'nvidia_uvm'):
    value = subprocess.check_output(['modinfo', '-k', kernel, '-F', 'vermagic', name], text=True).strip()
    assert value.split()[0] == kernel, (name, value)
    path = Path(subprocess.check_output(['modinfo', '-k', kernel, '-F', 'filename', name], text=True).strip())
    assert path.is_file() and path.resolve().is_relative_to(Path('/usr/lib/modules') / kernel)
    modules.append({'name': name, 'vermagic': value, 'file': str(path)})
services = ['nvidia-suspend.service', 'nvidia-resume.service', 'nvidia-hibernate.service']
assert all((Path('/usr/lib/systemd/system') / name).is_file() for name in services)
assert Path('/usr/bin/prime-run').is_file()
packages = subprocess.check_output(['pacman', '-Q', 'linux', 'linux-headers', 'nvidia-open-dkms', 'nvidia-utils', 'nvidia-prime', 'egl-wayland', 'dkms'], text=True).splitlines()
result = {'result': 'passed', 'revision': os.environ['GITHUB_SHA'], 'kernel': kernel, 'packages': packages, 'modules': modules, 'services_available': services, 'module_loading_attempted': False, 'physical_hardware_qualified': False}
output = Path('test-results/nvidia-driver.json')
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
