pragma Singleton
import Quickshell
import Quickshell.Io
import QtQuick

Singleton {
    readonly property color background: data.background
    readonly property color surface: data.surface
    readonly property color raised: data.raised
    readonly property color text: data.text
    readonly property color muted: data.muted
    readonly property color accent: data.accent
    readonly property color accentText: data.accentText
    readonly property color line: data.line
    readonly property string font: "JetBrainsMono Nerd Font"
    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/forge/theme.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter {
            id: data
            property string background: "#11171f"
            property string surface: "#1b242d"
            property string raised: "#27323b"
            property string text: "#e1e7ea"
            property string muted: "#9daab3"
            property string accent: "#b5c9a8"
            property string accentText: "#20301f"
            property string line: "#39454d"
        }
    }
}
