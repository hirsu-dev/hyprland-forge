import os
import subprocess
import time
import shutil
from pathlib import Path


root = Path(__file__).resolve().parent.parent
results = root / 'test-results'
results.mkdir(exist_ok=True)
with (results / 'iso-calamares.log').open('w') as stream:
    process = subprocess.Popen(['calamares', '-d'], stdout=stream, stderr=subprocess.STDOUT)
    try:
        time.sleep(12)
        if process.poll() is not None:
            raise RuntimeError('Calamares exited before the setup screen could be reviewed.')
        subprocess.run(['scrot', '--overwrite', str(results / 'iso-calamares.png')], check=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
text = (results / 'iso-calamares.log').read_text(errors='replace')
for message in ('Failed to load module', 'Cannot load module', 'Failed to load branding', 'No valid configuration file'):
    if message.lower() in text.lower():
        raise RuntimeError('The graphical installer configuration did not load: ' + message)
print('Calamares configuration loaded; screenshot captured. No installation was performed.')
greeter = shutil.which('sddm-greeter-qt6') or shutil.which('sddm-greeter')
if not greeter:
    raise RuntimeError('The SDDM theme preview program is missing.')
with (results / 'iso-greeter.log').open('w') as stream:
    process = subprocess.Popen([greeter, '--test-mode', '--theme', str(root / 'iso/boot/sddm')], stdout=stream, stderr=subprocess.STDOUT, env={**os.environ, 'QT_QUICK_CONTROLS_STYLE': 'Basic'})
    try:
        time.sleep(6)
        if process.poll() is not None:
            raise RuntimeError('The Forge login theme could not open in test mode.')
        subprocess.run(['scrot', '--overwrite', str(results / 'iso-greeter.png')], check=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
log = (results / 'iso-greeter.log').read_text(errors='replace')
if any(message in log for message in ('TypeError:', 'ReferenceError:', 'is not a type', 'Error loading the theme')):
    raise RuntimeError('The Forge login theme reported a QML error.')
print('Forge SDDM theme rendered in test mode. Password authentication was not tested.')
