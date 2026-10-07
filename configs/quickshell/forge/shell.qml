import Quickshell
import QtQuick

ShellRoot {
    Variants {
        model: Quickshell.screens
        Bar {}
    }
    ControlCenter {}
    PowerMenu {}
    Launcher {}
}
