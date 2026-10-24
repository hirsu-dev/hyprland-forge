import os
import tempfile
from pathlib import Path

from .storage import safe_target


DEFAULTS = {
    "thunar.desktop": ("inode/directory",),
    "firefox.desktop": ("text/html", "x-scheme-handler/http", "x-scheme-handler/https"),
    "org.xfce.mousepad.desktop": ("text/plain",),
    "org.gnome.Evince.desktop": ("application/pdf",),
    "org.xfce.ristretto.desktop": ("image/png", "image/jpeg", "image/gif", "image/webp"),
    "mpv.desktop": ("video/mp4", "video/webm", "video/x-matroska", "audio/mpeg", "audio/flac", "audio/ogg"),
    "xarchiver.desktop": ("application/zip", "application/x-7z-compressed", "application/x-tar", "application/gzip", "application/x-xz"),
}


def initialize_defaults(home, environment=None):
    environment = os.environ if environment is None else environment
    home = Path(home).resolve()
    config = Path(environment.get("XDG_CONFIG_HOME") or home / ".config")
    data = Path(environment.get("XDG_DATA_HOME") or home / ".local/share")
    if not config.is_absolute() or not data.is_absolute():
        return False
    if any(path.exists() or path.is_symlink() for path in (config / "mimeapps.list", config / "hyprland-mimeapps.list", data / "applications/mimeapps.list")):
        return False
    try:
        relative = (config / "mimeapps.list").relative_to(home).as_posix()
    except ValueError:
        return False
    target = safe_target(home, relative)
    directories = [data, *(Path(p) for p in environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p and Path(p).is_absolute())]
    entries = [f"{mime}={desktop};" for desktop, types in DEFAULTS.items() if any((directory / "applications" / desktop).is_file() for directory in directories) for mime in types]
    if not entries:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".forge-defaults-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("[Default Applications]\n" + "\n".join(entries) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            return False
        return True
    finally:
        os.unlink(temporary)
