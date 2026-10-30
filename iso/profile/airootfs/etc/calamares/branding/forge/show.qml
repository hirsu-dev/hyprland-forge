import QtQuick

Rectangle {
    id: root
    color: "#19262e"
    property bool active: false
    property real phase: 0
    function onActivate() { active = true; }
    function onLeave() { active = false; }
    NumberAnimation on phase { from: 0; to: 1; duration: 4500; loops: Animation.Infinite; running: root.active }
    Column {
        anchors.centerIn: parent; spacing: 28
        Text { text: "BUILDING YOUR\nNEXT SESSION_"; color: "#e1edf0"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 38; font.bold: true }
        Rectangle { width: 360; height: 2; color: "#536d78"; Rectangle { x: root.phase * 280; width: 80; height: 2; color: "#94dce5" } }
        Text { text: "Forge is installing your system and desktop.\nKeep this computer connected to power."; color: "#a3b9c1"; font.pixelSize: 15; lineHeight: 1.4 }
    }
}
