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
    readonly property real uiScale: bounded(preferences.scale, 0.75, 1.75, 1)
    readonly property real textScale: bounded(preferences.textScale, 0.85, 1.25, 1)
    readonly property real spacing: bounded(preferences.spacing, 0.75, 1.6, 1.2)
    readonly property real jaggedness: bounded(preferences.jaggedness, 0, 2, 1.4)
    readonly property real speed: bounded(preferences.speed, 0.5, 2, 1)
    readonly property real intensity: bounded(preferences.intensity, 0, 1, 0.65)
    readonly property real panelOpacity: bounded(preferences.panelOpacity, 0.7, 1, 0.9)
    readonly property bool ambient: motion && effects && preferences.ambient && intensity > 0
    readonly property bool scanlines: motion && effects && preferences.scanlines && intensity > 0
    readonly property int duration: motion ? Math.round(280 / speed) : 0
    readonly property var interfaceValues: ({ motion: motion, effects: effects, scale: uiScale, textScale: textScale, spacing: spacing, jaggedness: jaggedness, speed: speed, intensity: intensity, ambient: preferences.ambient, scanlines: preferences.scanlines, panelOpacity: panelOpacity })
    readonly property string font: "JetBrainsMono Nerd Font"
    function bounded(value, low, high, fallback) { return Number.isFinite(value) ? Math.max(low, Math.min(high, value)) : fallback }
    function px(value) { return Math.round(value * uiScale) }
    function gap(value) { return Math.round(value * uiScale * spacing) }
    function fontSize(value) { return Math.round(value * uiScale * textScale) }
    function panelHeight(screen, preferred) { return Math.max(px(100), Math.min(px(preferred), (screen ? screen.height : px(preferred) + px(116) + gap(24)) - px(116) - gap(24))) }
    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/forge/theme.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter {
            id: data
            property string background: "#10191f"
            property string surface: "#19262e"
            property string raised: "#253740"
            property string text: "#e1edf0"
            property string muted: "#a3b9c1"
            property string accent: "#b4d9de"
            property string accentText: "#10191f"
            property string line: "#536d78"
            property string cyan: "#94dce5"
            property string danger: "#d98992"
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
            property real scale: 1
            property real textScale: 1
            property real spacing: 1.2
            property real jaggedness: 1.4
            property real speed: 1
            property real intensity: 0.65
            property bool ambient: true
            property bool scanlines: true
            property real panelOpacity: 0.9
        }
    }
}
