import Quickshell
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.powerOpen
    implicitWidth: Math.min(520, screen ? screen.width - 40 : 520)
    implicitHeight: 350
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) { content.forceActiveFocus(); content.enter() }
    ForgeFrame {
        id: content
        anchors.fill: parent
        borderColor: ForgeTheme.danger
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 26
            spacing: 16
            Text { text: "FORGE / SESSION CONTROL"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: 10; font.letterSpacing: 1.5 }
            Text { text: "DISCONNECT_"; font.pixelSize: 30; font.bold: true; font.italic: true; color: ForgeTheme.accent; font.family: ForgeTheme.font }
            Text { text: "SELECT AN ACTION. UNSAVED WORK MAY BE LOST."; font.pixelSize: 10; color: ForgeTheme.muted; font.family: ForgeTheme.font }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 8; rowSpacing: 8
                Repeater {
                    model: [{ label: "01 / Suspend", action: "suspend" }, { label: "02 / Restart", action: "reboot" }, { label: "03 / Power off", action: "poweroff" }, { label: "04 / Log out", action: "logout" }]
                    ForgeButton {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 44
                        text: modelData.label
                        selected: Desktop.powerAction === modelData.action
                        onClicked: Desktop.requestPower(modelData.action)
                    }
                }
            }
            Text { Layout.fillWidth: true; text: Desktop.powerAction ? "AWAITING CONFIRMATION // " + Desktop.powerAction.toUpperCase() : "NO ACTION QUEUED"; color: Desktop.powerAction ? ForgeTheme.danger : ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 10 }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                ForgeButton { Layout.fillWidth: true; text: "CANCEL"; onClicked: Desktop.closePanels() }
                ForgeButton { Layout.fillWidth: true; text: "CONFIRM →"; danger: true; selected: true; enabled: Desktop.powerAction !== ""; onClicked: Desktop.confirmPower() }
            }
        }
    }
}
