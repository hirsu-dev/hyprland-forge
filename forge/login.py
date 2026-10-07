import platform
import subprocess
from pathlib import Path

from .manifest import ForgeError


def inventory(runner=subprocess.run):
    result = runner(["systemctl", "show", "display-manager.service", "--property=LoadState,FragmentPath"], capture_output=True, text=True, timeout=10)
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    state = values.get("LoadState")
    if state not in ("loaded", "not-found", "masked") or (result.returncode != 0 and not (result.returncode == 4 and state == "not-found")):
        raise ForgeError("Cannot determine the existing graphical login configuration")
    target = runner(["systemctl", "get-default"], capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if not target.endswith(".target"):
        raise ForgeError("Cannot determine the default boot target")
    return {"state": state, "manager": values.get("FragmentPath", ""), "target": target}


def configure(plan, mode, data):
    plan["login"] = {"mode": mode, "before": data, "action": "preserve"}
    if mode == "keep":
        return plan
    if data["state"] != "not-found":
        if mode == "sddm" and (data["state"] == "masked" or Path(data["manager"]).name != "sddm.service"):
            raise ForgeError("An existing or masked display manager must be changed manually; use --login keep to preserve it")
        return plan
    if data["target"] not in ("graphical.target", "multi-user.target"):
        if mode == "sddm":
            raise ForgeError("Refusing to replace a custom default boot target")
        return plan
    plan["login"]["action"] = "enable-sddm"
    plan["packages"] = list(dict.fromkeys([*plan["packages"], "sddm"]))
    plan["commands"] = [["sudo", "pacman", "-Syu", "--needed", "--", *plan["packages"]]]
    plan["services"] = list(dict.fromkeys([*plan.get("services", []), "sddm.service"]))
    plan["reboot_required"] = True
    if data["target"] == "multi-user.target":
        plan["default_target"] = {"previous": data["target"], "next": "graphical.target"}
    return plan


def resolve_plan(plan, mode="auto", apply=False):
    if "compositor" not in plan["stages"] or mode == "keep":
        return plan
    native = platform.system() == "Linux" and Path("/run/systemd/system").is_dir()
    if apply and not native:
        raise ForgeError("Graphical login setup requires a running systemd system; use --login keep to skip it")
    data = inventory() if native else {"state": "not-found", "manager": "", "target": "multi-user.target"}
    result = configure(plan, mode, data)
    result["login"]["preview_only"] = not native
    return result


def verify_unchanged(plan, runner=subprocess.run):
    login = plan.get("login", {})
    if login.get("action") != "enable-sddm":
        return
    if login.get("preview_only") or inventory(runner) != login["before"]:
        raise ForgeError("Graphical login configuration changed; regenerate the installation plan")
    result = runner(["systemctl", "is-enabled", "sddm.service"], capture_output=True, text=True, timeout=10)
    if result.stdout.strip() not in ("enabled", "disabled", "enabled-runtime", "not-found"):
        raise ForgeError("SDDM is masked or has unsupported service configuration")
