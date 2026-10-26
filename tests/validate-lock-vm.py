import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

assert "--disposable-vm" in sys.argv
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "hyprlock"], capture_output=True).returncode == 1
with tempfile.TemporaryFile(mode="w+t") as output:
    process = subprocess.Popen([str(Path.home() / ".local/bin/forge-lock"), "--no-fade-in", "--verbose"], stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
    try:
        time.sleep(5)
        output.seek(0)
        log = output.read()
        assert process.poll() is None, log[-5000:]
        assert b"LIBGL_ALWAYS_SOFTWARE=1" in Path(f"/proc/{process.pid}/environ").read_bytes()
        process.send_signal(signal.SIGUSR1)
        assert process.wait(timeout=15) == 0, log[-5000:]
        subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, check=True, timeout=10)
        print(json.dumps({"lock_rendering": "passed", "software_graphics": True, "unlock_signal": "passed", "password_authentication": "not-tested", "scope": "virtual-machine"}))
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGUSR1)
            process.wait(timeout=15)
