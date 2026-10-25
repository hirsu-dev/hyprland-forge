import Quickshell
import Quickshell.Io
import QtQuick

ShellRoot {
    Variants {
        model: Quickshell.screens
        Bar {}
    }
    Variants {
        model: Quickshell.screens
        Taskbar {}
    }
    ControlCenter { id: controls }
    Settings { id: settings }
    PowerMenu { id: power }
    Launcher { id: launcher }
    NotificationPopups {}
    Hud {}
    Overview { id: overview }
    Hub { id: hub }
    IpcHandler {
        target: "forgeMotion"
        function status(): string { return JSON.stringify([controls.motionState("controls"), settings.motionState("settings"), power.motionState("power"), launcher.motionState("launcher"), overview.motionState("overview"), hub.motionState("hub")]) }
    }
}
