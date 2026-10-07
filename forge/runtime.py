import json
import os
import platform
import shlex
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .manifest import ForgeError
from .storage import Deployment, safe_target, write_json


def preflight():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ForgeError("Installation requires x86_64 Arch Linux")
    if os.geteuid() == 0:
        raise ForgeError("Run as your normal user; sudo is requested only for packages")
    release = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            release[key] = value.strip('"')
    if release.get("ID") != "arch":
        raise ForgeError("This release supports Arch Linux only")
    if Path("/run/archiso").exists():
        raise ForgeError("Install Arch with live.sh first, then reboot")
    for executable in ("sudo", "pacman"):
        if not shutil.which(executable):
            raise ForgeError(f"Required command is missing: {executable}")
    if Path("/var/lib/pacman/db.lck").exists():
        raise ForgeError("Pacman is busy. Retry after the current transaction finishes")


@contextmanager
def lock(state_root):
    import fcntl
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_root / "install.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ForgeError("Another Forge operation is running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def execute(plan, source_root, user_root, state_root, runner=subprocess.run):
    transaction_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    transaction_root = state_root / "transactions" / transaction_id
    try:
        state_relative = str((transaction_root / "transaction.json").relative_to(user_root)).replace("\\", "/")
    except ValueError as exc:
        raise ForgeError("Transaction storage must be inside home") from exc
    safe_target(user_root, state_relative)
    transaction_root.mkdir(parents=True, mode=0o700)
    record = {"id": transaction_id, "status": "started", "plan": plan, "commands_completed": []}
    record["services_enabled"] = []
    record_path = transaction_root / "transaction.json"
    write_json(record_path, record)
    deployment = Deployment(user_root, transaction_root)
    try:
        for command in plan["commands"]:
            runner(command, check=True)
            record["commands_completed"].append(command)
            write_json(record_path, record)
        deployment.apply(plan["files"], source_root)
        for service in plan.get("services", []):
            prior = runner(["systemctl", "is-enabled", service], capture_output=True, text=True)
            if prior.stdout.strip() == "enabled":
                continue
            if prior.stdout.strip() not in ("disabled", "enabled-runtime"):
                raise ForgeError(f"Cannot enable {service}: {prior.stdout.strip()}")
            record["services_enabled"].append({"name": service, "previous": prior.stdout.strip()})
            write_json(record_path, record)
            runner(["sudo", "systemctl", "enable", service], check=True)
        record["status"] = "complete"
        write_json(record_path, record)
        write_json(state_root / "latest.json", {"id": transaction_id})
        return transaction_id
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = type(exc).__name__
        record["service_rollback_failures"] = undo_services(record["services_enabled"], runner)
        try:
            record["rollback_conflicts"] = deployment.rollback()
        except Exception as rollback_error:
            record["rollback_error"] = str(rollback_error)
        write_json(record_path, record)
        raise


def undo_services(services, runner=subprocess.run):
    failures = []
    for service in reversed(services):
        try:
            runner(["sudo", "systemctl", "disable", service["name"]], check=True)
            if service["previous"] == "enabled-runtime":
                runner(["sudo", "systemctl", "enable", "--runtime", service["name"]], check=True)
        except (OSError, subprocess.CalledProcessError):
            failures.append(service["name"])
    return failures


def restore(transaction_id, user_root, state_root):
    import re
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", transaction_id):
        raise ForgeError("Invalid transaction identifier")
    transaction_root = state_root / "transactions" / transaction_id
    record_path = transaction_root / "transaction.json"
    try:
        record_relative = str(record_path.relative_to(user_root)).replace("\\", "/")
        journal_relative = str((transaction_root / "files.json").relative_to(user_root)).replace("\\", "/")
    except ValueError as exc:
        raise ForgeError("Transaction storage must be inside home") from exc
    safe_target(user_root, record_relative)
    safe_target(user_root, journal_relative)
    if not record_path.is_file():
        raise ForgeError("Transaction not found")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    conflicts = Deployment(user_root, transaction_root).rollback()
    record["status"] = "rollback-conflicts" if conflicts else "configs-restored"
    record["rollback_conflicts"] = conflicts
    write_json(record_path, record)
    return conflicts


def show_plan(plan):
    print(f"Hyprland Forge {plan['release']}")
    print("Stages: " + ", ".join(plan["stages"]))
    for command in plan["commands"]:
        print(shlex.join(command))
    for item in plan["files"]:
        print(f"{item['source']} -> ~/{item['target']}")
    for service in plan.get("services", []):
        print(f"Enable on next boot: {service}")
    if plan["pending"]:
        print("Not released: " + ", ".join(plan["pending"]))
    print("Package changes include a full Arch update. Config rollback leaves packages and services unchanged.")
