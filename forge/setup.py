import json
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .hardware import resolve_plan, virtualization
from .login import resolve_plan as resolve_login
from .manifest import ForgeError, load_manifest, make_plan, relative_path
from .runtime import execute, lock, preflight
from .storage import atomic_write, safe_target, write_json


GAMING = ("steam", "lutris", "lib32-mesa", "lib32-vulkan-radeon", "lib32-nvidia-utils", "lib32-vulkan-icd-loader", "lib32-gamemode", "lib32-mangohud")


def confirm(question, default=True, reader=None):
    reader = reader or input
    while True:
        answer = reader(question + (" [Y/n] " if default else " [y/N] ")).strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer yes or no.")


def with_gaming(plan, source_root):
    packages = [p for p in GAMING if plan["profile"] != "virtual-machine" or p not in ("lib32-nvidia-utils", "lib32-vulkan-radeon")]
    plan["packages"] = list(dict.fromkeys([*plan["packages"], *packages]))
    plan["commands"] = [
        ["sudo", sys.executable, str(source_root / "forge/bootstrap.py"), "--multilib"],
        ["sudo", "pacman", "-Syu", "--needed", "--", *plan["packages"]],
    ]
    return plan


def cache_installer(source_root, home, manifest):
    safe_target(home, ".local/share/hyprland-forge/installers/.guard")
    parent = home / ".local/share/hyprland-forge/installers"
    parent.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix=manifest["release"] + "-", dir=parent))
    names = {"install.sh", "live.sh", "install-online.sh", "project.json"}
    names.update("forge/" + p.name for p in (source_root / "forge").glob("*.py"))
    names.update(item["source"] for stage in manifest["stages"] for item in stage.get("files", []))
    for name in sorted(names):
        source = source_root / relative_path(name)
        if source.is_symlink() or not source.resolve().is_relative_to(source_root.resolve()):
            raise ForgeError("Unsafe installer source")
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if name.endswith(".sh") or name.startswith("configs/bin/") else 0o644)
    return target


class LoggedRunner:
    def __init__(self, stream):
        self.stream = stream

    def __call__(self, command, **kwargs):
        self.stream.write(json.dumps(command) + "\n")
        self.stream.flush()
        if command[:2] != ["sudo", "pacman"]:
            result = subprocess.run(command, **kwargs)
            if kwargs.get("capture_output"):
                self.stream.write((result.stdout or "") + (result.stderr or ""))
            self.stream.flush()
            return result
        command = [*command[:3], "--noconfirm", *command[3:]]
        tail = deque(maxlen=15)
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace") as process:
            for line in process.stdout:
                self.stream.write(line)
                self.stream.flush()
                tail.append(line.rstrip())
            result = process.wait()
        if result:
            print("\n".join(tail), file=sys.stderr)
            raise subprocess.CalledProcessError(result, command)
        return subprocess.CompletedProcess(command, 0, "", "")


def ensure_network():
    if not shutil.which("nm-online"):
        return
    if subprocess.run(["nm-online", "--quiet", "--timeout=5"]).returncode == 0:
        return
    print("Connect this computer to the internet using the network screen.")
    subprocess.run(["sudo", "systemctl", "start", "NetworkManager.service"], check=True)
    subprocess.run(["nmtui", "connect"], check=True)
    if subprocess.run(["nm-online", "--quiet", "--timeout=15"]).returncode != 0:
        raise ForgeError("No network connection was established. Re-run setup when connected")


def run(source_root, profile=None, login="auto"):
    if not sys.stdin.isatty():
        raise ForgeError("Guided setup needs an interactive terminal")
    preflight()
    profile = profile or ("virtual-machine" if virtualization() else "laptop")
    manifest = load_manifest(source_root)
    plan = resolve_login(resolve_plan(make_plan(manifest, None), apply=True, profile=profile), mode=login, apply=True)
    print(f"\nHYPRLAND FORGE  {manifest['release']}\n")
    print("Cyberpunk desktop, apps, audio, networking, display controls and hardware drivers.")
    print("Arch will receive a full update. Existing managed configs are backed up.")
    print("Hardware: " + ("virtual machine" if profile == "virtual-machine" else "AMD / NVIDIA laptop"))
    print("Login: " + ("SDDM" if plan.get("login", {}).get("action") == "enable-sddm" else "keep current login"))
    if not confirm("Install Forge on this Arch system?"):
        print("Setup cancelled.")
        return 0
    gaming = confirm("Include Steam and gaming support?")
    home = Path.home()
    state = home / ".local/state/hyprland-forge"
    safe_target(home, ".local/state/hyprland-forge/setup.json")
    safe_target(home, ".local/state/hyprland-forge/setup-complete")
    safe_target(home, ".local/state/hyprland-forge/logs/.guard")
    cached = cache_installer(source_root, home, manifest)
    if gaming:
        plan = with_gaming(plan, cached)
        print("Official multilib packages will be enabled for Steam.")
    subprocess.run(["sudo", "-v"], check=True)
    logs = state / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / ("setup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + cached.name + ".log")
    print("Installing packages and desktop settings. This can take several minutes.")
    print(f"Details: {log}")
    with lock(state), log.open("x", encoding="utf-8") as stream:
        log.chmod(0o600)
        try:
            ensure_network()
            transaction = execute(plan, cached, home, state, runner=LoggedRunner(stream))
        except BaseException as exc:
            stream.write(type(exc).__name__ + ": " + str(exc) + "\n")
            print(f"Setup stopped. Details are saved in {log}", file=sys.stderr)
            print("Re-run the same installation command to retry.", file=sys.stderr)
            raise
        write_json(state / "setup.json", {"status": "complete", "release": manifest["release"], "transaction": transaction, "installer": str(cached), "gaming": gaming, "log": str(log)})
        atomic_write(state / "setup-complete", (manifest["release"] + "\n").encode())
    print(f"\nForge is installed. Configuration backup: {transaction}")
    print("After restarting, choose Hyprland at the graphical login.")
    print("If Windows is still the default boot, select Arch Linux from the firmware's one-time boot menu.")
    print("Check your session later with ~/.local/bin/forge-doctor")
    if confirm("Restart now?", default=False):
        subprocess.run(["sudo", "systemctl", "reboot"], check=True)
    return 0
