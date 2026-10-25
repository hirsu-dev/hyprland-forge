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
    visible: !Tasks.fullscreenOn(modelData)
    anchors { top: true; left: true; right: true }
    implicitHeight: ForgeTheme.px(56)
    color: "transparent"
    exclusiveZone: implicitHeight
    ForgeFrame {
        anchors.fill: parent
        anchors.margins: ForgeTheme.gap(6)
        cut: ForgeTheme.px(12)
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: ForgeTheme.gap(12)
            anchors.rightMargin: ForgeTheme.gap(14)
            spacing: ForgeTheme.gap(6)
            ForgeButton {
                text: "FORGE /"
                selected: true
                implicitHeight: ForgeTheme.px(30)
                onClicked: Desktop.toggleLauncher(bar.screen)
            }
            Rectangle { Layout.leftMargin: ForgeTheme.gap(5); Layout.rightMargin: ForgeTheme.gap(5); width: 1; height: 20; color: ForgeTheme.line }
            Row {
                spacing: ForgeTheme.gap(3)
                Repeater {
                    model: bar.width < ForgeTheme.px(1100) ? 4 : bar.width < ForgeTheme.px(1400) ? 6 : 10
                    ForgeButton {
                        required property int index
                        readonly property var monitor: Hyprland.monitorFor(bar.screen)
                        selected: monitor && monitor.activeWorkspace && monitor.activeWorkspace.id === index + 1
                        text: String(index + 1).padStart(2, "0")
                        implicitWidth: ForgeTheme.px(selected ? 36 : 26)
                        implicitHeight: ForgeTheme.px(28)
                        onClicked: Desktop.workspace(index + 1)
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                Layout.maximumWidth: Math.max(0, bar.width - 980)
                visible: bar.width > ForgeTheme.px(1220)
                text: Desktop.player ? "♫  " + Desktop.player.trackTitle : "OVERDRIVE // LOCAL SESSION"
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: ForgeTheme.cyan
                font.family: ForgeTheme.font
                font.pixelSize: ForgeTheme.fontSize(10)
            }
            Item { Layout.fillWidth: true }
            Row {
                spacing: ForgeTheme.gap(4)
                Repeater {
                    model: SystemTray.items
                    Rectangle {
                        id: trayIcon
                        required property var modelData
                        width: ForgeTheme.px(26); height: 28
                        color: trayMouse.containsMouse ? ForgeTheme.raised : "transparent"
                        Image { anchors.centerIn: parent; source: trayIcon.modelData.icon; sourceSize.width: ForgeTheme.px(18); sourceSize.height: ForgeTheme.px(18); width: 18; height: 18 }
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
            ForgeButton { text: Desktop.muted ? "MUTE" : "VOL " + Desktop.volume; implicitHeight: ForgeTheme.px(28); onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { visible: Desktop.recording; text: "REC ■"; danger: true; implicitHeight: ForgeTheme.px(28); onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.openHub("capture") } }
            ForgeButton { text: Alerts.dnd ? "DND" : "N " + Alerts.history.length; implicitHeight: ForgeTheme.px(28); onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.openHub("alerts") } }
            ForgeButton { visible: bar.width > ForgeTheme.px(1000); text: Desktop.battery; implicitHeight: ForgeTheme.px(28); onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { visible: bar.width > ForgeTheme.px(900); text: Desktop.time; implicitHeight: ForgeTheme.px(28); onClicked: Desktop.toggleControls(bar.screen) }
            ForgeButton { text: "SYS"; implicitHeight: ForgeTheme.px(28); onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.toggleSettings() } }
            ForgeButton { text: "⏻"; danger: true; implicitHeight: ForgeTheme.px(28); onClicked: Desktop.togglePower(bar.screen) }
        }
    }
}
