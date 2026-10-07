import Quickshell
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.powerOpen
    implicitWidth: Math.min(440, screen ? screen.width - 40 : 440)
    implicitHeight: 290
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) content.forceActiveFocus()
    Rectangle {
        id: content
        anchors.fill: parent
        radius: 24
        color: ForgeTheme.background
        border.color: ForgeTheme.line
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16
            Text { text: "End the day, your way"; font.pixelSize: 20; color: ForgeTheme.text; font.family: ForgeTheme.font }
            Text { text: "Unsaved work may be lost."; font.pixelSize: 12; color: ForgeTheme.muted }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 8; rowSpacing: 8
                Repeater {
                    model: [{ label: "󰒲 Suspend", action: "suspend" }, { label: "󰜉 Restart", action: "reboot" }, { label: "󰐥 Power off", action: "poweroff" }, { label: "󰍃 Log out", action: "logout" }]
                    ForgeButton {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.label
                        selected: Desktop.powerAction === modelData.action
                        onClicked: Desktop.requestPower(modelData.action)
                    }
                }
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                ForgeButton { Layout.fillWidth: true; text: "Cancel"; onClicked: Desktop.closePanels() }
                ForgeButton { Layout.fillWidth: true; text: "Confirm"; selected: true; enabled: Desktop.powerAction !== ""; onClicked: Desktop.confirmPower() }
            }
        }
    }
}
