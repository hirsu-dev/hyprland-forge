import Quickshell
import QtQuick

PanelWindow {
    screen: Desktop.primaryScreen
    visible: Alerts.popups.length > 0 && !Desktop.hubOpen
    anchors { top: true; right: true }
    margins { top: 64; right: 12 }
    implicitWidth: Math.min(390, screen ? screen.width - 24 : 390)
    implicitHeight: Math.min(stack.implicitHeight, screen ? screen.height - 140 : 600)
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    Column {
        id: stack
        width: parent.width
        spacing: 8
        Repeater { model: Alerts.popups; NotificationCard { required property var modelData; width: stack.width; entry: modelData } }
    }
}
