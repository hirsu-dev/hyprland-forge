import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: bar
    required property var modelData
    screen: modelData
    anchors { top: true; left: true; right: true }
    implicitHeight: 54
    color: "transparent"
    exclusiveZone: 54
    Rectangle {
        anchors.fill: parent
        anchors.margins: 7
        radius: 15
        color: ForgeTheme.background
        border.color: ForgeTheme.line
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 7
            ForgeButton { text: "󰣇"; selected: true; onClicked: Desktop.toggleLauncher(bar.screen) }
            Row {
                spacing: 4
                Repeater {
                    model: 10
                    Rectangle {
                        required property int index
                        readonly property var monitor: Hyprland.monitorFor(bar.screen)
                        readonly property bool active: monitor && monitor.activeWorkspace && monitor.activeWorkspace.id === index + 1
                        width: active ? 30 : 13
                        height: 13
                        anchors.verticalCenter: parent.verticalCenter
                        radius: 7
                        color: active ? ForgeTheme.accent : ForgeTheme.raised
                        Behavior on width { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
                        Behavior on color { ColorAnimation { duration: 190 } }
                        MouseArea { anchors.fill: parent; onClicked: Desktop.workspace(parent.index + 1) }
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                Layout.maximumWidth: Math.max(80, bar.width * 0.22)
                text: Desktop.player ? "♫  " + Desktop.player.trackTitle : "FORGE"
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: ForgeTheme.muted
                font.family: ForgeTheme.font
                font.pixelSize: 11
            }
            Item { Layout.fillWidth: true }
            ForgeButton { text: Desktop.time; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: Desktop.muted ? "󰝟" : "󰕾 " + Desktop.volume; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: "󰁹 " + Desktop.battery; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: "󰒓"; onClicked: Desktop.toggleControls(bar.screen) }
        }
    }
}
