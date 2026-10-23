import QtQuick
import QtQuick.Shapes

Item {
    id: root
    default property alias contentData: body.data
    property color color: ForgeTheme.background
    property color borderColor: ForgeTheme.line
    property real cut: 16
    property real progress: 1
    property bool ornament: true
    opacity: progress
    transform: Translate { x: (1 - root.progress) * 22 }
    function enter() {
        if (ForgeTheme.motion) entry.restart()
        else progress = 1
    }
    NumberAnimation {
        id: entry
        target: root
        property: "progress"
        from: 0
        to: 1
        duration: ForgeTheme.duration
        easing.type: Easing.OutCubic
    }
    Shape {
        anchors.fill: parent
        ShapePath {
            strokeWidth: 1
            strokeColor: root.borderColor
            fillColor: root.color
            startX: 0; startY: root.ornament ? root.cut : 0
            PathLine { x: root.ornament ? root.cut : 0; y: 0 }
            PathLine { x: root.width - root.cut * (root.ornament ? 2 : 1); y: 0 }
            PathLine { x: root.width - root.cut * (root.ornament ? 2 : 1); y: root.ornament ? 5 : 0 }
            PathLine { x: root.width - root.cut; y: root.ornament ? 5 : 0 }
            PathLine { x: root.width; y: root.cut + (root.ornament ? 5 : 0) }
            PathLine { x: root.width; y: root.height - (root.ornament ? root.cut : 0) }
            PathLine { x: root.width - (root.ornament ? root.cut : 0); y: root.height }
            PathLine { x: root.ornament ? root.cut * 3 : root.cut; y: root.height }
            PathLine { x: root.ornament ? root.cut * 3 - 8 : 0; y: root.height - (root.ornament ? 6 : root.cut) }
            PathLine { x: 0; y: root.height - (root.ornament ? 6 : root.cut) }
            PathLine { x: 0; y: root.ornament ? root.cut : 0 }
        }
    }
    Rectangle {
        x: root.cut + 8; y: 0
        width: Math.min(84, root.width / 4); height: 2
        color: ForgeTheme.danger
        visible: root.ornament
    }
    Rectangle {
        x: root.width - 3; y: root.cut + 22
        width: 3; height: 28
        color: ForgeTheme.accent
        visible: root.ornament
    }
    Rectangle {
        x: 1; y: root.height * root.progress
        width: root.width - 2; height: 2
        color: ForgeTheme.danger
        opacity: (1 - root.progress) * 0.8
        visible: ForgeTheme.effects && ForgeTheme.motion && root.progress < 1
    }
    Item { id: body; anchors.fill: parent }
}
