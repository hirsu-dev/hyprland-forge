import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge.everyday import DEFAULTS, initialize_defaults


with tempfile.TemporaryDirectory(prefix="forge-everyday-") as directory:
    home = Path(directory)
    environment = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"), "XDG_DATA_DIRS": "/usr/share", "XDG_CURRENT_DESKTOP": "Hyprland", "LC_ALL": "C.UTF-8"}
    subprocess.run(["xdg-user-dirs-update"], env=environment, check=True)
    assert (home / "Downloads").is_dir()
    assert (home / "Pictures").is_dir()
    assert initialize_defaults(home, environment)
    for desktop, types in DEFAULTS.items():
        assert (Path("/usr/share/applications") / desktop).is_file(), desktop
        for mime in types:
            actual = subprocess.check_output(["xdg-mime", "query", "default", mime], env=environment, text=True).strip()
            assert actual == desktop, (mime, actual, desktop)
    target = home / ".config/mimeapps.list"
    custom = "[Default Applications]\ntext/html=my-browser.desktop;\n"
    target.write_text(custom)
    assert not initialize_defaults(home, environment)
    assert target.read_text() == custom
print("Native Arch default app resolution, installed desktop entries, user folders and preference preservation passed")
