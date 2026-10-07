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
    color: selected ? ForgeTheme.accent : pointer.containsMouse ? ForgeTheme.raised : ForgeTheme.surface
    border.color: selected ? ForgeTheme.accent : ForgeTheme.line
    border.width: pointer.containsMouse || activeFocus ? 1 : 0
    Behavior on color { ColorAnimation { duration: 140 } }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        textFormat: Text.PlainText
        font.family: ForgeTheme.font
        font.pixelSize: 12
        color: root.selected ? ForgeTheme.accentText : ForgeTheme.text
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
