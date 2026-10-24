import os
import shutil
import subprocess
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="forge-power-") as directory:
    path = Path(directory)
    shutil.copyfile(root / "configs/quickshell/forge/BatteryPolicy.qml", path / "BatteryPolicy.qml")
    (path / "shell.qml").write_text('''import Quickshell
import QtQuick
ShellRoot {
    property var events: []
    BatteryPolicy { id: battery; onWarning: (title, message, critical) => events.push({ title: title, critical: critical }) }
    Component.onCompleted: {
        battery.available = true
        battery.charge = 0.1
        if (events.length !== 0) throw new Error("Charging must stay quiet")
        battery.discharging = true
        if (events.length !== 1 || events[0].critical) throw new Error("Missing low warning")
        battery.charge = 0.14
        battery.charge = 0.09
        if (events.length !== 1) throw new Error("Low warning repeated")
        battery.charge = 0.05
        if (events.length !== 2 || !events[1].critical) throw new Error("Missing critical warning")
        battery.charge = 0.04
        if (events.length !== 2) throw new Error("Critical warning repeated")
        battery.discharging = false
        battery.discharging = true
        if (events.length !== 3) throw new Error("Charging did not rearm warning")
        battery.charge = 0.8
        battery.charge = 0.14
        if (events.length !== 4 || events[3].critical) throw new Error("Recovery did not rearm warning")
        battery.charge = NaN
        battery.charge = -1
        battery.charge = 2
        if (events.length !== 4) throw new Error("Invalid telemetry emitted warning")
        console.log("FORGE_POWER_POLICY_PASSED")
        Qt.quit()
    }
}
''')
    result = subprocess.run(["quickshell", "-p", str(path / "shell.qml")], env={**os.environ, "QT_QUICK_BACKEND": "software"}, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0 and "FORGE_POWER_POLICY_PASSED" in result.stdout + result.stderr, result.stdout + result.stderr
print("Native QML battery thresholds, charging rearm, duplicate suppression and invalid telemetry checks passed")
