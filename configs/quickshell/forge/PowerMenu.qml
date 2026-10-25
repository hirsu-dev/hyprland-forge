import Quickshell
import QtQuick
import QtQuick.Layouts

ForgePanel {
    id: panel
    screen: Desktop.panelScreen
    opened: Desktop.powerOpen
    implicitWidth: Math.min(ForgeTheme.px(520), screen ? screen.width - ForgeTheme.gap(40) : ForgeTheme.px(520))
    implicitHeight: ForgeTheme.px(350)
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    onOpenedChanged: if (opened) Qt.callLater(() => content.forceActiveFocus())
    ForgeFrame {
        id: content
        managedProgress: true
        progress: panel.reveal
        anchors.fill: parent
        borderColor: ForgeTheme.danger
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: ForgeTheme.gap(26)
            spacing: ForgeTheme.gap(16)
            Text { text: "FORGE / SESSION CONTROL"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); font.letterSpacing: 1.5 }
            Text { text: "DISCONNECT_"; font.pixelSize: ForgeTheme.fontSize(30); font.bold: true; font.italic: true; color: ForgeTheme.accent; font.family: ForgeTheme.font }
            Text { text: "SELECT AN ACTION. UNSAVED WORK MAY BE LOST."; font.pixelSize: ForgeTheme.fontSize(10); color: ForgeTheme.muted; font.family: ForgeTheme.font }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: ForgeTheme.gap(8); rowSpacing: ForgeTheme.gap(8)
                Repeater {
                    model: [{ label: "01 / Suspend", action: "suspend" }, { label: "02 / Restart", action: "reboot" }, { label: "03 / Power off", action: "poweroff" }, { label: "04 / Log out", action: "logout" }]
                    ForgeButton {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: ForgeTheme.px(44)
                        text: modelData.label
                        selected: Desktop.powerAction === modelData.action
                        onClicked: Desktop.requestPower(modelData.action)
                    }
                }
            }
            Text { Layout.fillWidth: true; text: Desktop.powerAction ? "AWAITING CONFIRMATION // " + Desktop.powerAction.toUpperCase() : "NO ACTION QUEUED"; color: Desktop.powerAction ? ForgeTheme.danger : ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                ForgeButton { Layout.fillWidth: true; text: "CANCEL"; onClicked: Desktop.closePanels() }
                ForgeButton { Layout.fillWidth: true; text: "CONFIRM →"; danger: true; selected: true; enabled: Desktop.powerAction !== ""; onClicked: Desktop.confirmPower() }
            }
        }
    }
}
