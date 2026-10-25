import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from .manifest import ForgeError, relative_path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".forge-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + "\n").encode())


def safe_target(user_root, relative):
    root = user_root.resolve()
    path = root / relative_path(relative)
    if not path.resolve().is_relative_to(root):
        raise ForgeError(f"Destination escapes home: {relative}")
    current = path
    while current != root:
        if current.is_symlink():
            raise ForgeError(f"Symlink destination needs manual migration: {relative}")
        current = current.parent
    if path.exists() and not path.is_file():
        raise ForgeError(f"Destination is not a regular file: {relative}")
    return path


class Deployment:
    def __init__(self, user_root, transaction_root):
        self.user_root = user_root.resolve()
        self.transaction_root = transaction_root
        self.journal_path = transaction_root / "files.json"
        self.entries = []
        if self.journal_path.exists():
            self.entries = json.loads(self.journal_path.read_text(encoding="utf-8"))

    def apply(self, files, source_root):
        prepared = []
        for item in files:
            source = (source_root / relative_path(item["source"])).resolve()
            if not source.is_relative_to(source_root.resolve()) or not source.is_file():
                raise ForgeError("Unsafe config source")
            target = safe_target(self.user_root, item["target"])
            if item.get("preserve") is True and target.exists():
                continue
            content = source.read_bytes()
            new_hash = hashlib.sha256(content).hexdigest()
            mode = 0o755 if item.get("executable", False) else 0o644
            if target.exists() and digest(target) == new_hash and (os.name == "nt" or stat.S_IMODE(target.stat().st_mode) == mode):
                continue
            prepared.append((item, target, content, new_hash, mode))
        for item, target, content, new_hash, mode in prepared:
            entry = {"target": item["target"], "installed_hash": new_hash, "installed_mode": mode, "backup": None}
            if target.exists():
                backup = f"backup/{len(self.entries)}"
                entry.update(backup=backup, previous_hash=digest(target), previous_mode=stat.S_IMODE(target.stat().st_mode))
                atomic_write(self.transaction_root / backup, target.read_bytes())
            self.entries.append(entry)
            write_json(self.journal_path, self.entries)
            atomic_write(target, content, mode)

    def rollback(self):
        conflicts = []
        for entry in reversed(self.entries):
            target = safe_target(self.user_root, entry["target"])
            current_hash = digest(target) if target.exists() else None
            current_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
            if entry.get("restored"):
                continue
            if current_hash == entry.get("previous_hash") and (os.name == "nt" or current_mode == entry.get("previous_mode")):
                entry["restored"] = True
                write_json(self.journal_path, self.entries)
                continue
            if current_hash != entry["installed_hash"] or (os.name != "nt" and "installed_mode" in entry and current_mode != entry["installed_mode"]):
                conflicts.append(entry["target"])
                continue
            if entry["backup"] is None:
                target.unlink()
            else:
                backup = self.transaction_root / relative_path(entry["backup"])
                if not backup.resolve().is_relative_to(self.transaction_root.resolve()) or digest(backup) != entry["previous_hash"]:
                    raise ForgeError("Backup failed integrity verification")
                atomic_write(target, backup.read_bytes(), entry["previous_mode"])
            entry["restored"] = True
            write_json(self.journal_path, self.entries)
        return conflicts
