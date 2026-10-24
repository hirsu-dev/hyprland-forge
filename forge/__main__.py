import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .manifest import ForgeError, load_manifest, make_plan
from .runtime import execute, lock, preflight, restore, show_plan
from .storage import safe_target
from .hardware import doctor, resolve_plan
from .login import resolve_plan as resolve_login


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hyprland-forge")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--setup", action="store_true")
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--rollback", metavar="TRANSACTION")
    modes.add_argument("--doctor", action="store_true")
    parser.add_argument("--stage", action="append")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--login", choices=("auto", "sddm", "keep"), default="auto")
    parser.add_argument("--profile", choices=("laptop", "virtual-machine"))
    args = parser.parse_args(argv)
    source_root = Path(__file__).resolve().parent.parent
    try:
        if args.setup:
            if args.json or args.stage:
                raise ForgeError("Guided setup installs the full desktop; use --plan for individual stages")
            from .setup import run
            return run(source_root, args.profile, args.login)
        if args.doctor:
            report = doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["runtime_ready"] else 1
        manifest = load_manifest(source_root)
        plan = make_plan(manifest, args.stage)
        if args.json and (args.apply or args.rollback):
            raise ForgeError("--json is available only for plans")
        if args.rollback and args.stage:
            raise ForgeError("--stage cannot be combined with --rollback")
        if args.apply:
            preflight()
        if not args.rollback:
            plan = resolve_plan(plan, apply=args.apply, profile=args.profile or "laptop")
            plan = resolve_login(plan, mode=args.login, apply=args.apply)
        if not args.apply and not args.rollback:
            print(json.dumps(plan, indent=2)) if args.json else show_plan(plan)
            return 0
        preflight()
        user_root = Path.home()
        state_root = user_root / ".local/state/hyprland-forge"
        safe_target(user_root, ".local/state/hyprland-forge/install.lock")
        for item in plan["files"]:
            safe_target(user_root, item["target"])
        if not sys.stdin.isatty():
            raise ForgeError("Apply and rollback require an interactive terminal")
        if args.rollback:
            print("Restore managed configuration files. Packages will remain installed.")
            if input("Type RESTORE: ") != "RESTORE":
                raise ForgeError("Cancelled")
            with lock(state_root):
                conflicts = restore(args.rollback, user_root, state_root)
            if conflicts:
                raise ForgeError("Kept files edited since installation: " + ", ".join(conflicts))
            print("Configuration restored")
            return 0
        show_plan(plan)
        if input("Type INSTALL: ") != "INSTALL":
            raise ForgeError("Cancelled")
        with lock(state_root):
            transaction_id = execute(plan, source_root, user_root, state_root)
        print(f"Complete: {transaction_id}")
        if plan.get("reboot_required"):
            print("Reboot when ready, then run bash install.sh --doctor")
        return 0
    except (ForgeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Forge: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Forge: cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
