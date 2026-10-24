import os
import shutil
import subprocess
import tempfile
import time
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
    }
}
''')
    with tempfile.TemporaryFile(mode="w+") as output:
        process = subprocess.Popen(["quickshell", "-p", str(path / "shell.qml")], env={**os.environ, "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORM": "xcb"}, stdout=output, stderr=subprocess.STDOUT, text=True)
        captured = ""
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                output.seek(0)
                captured = output.read()
                if "FORGE_POWER_POLICY_PASSED" in captured or process.poll() is not None:
                    break
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        assert "FORGE_POWER_POLICY_PASSED" in captured, captured
print("Native QML battery thresholds, charging rearm, duplicate suppression and invalid telemetry checks passed")
