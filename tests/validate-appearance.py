from pathlib import Path
from configparser import ConfigParser
from kitty.config import load_config

root = Path.cwd()
errors = []
options = load_config(str(root / "configs/kitty/kitty.conf"), accumulate_bad_lines=errors)
assert not errors, errors
assert str(options.background) == "#100d16"
settings = ConfigParser()
settings.read(root / "configs/qt6ct/qt6ct.conf")
assert settings.getboolean("Appearance", "custom_palette")
assert Path(settings.get("Appearance", "color_scheme_path")).is_file()
assert Path("/usr/share/icons/Papirus-Dark/index.theme").is_file()
for version in ("3", "4"):
    settings.read(root / f"configs/gtk-{version}.0/settings.ini")
    assert settings.getboolean("Settings", "gtk-application-prefer-dark-theme")
print("Terminal parser, Qt palette and icon assets passed")
