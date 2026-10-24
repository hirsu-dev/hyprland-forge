import logging
import os
import platform
import signal
import stat
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .everyday import initialize_defaults
from .manifest import ForgeError
from .storage import safe_target, write_json


class SessionLog(RotatingFileHandler):
    def _open(self):
        descriptor = os.open(self.baseFilename, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, "a", encoding=self.encoding, errors=self.errors)


class Component:
    def __init__(self, name, command, environment=None):
        self.name = name
        self.command = command
        self.environment = environment
        self.process = None
        self.started = 0
        self.retry_at = 0
        self.failures = 0
        self.restarts = 0
        self.last_exit = None

    def update(self, now, logger, factory=subprocess.Popen):
        if self.process is not None:
            result = self.process.poll()
            if result is None:
                return False
            terminate_group(self.process, signal.SIGKILL)
            if now - self.started >= 60:
                self.failures = 0
            self.last_exit = result
            self.process = None
            self.failures += 1
            self.retry_at = now + min(60, 2 ** min(self.failures, 6))
            logger.warning("%s exited (%s); retry in %ss", self.name, result, self.retry_at - now)
            return True
        if now < self.retry_at:
            return False
        try:
            self.process = factory(self.command, env=self.environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, close_fds=True, start_new_session=True)
        except OSError as exc:
            self.failures += 1
            self.retry_at = now + min(60, 2 ** min(self.failures, 6))
            self.last_exit = "unavailable"
            logger.warning("%s unavailable: %s", self.name, exc)
        else:
            if self.started:
                self.restarts += 1
            self.started = now
            logger.info("%s started", self.name)
        return True

    def status(self):
        return {"name": self.name, "running": self.process is not None and self.process.poll() is None, "restarts": self.restarts, "failures": self.failures, "last_exit": self.last_exit}


def terminate_group(process, signum):
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def stop_components(components):
    processes = [component.process for component in components if component.process is not None]
    for process in processes:
        terminate_group(process, signal.SIGTERM)
    deadline = time.monotonic() + 2
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for process in processes:
        terminate_group(process, signal.SIGKILL)
        process.wait()


def runtime_directory(environment):
    value = environment.get("XDG_RUNTIME_DIR", "")
    root = Path(value)
    if not value or not root.is_absolute() or root.is_symlink():
        raise ForgeError("A private XDG_RUNTIME_DIR is required")
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ForgeError("XDG_RUNTIME_DIR must belong to this user with mode 0700")
    return root


def acquire_lock(root):
    import fcntl
    descriptor = os.open(root / "hyprland-forge-session.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ForgeError("Unsafe session lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return None
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def prepare(home, logger):
    variables = [key for key in ("WAYLAND_DISPLAY", "DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "XDG_SESSION_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE") if key in os.environ]
    commands = [
        (["dbus-update-activation-environment", "--systemd", *variables], "session environment activation failed"),
        (["systemctl", "--user", "start", "hyprpolkitagent.service"], "authentication agent unavailable"),
        (["xdg-user-dirs-update"], "user directories unavailable"),
    ]
    recovery = home / ".local/bin/forge-settings"
    if recovery.is_file() and os.access(recovery, os.X_OK):
        commands.append(([str(recovery), "--recover"], "display recovery unavailable"))
    for command, message in commands:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
            if result.returncode:
                logger.warning(message)
        except (OSError, subprocess.TimeoutExpired):
            logger.warning(message)
    try:
        initialize_defaults(home)
    except (ForgeError, OSError):
        logger.warning("Default apps could not be initialized")
    try:
        subprocess.run(["makoctl", "quit"], stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def components(home):
    result = [
        Component("idle", ["hypridle"]),
        Component("clipboard-text", ["wl-paste", "--type", "text", "--watch", "cliphist", "store"]),
        Component("clipboard-image", ["wl-paste", "--type", "image", "--watch", "cliphist", "store"]),
        Component("wallpaper", [str(home / ".local/bin/forge-wallpaper")]),
    ]
    config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    if (config / "quickshell/forge/shell.qml").is_file():
        from .hardware import virtualization
        environment = dict(os.environ)
        if virtualization():
            environment["QT_QUICK_BACKEND"] = "software"
        result.append(Component("shell", ["quickshell", "-c", "forge"], environment))
    return result


def main():
    if platform.system() != "Linux":
        print("Forge session requires Linux", file=sys.stderr)
        return 1
    descriptor = None
    services = []
    stopped = threading.Event()
    old_handlers = {}
    logger = logging.getLogger("forge.session")
    logger.setLevel(logging.INFO)
    try:
        root = runtime_directory(os.environ)
        descriptor = acquire_lock(root)
        if descriptor is None:
            return 0
        home = Path.home()
        path = safe_target(home, ".local/state/hyprland-forge/session.log")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = SessionLog(path, maxBytes=262144, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.addHandler(logging.StreamHandler())
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
        prepare(home, logger)
        services = components(home)
        check_at, status_at, missing = 0, 0, 0
        while not stopped.is_set():
            now = time.monotonic()
            if now >= check_at:
                try:
                    alive = subprocess.run(["hyprctl", "-j", "monitors"], stdin=subprocess.DEVNULL, capture_output=True, timeout=3).returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    alive = False
                missing = 0 if alive else missing + 1
                check_at = now + 5
                if missing >= 3:
                    break
            changed = False
            for service in services:
                changed = service.update(now, logger) or changed
            if changed or now >= status_at:
                write_json(root / "hyprland-forge-session.json", {"running": True, "pid": os.getpid(), "updated": time.time(), "components": [service.status() for service in services]})
                status_at = now + 5
            stopped.wait(0.5)
        return 0
    except (ForgeError, OSError) as exc:
        print("Forge session: " + str(exc), file=sys.stderr)
        return 1
    finally:
        stop_components(services)
        if descriptor is not None:
            try:
                write_json(root / "hyprland-forge-session.json", {"running": False, "components": []})
            except OSError:
                pass
            os.close(descriptor)
        for signum, previous in old_handlers.items():
            signal.signal(signum, previous)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
