import os
import subprocess
import time
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
