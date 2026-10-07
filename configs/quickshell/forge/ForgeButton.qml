import QtQuick

Rectangle {
    id: root
    property string text: ""
    property bool selected: false
    signal clicked()
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.4
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: clicked()
    Keys.onReturnPressed: clicked()
    Keys.onSpacePressed: clicked()
    implicitWidth: label.implicitWidth + 24
    implicitHeight: 36
    radius: 12
    color: selected ? Palette.accent : pointer.containsMouse ? Palette.raised : Palette.surface
    border.color: selected ? Palette.accent : Palette.line
    border.width: pointer.containsMouse || activeFocus ? 1 : 0
    Behavior on color { ColorAnimation { duration: 140 } }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        textFormat: Text.PlainText
        font.family: Palette.font
        font.pixelSize: 12
        color: root.selected ? Palette.onAccent : Palette.text
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
