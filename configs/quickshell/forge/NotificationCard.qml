import QtQuick
import QtQuick.Layouts

ForgeFrame {
    id: card
    required property var entry
    readonly property var notification: Alerts.find(entry.id)
    implicitHeight: body.implicitHeight + 28
    cut: 12
    ornament: false
    color: ForgeTheme.surface
    borderColor: entry.critical ? ForgeTheme.danger : ForgeTheme.accent
    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: card.entry.app + " / " + card.entry.time; textFormat: Text.PlainText; elide: Text.ElideRight; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: 10 }
            ForgeButton { text: "×"; implicitWidth: 28; implicitHeight: 26; onClicked: Alerts.dismiss(card.entry.id) }
        }
        Text { Layout.fillWidth: true; text: card.notification ? card.notification.summary.slice(0, 256) : card.entry.title; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.pixelSize: 13 }
        Text { Layout.fillWidth: true; visible: text !== ""; text: card.notification ? card.notification.body.slice(0, 4096) : card.entry.body; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 5; elide: Text.ElideRight; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 11 }
        Flow {
            Layout.fillWidth: true
            spacing: 5
            Repeater {
                model: card.notification ? card.notification.actions : []
                ForgeButton { required property var modelData; text: modelData.text; onClicked: modelData.invoke() }
            }
        }
    }
}
