import QtQuick

ForgeFrame {
    id: root
    property string text: ""
    property bool selected: false
    property bool danger: false
    signal clicked()
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (enabled) clicked()
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onSpacePressed: if (enabled) clicked()
    implicitWidth: label.implicitWidth + 28
    implicitHeight: 36
    cut: 7
    ornament: false
    opacity: enabled ? 1 : 0.38
    color: selected ? (danger ? ForgeTheme.danger : ForgeTheme.accent) : pointer.containsMouse || activeFocus ? ForgeTheme.raised : ForgeTheme.surface
    borderColor: selected ? color : pointer.containsMouse || activeFocus ? ForgeTheme.cyan : ForgeTheme.line
    Behavior on color { ColorAnimation { duration: ForgeTheme.duration / 2 } }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        textFormat: Text.PlainText
        font.family: ForgeTheme.font
        font.pixelSize: 11
        font.bold: root.selected
        color: root.selected ? ForgeTheme.accentText : root.danger ? ForgeTheme.danger : ForgeTheme.text
    }
    Rectangle {
        x: 4; y: 9; width: 2; height: parent.height - 24
        visible: root.activeFocus
        color: ForgeTheme.cyan
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
