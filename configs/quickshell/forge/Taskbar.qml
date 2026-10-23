import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: bar
    required property var modelData
    screen: modelData
    visible: Tasks.visibleOn(modelData)
    anchors { bottom: true; left: true; right: true }
    implicitHeight: 60
    exclusiveZone: visible ? 60 : 0
    color: "transparent"
    readonly property var runningWindows: Tasks.forScreen(modelData)
    ForgeFrame {
        anchors.fill: parent
        anchors.margins: 6
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 16
            spacing: 7
            ForgeButton { text: bar.width > 850 ? "EXEC /" : "↗"; selected: true; implicitHeight: 34; onClicked: Desktop.toggleLauncher(bar.screen) }
            Flickable {
                Layout.preferredWidth: Math.min(pinRow.implicitWidth, bar.width * 0.32)
                Layout.fillHeight: true
                contentWidth: pinRow.implicitWidth
                contentHeight: height
                clip: true
                flickableDirection: Flickable.HorizontalFlick
                Row {
                    id: pinRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5
                    Repeater {
                        model: Tasks.pins
                        TaskButton {
                            required property string modelData
                            entry: Tasks.entryFor(modelData)
                            enabled: entry !== null
                        }
                    }
                }
                ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
            }
            Rectangle { width: 1; height: 22; color: ForgeTheme.danger }
            Flickable {
                id: windowList
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: windowRow.implicitWidth
                contentHeight: height
                clip: true
                flickableDirection: Flickable.HorizontalFlick
                Row {
                    id: windowRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5
                    Repeater {
                        model: bar.runningWindows
                        TaskButton {
                            required property var modelData
                            window: modelData
                            entry: Tasks.entryFor(modelData.appId)
                            showTitle: Tasks.showTitles && bar.width > 800
                        }
                    }
                }
                Text {
                    visible: bar.runningWindows.length === 0
                    anchors.verticalCenter: parent.verticalCenter
                    text: "NO ACTIVE TASKS / YOUR NEXT MOVE"
                    color: ForgeTheme.muted
                    font.family: ForgeTheme.font
                    font.pixelSize: 9
                    elide: Text.ElideRight
                    width: parent.width
                }
                ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
            }
            Text { visible: bar.width > 1000; text: String(bar.runningWindows.length).padStart(2, "0") + " TASKS"; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: 10 }
            ForgeButton { text: bar.width > 850 ? "CLIPBOARD" : "CLIP"; implicitHeight: 34; onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.exec([Quickshell.env("HOME") + "/.local/bin/forge-clipboard"]) } }
            ForgeButton { text: "CONFIG"; implicitHeight: 34; onClicked: { Desktop.selectedScreen = bar.screen.name; Desktop.settingsPage = 2; if (!Desktop.settingsOpen) Desktop.toggleSettings() } }
        }
    }
}
