pragma Singleton
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    id: root
    property bool available: false
    property int brightness: 0
    property string device: ""
    property int requested: -1
    property int applying: -1
    function refresh() { if (!reader.running && !writer.running) reader.running = true }
    function setBrightness(value) {
        if (!available) return
        requested = Math.max(2, Math.min(100, Math.round(value)))
        debounce.restart()
    }
    function apply() {
        if (writer.running || requested < 0 || !available) return
        applying = requested
        writer.command = ["brightnessctl", "-d", device, "-n2", "set", applying + "%"]
        writer.running = true
    }
    Connections {
        target: Desktop
        function onControlsOpenChanged() { if (Desktop.controlsOpen) root.refresh() }
    }
    Timer { interval: 5000; running: Desktop.controlsOpen; repeat: true; onTriggered: root.refresh() }
    Timer { id: debounce; interval: 80; onTriggered: root.apply() }
    Process {
        id: reader
        command: ["brightnessctl", "-m", "-c", "backlight", "info"]
        stdout: StdioCollector {
            onStreamFinished: {
                const fields = text.trim().split("\n")[0].split(",")
                const percent = fields.length > 3 ? Number(fields[3].replace("%", "")) : NaN
                root.available = fields.length >= 5 && fields[1] === "backlight" && Number.isFinite(percent)
                if (root.available) { root.device = fields[0]; root.brightness = Math.max(0, Math.min(100, Math.round(percent))) }
            }
        }
        onExited: (exitCode, exitStatus) => { if (exitCode !== 0) root.available = false }
    }
    Process {
        id: writer
        stdout: StdioCollector {}
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) { root.requested = -1; root.available = false; return }
            root.brightness = root.applying
            if (root.requested !== root.applying) debounce.restart()
            else { root.requested = -1; root.refresh() }
        }
    }
}
