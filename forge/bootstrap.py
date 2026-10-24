import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def root_arch():
    if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() != 0 or not Path("/etc/arch-release").is_file() or Path("/run/archiso").exists():
        raise ValueError("Account preparation needs root on an installed x86_64 Arch system")
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if release.get("ID", "").strip('"') != "arch":
        raise ValueError("Guided setup supports Arch Linux only")
    if subprocess.run(["systemd-detect-virt", "--chroot"], capture_output=True).returncode == 0:
        raise ValueError("Reboot into installed Arch before preparing the desktop")


def checked_system_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Refusing to replace an unsafe system file: {path}")


def enable_multilib(path=Path("/etc/pacman.conf"), backup_root=Path("/var/lib/hyprland-forge/system")):
    checked_system_file(path)
    content = path.read_text()
    if re.search(r"^\s*\[multilib\]\s*(?:#.*)?$", content, re.MULTILINE):
        return None
    if backup_root.is_symlink():
        raise ValueError("Unsafe system backup directory")
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = backup_root / ("pacman.conf-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    with backup.open("xb") as stream:
        stream.write(path.read_bytes())
    backup.chmod(0o600)
    descriptor, temporary = tempfile.mkstemp(prefix=".forge-pacman-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content.rstrip() + "\n\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.chmod(temporary, 0o600)
            os.unlink(temporary)
    return backup


def allow_sudo(username, directory=Path("/etc/sudoers.d"), runner=subprocess.run):
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        raise ValueError("Invalid account name")
    if directory.is_symlink():
        raise ValueError("Unsafe sudo configuration directory")
    directory.mkdir(exist_ok=True, mode=0o750)
    target = directory / ("forge-" + username)
    content = f"{username} ALL=(ALL:ALL) ALL\n"
    if target.exists() or target.is_symlink():
        checked_system_file(target)
        if target.read_text() != content:
            raise ValueError("An existing Forge sudo rule needs review")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".forge-", dir=directory)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        os.chmod(temporary, 0o440)
        runner(["visudo", "--check", "--file", temporary], check=True)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.chmod(temporary, 0o600)
            os.unlink(temporary)


def prepare_account(reader=None, runner=subprocess.run):
    import pwd
    from forge.setup import confirm
    reader = reader or input
    accounts = [p for p in pwd.getpwall() if 1000 <= p.pw_uid < 65534 and p.pw_shell not in ("/usr/bin/nologin", "/bin/false", "/sbin/nologin")]
    suggested = os.environ.get("SUDO_USER", "")
    if not suggested and len(accounts) == 1:
        suggested = accounts[0].pw_name
    if suggested and any(p.pw_name == suggested for p in accounts):
        if confirm(f"Install Forge for {suggested} and allow password-protected software installation?", reader=reader):
            return pwd.getpwnam(suggested)
    if accounts:
        print("Existing desktop accounts: " + ", ".join(p.pw_name for p in accounts))
    username = reader("Desktop username: ").strip()
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        raise ValueError("Use a lowercase username, up to 32 letters, digits, underscores or hyphens")
    try:
        account = pwd.getpwnam(username)
    except KeyError:
        if not confirm(f"Create {username} as your desktop account with password-protected sudo?", reader=reader):
            raise ValueError("Setup cancelled")
        runner(["useradd", "--create-home", "--groups", "wheel", "--shell", "/bin/bash", "--", username], check=True)
        runner(["passwd", username], check=True)
        account = pwd.getpwnam(username)
    else:
        if not any(p.pw_name == username for p in accounts):
            raise ValueError("Choose a normal desktop account, not root or a system account")
        if not confirm(f"Allow {username} to install software using their password?", reader=reader):
            raise ValueError("Setup cancelled")
    return account


def main(argv=None):
    try:
        root_arch()
        argv = sys.argv[1:] if argv is None else argv
        if argv == ["--multilib"]:
            backup = enable_multilib()
            if backup:
                print(f"Official multilib enabled. Previous configuration: {backup}")
            return 0
        if "--setup" not in argv:
            raise ValueError("Use the guided --setup mode to prepare an account")
        if not sys.stdin.isatty():
            raise ValueError("Account setup requires an interactive terminal")
        account = prepare_account()
        status = subprocess.run(["passwd", "--status", account.pw_name], capture_output=True, text=True, check=True).stdout.split()
        if len(status) < 2:
            raise ValueError("Could not determine the account's password status")
        if status[1] != "P":
            print("Set a password for the desktop account.")
            subprocess.run(["passwd", account.pw_name], check=True)
        allow_sudo(account.pw_name)
        source = Path(__file__).resolve().parent.parent
        command = ["runuser", "-u", account.pw_name, "--", "env", "HOME=" + account.pw_dir, "USER=" + account.pw_name, "LOGNAME=" + account.pw_name, "PATH=/usr/local/sbin:/usr/local/bin:/usr/bin", "bash", str(source / "install.sh"), *argv]
        return subprocess.run(command).returncode
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Forge: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Forge: cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
