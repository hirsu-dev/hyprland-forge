import Quickshell
import QtQuick

PanelWindow {
    id: root
    property bool opened: false
    property real reveal: opened ? 1 : 0
    readonly property bool transitioning: travel.running
    visible: opened || reveal > 0.001
    focusable: opened
    color: "transparent"
    Behavior on reveal {
        NumberAnimation {
            id: travel
            duration: ForgeTheme.motion ? Math.round((root.opened ? 360 : 140) / ForgeTheme.speed) : 0
            easing.type: root.opened ? Easing.OutQuint : Easing.InCubic
        }
    }
    function motionState(name) { return { name: name, opened: opened, shown: visible, reveal: reveal, moving: transitioning, focusable: focusable } }
}
