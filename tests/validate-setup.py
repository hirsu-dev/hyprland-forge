import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archinstall.lib.args import ArchConfig, Arguments
from forge.bootstrap import allow_sudo
from forge.live import configuration, first_login


version = "0.14.0"
url = f"https://github.com/hirsu-dev/hyprland-forge/releases/download/v{version}/hyprland-forge-{version}.tar.gz"
seed = configuration(version, url, "a" * 64)
config = ArchConfig.from_config(seed, Arguments())
assert config.disk_config is None
assert config.auth_config is None
assert config.profile_config.profile.name == "Minimal"
assert config.network_config.type.value == "nm"
assert config.kernels == ["linux"]
assert config.services == ["NetworkManager"]
assert config.custom_commands == seed["custom_commands"]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    command = root / "stage.sh"
    command.write_text(seed["custom_commands"][0])
    subprocess.run(["bash", "-n", str(command)], check=True)
    hook = first_login(Path("/opt/hyprland-forge-" + version), root)
    subprocess.run(["sh", "-n", str(hook)], check=True)
    allow_sudo("forgefixture", root / "sudoers.d")
    assert (root / "sudoers.d/forge-forgefixture").read_text() == "forgefixture ALL=(ALL:ALL) ALL\n"
print("Arch installer configuration and first-login hook validated; no disk operation was run.")
