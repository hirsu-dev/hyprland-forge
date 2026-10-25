import QtQuick

ForgeFrame {
    id: root
    property string text: ""
    property bool selected: false
    property bool danger: false
    signal clicked()
    property real clickPhase: 1
    function activate() { if (enabled) { if (ForgeTheme.motion && ForgeTheme.effects) clickSweep.restart(); clicked() } }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: activate()
    Keys.onReturnPressed: activate()
    Keys.onSpacePressed: activate()
    implicitWidth: label.implicitWidth + ForgeTheme.gap(28)
    implicitHeight: ForgeTheme.px(36) + ForgeTheme.gap(4)
    cut: ForgeTheme.px(9)
    ornament: false
    opacity: enabled ? 1 : 0.38
    color: selected ? (danger ? ForgeTheme.danger : ForgeTheme.accent) : pointer.containsMouse || activeFocus ? ForgeTheme.raised : ForgeTheme.surface
    borderColor: selected ? color : pointer.containsMouse || activeFocus ? ForgeTheme.cyan : ForgeTheme.line
    Behavior on color { ColorAnimation { duration: ForgeTheme.duration / 2 } }
    transform: Translate {
        y: ForgeTheme.motion ? pointer.pressed ? ForgeTheme.px(2) : pointer.containsMouse ? -ForgeTheme.px(1) : 0 : 0
        Behavior on y { NumberAnimation { duration: ForgeTheme.duration / 2; easing.type: Easing.OutCubic } }
    }
    NumberAnimation { id: clickSweep; target: root; property: "clickPhase"; from: 0; to: 1; duration: ForgeTheme.duration; easing.type: Easing.OutCubic }
    Rectangle {
        x: root.width * root.clickPhase; y: root.edge
        width: Math.max(1, root.width * 0.12 * (1 - root.clickPhase)); height: Math.max(0, root.height - root.edge * 2)
        color: root.selected ? ForgeTheme.accentText : ForgeTheme.cyan
        opacity: (1 - root.clickPhase) * ForgeTheme.intensity * 0.45
        visible: root.clickPhase < 1 && ForgeTheme.motion && ForgeTheme.effects
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        textFormat: Text.PlainText
        font.family: ForgeTheme.font
        font.pixelSize: ForgeTheme.fontSize(11)
        width: Math.max(0, root.width - Math.min(ForgeTheme.gap(16), root.width / 4))
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
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
        onClicked: root.activate()
    }
}
