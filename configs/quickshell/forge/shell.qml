import Quickshell
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
    ControlCenter {}
    Settings {}
    PowerMenu {}
    Launcher {}
    NotificationPopups {}
    Hud {}
    Overview {}
    Hub {}
}
