import QtQuick
import QtQuick.Layouts

ForgeButton {
    id: root
    required property var preview
    text: ""
    implicitHeight: ForgeTheme.px(112)
    selected: ForgeTheme.accent.toString() === preview.color
    color: ForgeTheme.surface
    borderColor: selected ? ForgeTheme.cyan : activeFocus ? ForgeTheme.cyan : ForgeTheme.line
    cut: ForgeTheme.px(14)
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ForgeTheme.gap(12)
        spacing: ForgeTheme.gap(10)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.preview.base
            border.color: root.preview.color
            border.width: 1
            Rectangle { x: 6; y: 5; width: Math.max(0, parent.width - 12); height: 2; color: root.preview.color; opacity: 0.6 }
            Row {
                x: 8; y: 15
                spacing: 5
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        width: Math.max(4, Math.min(22, (root.width - 80) / 6)); height: 8 + index * 4
                        color: root.preview.color
                        opacity: 0.2 + index * 0.22
                    }
                }
            }
            Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 6; width: Math.min(70, parent.width / 3); height: 3; color: root.preview.color }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: root.preview.name.toUpperCase(); elide: Text.ElideRight; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); font.letterSpacing: 1 }
            Rectangle { width: ForgeTheme.px(7); height: width; color: root.preview.color }
        }
    }
    Accessible.name: "Apply " + preview.name + " theme"
}
