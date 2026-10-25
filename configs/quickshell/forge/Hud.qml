import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: panel
    property string label: ""
    property int amount: 0
    property bool active: false
    screen: Desktop.panelScreen
    visible: active
    anchors { bottom: true }
    margins.bottom: 96
    implicitWidth: ForgeTheme.px(340)
    implicitHeight: ForgeTheme.px(86)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    function show(label, amount) { panel.label = label; panel.amount = amount; active = true; hide.restart() }
    Connections {
        target: Desktop
        function onVolumeChanged() { panel.show(Desktop.muted ? "AUDIO / MUTED" : "AUDIO / OUTPUT", Desktop.volume) }
        function onMutedChanged() { panel.show(Desktop.muted ? "AUDIO / MUTED" : "AUDIO / OUTPUT", Desktop.volume) }
        function onMicMutedChanged() { panel.show(Desktop.micMuted ? "MICROPHONE / MUTED" : "MICROPHONE / LIVE", Desktop.micMuted ? 0 : 100) }
    }
    Connections { target: Laptop; function onBrightnessChanged() { panel.show("DISPLAY / LUMINANCE", Laptop.brightness) } }
    Timer { id: hide; interval: 1800; onTriggered: panel.active = false }
    IpcHandler {
        target: "forgeHud"
        function status(): string { return JSON.stringify({ active: panel.active, label: panel.label, amount: panel.amount }) }
    }
    ForgeFrame {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent; anchors.margins: ForgeTheme.gap(18)
            RowLayout {
                Text { text: panel.label; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11); color: ForgeTheme.cyan }
                Item { Layout.fillWidth: true }
                Text { text: panel.amount + "%"; font.family: ForgeTheme.font; color: ForgeTheme.accent }
            }
            Rectangle {
                Layout.fillWidth: true; height: 5; color: ForgeTheme.line
                Rectangle { width: parent.width * Math.max(0, Math.min(100, panel.amount)) / 100; height: parent.height; color: ForgeTheme.accent; Behavior on width { NumberAnimation { duration: ForgeTheme.duration } } }
            }
        }
    }
}
