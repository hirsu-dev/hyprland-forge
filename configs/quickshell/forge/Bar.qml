import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import Quickshell.Services.SystemTray
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

PanelWindow {
    id: bar
    required property var modelData
    screen: modelData
    anchors { top: true; left: true; right: true }
    implicitHeight: 56
    color: "transparent"
    exclusiveZone: 56
    ForgeFrame {
        anchors.fill: parent
        anchors.margins: 6
        cut: 12
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 14
            spacing: 6
            ForgeButton {
                text: "FORGE /"
                selected: true
                implicitHeight: 30
                onClicked: Desktop.toggleLauncher(bar.screen)
            }
            Rectangle { Layout.leftMargin: 5; Layout.rightMargin: 5; width: 1; height: 20; color: ForgeTheme.line }
            Row {
                spacing: 3
                Repeater {
                    model: 10
                    ForgeButton {
                        required property int index
                        readonly property var monitor: Hyprland.monitorFor(bar.screen)
                        selected: monitor && monitor.activeWorkspace && monitor.activeWorkspace.id === index + 1
                        text: String(index + 1).padStart(2, "0")
                        implicitWidth: selected ? 36 : 26
                        implicitHeight: 28
                        onClicked: Desktop.workspace(index + 1)
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                Layout.maximumWidth: Math.max(0, bar.width - 980)
                visible: bar.width > 1020
                text: Desktop.player ? "♫  " + Desktop.player.trackTitle : "OVERDRIVE // LOCAL SESSION"
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: ForgeTheme.cyan
                font.family: ForgeTheme.font
                font.pixelSize: 10
            }
            Item { Layout.fillWidth: true }
            Row {
                spacing: 4
                Repeater {
                    model: SystemTray.items
                    Rectangle {
                        id: trayIcon
                        required property var modelData
                        width: 26; height: 28
                        color: trayMouse.containsMouse ? ForgeTheme.raised : "transparent"
                        Image { anchors.centerIn: parent; source: trayIcon.modelData.icon; sourceSize.width: 18; sourceSize.height: 18; width: 18; height: 18 }
                        ToolTip.visible: trayMouse.containsMouse
                        ToolTip.text: modelData.tooltipTitle || modelData.title || modelData.id
                        ToolTip.delay: 500
                        MouseArea {
                            id: trayMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                            onClicked: mouse => {
                                if ((mouse.button === Qt.RightButton || trayIcon.modelData.onlyMenu) && trayIcon.modelData.hasMenu) {
                                    const position = trayIcon.mapToItem(bar.contentItem, 0, trayIcon.height)
                                    trayIcon.modelData.display(bar, Math.round(position.x), Math.round(position.y))
                                } else if (mouse.button === Qt.MiddleButton) trayIcon.modelData.secondaryActivate()
                                else if (mouse.button === Qt.LeftButton) trayIcon.modelData.activate()
                            }
                            onWheel: wheel => trayIcon.modelData.scroll(wheel.angleDelta.y || wheel.angleDelta.x, !wheel.angleDelta.y)
                        }
                    }
                }
            }
            ForgeButton { text: Desktop.muted ? "MUTE" : "VOL " + Desktop.volume; implicitHeight: 28; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { visible: Desktop.recording; text: "REC ■"; danger: true; implicitHeight: 28; onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.openHub("capture") } }
            ForgeButton { text: Alerts.dnd ? "DND" : "N " + Alerts.history.length; implicitHeight: 28; onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.openHub("alerts") } }
            ForgeButton { text: Desktop.battery; implicitHeight: 28; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: Desktop.time; implicitHeight: 28; onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: "SYS"; implicitHeight: 28; onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.toggleSettings() } }
            ForgeButton { text: "⏻"; danger: true; implicitHeight: 28; onClicked: Desktop.togglePower(bar.screen) }
        }
    }
}
