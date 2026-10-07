import configparser
import shlex
import shutil
from pathlib import Path


unit = configparser.ConfigParser(strict=False, interpolation=None)
unit.read("/usr/lib/systemd/system/sddm.service")
assert "display-manager.service" in unit["Install"]["Alias"].split()
assert Path(shlex.split(unit["Service"]["ExecStart"])[0]).is_file()
sessions = list(Path("/usr/share/wayland-sessions").glob("*hyprland*.desktop"))
assert sessions, "Hyprland must provide a login session"
available = []
for session in sessions:
    desktop = configparser.ConfigParser(interpolation=None)
    desktop.read(session)
    entry = desktop["Desktop Entry"]
    if entry.get("TryExec") and not shutil.which(entry["TryExec"]):
        continue
    command = shlex.split(entry["Exec"])
    assert command and shutil.which(command[0]), session
    available.append(session.name)
assert "hyprland.desktop" in available, "The direct Hyprland session must be usable without UWSM"
print("SDDM service and Hyprland session entries verified")
