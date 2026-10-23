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
    readonly property color cyan: data.cyan
    readonly property color danger: data.danger
    readonly property bool motion: preferences.motion
    readonly property bool effects: preferences.effects
    readonly property int duration: motion ? 220 : 0
    readonly property string font: "JetBrainsMono Nerd Font"
    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/forge/theme.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter {
            id: data
            property string background: "#100d16"
            property string surface: "#1d141f"
            property string raised: "#2b1b2a"
            property string text: "#f4edf5"
            property string muted: "#bdaab8"
            property string accent: "#fcee0a"
            property string accentText: "#100d16"
            property string line: "#693642"
            property string cyan: "#74f7ef"
            property string danger: "#ff4d61"
        }
    }
    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/forge/interface.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter {
            id: preferences
            property bool motion: true
            property bool effects: true
        }
    }
}
