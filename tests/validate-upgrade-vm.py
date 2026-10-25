import hashlib
import json
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path


assert "--disposable-vm" in sys.argv
assert os.geteuid() != 0 and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
root = Path(__file__).resolve().parent.parent
home = Path.home()
output = root / "test-results/qualification"
output.mkdir(parents=True, exist_ok=True)
paths = [".config/forge/interface.json", ".config/forge/taskbar.json", ".config/forge/theme.json", ".config/kitty/forge-colors.conf", ".config/fuzzel/forge-colors.ini", ".config/hypr/forge/colors.lua", ".config/hypr/user.lua", ".config/forge/preferences.json"]
before = {name: (home / name).read_bytes() for name in paths if (home / name).is_file()}
assert len(before) >= 6
process = None
master, slave = pty.openpty()
transcript = bytearray()
try:
    process = subprocess.Popen(["bash", str(root / "install.sh"), "--setup", "--profile", "virtual-machine"], cwd=root, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    os.write(master, b"y\ny\nn\n")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if select.select([master], [], [], 0.2)[0]:
            try:
                data = os.read(master, 8192)
            except OSError:
                break
            if not data:
                break
            transcript.extend(data)
        elif process.poll() is not None:
            break
    assert process.wait(timeout=10) == 0, transcript.decode(errors="replace")[-5000:]
    for name, data in before.items():
        assert (home / name).read_bytes() == data, "Preference changed: " + name
    setup = json.loads((home / ".local/state/hyprland-forge/setup.json").read_text())
    build = json.loads((root / "build.json").read_text())
    assert setup["release"] == build["version"] and setup["profile"] == "virtual-machine" and setup["gaming"] is True, setup
    assert not [value for value in json.loads(subprocess.check_output(["hyprctl", "-j", "configerrors"], text=True)) if value.strip()]
    report = {"result": "passed", "scope": "virtual-machine", "version": build["version"], "revision": build["revision"], "preferences_preserved": {name: hashlib.sha256(data).hexdigest() for name, data in before.items()}, "transaction": setup["transaction"], "physical_hardware_qualified": False}
    (output / "upgrade.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
    os.close(master)
    (output / "upgrade.log").write_bytes(transcript)
