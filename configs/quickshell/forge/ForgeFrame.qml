import QtQuick
import QtQuick.Shapes

Item {
    id: root
    default property alias contentData: body.data
    property color color: ForgeTheme.background
    property color borderColor: ForgeTheme.line
    property real cut: ForgeTheme.px(20)
    property real progress: 1
    property real signalPhase: 0
    property bool ornament: true
    property bool managedProgress: false
    readonly property real edge: Math.max(0, Math.min(cut * ForgeTheme.jaggedness, width / 7, height / 3))
    readonly property real notch: ornament ? Math.min(ForgeTheme.px(7) * ForgeTheme.jaggedness, edge / 2) : 0
    readonly property bool onScreen: visible && !!Window.window && Window.window.visible
    readonly property bool signalRunning: onScreen && ornament && ForgeTheme.ambient
    opacity: progress
    transform: [Translate { x: (1 - root.progress) * ForgeTheme.px(32); y: (1 - root.progress) * ForgeTheme.px(5) }, Scale { origin.x: root.width / 2; origin.y: root.height / 2; xScale: 0.98 + root.progress * 0.02; yScale: xScale }]
    function enter() {
        if (managedProgress) return
        if (ForgeTheme.motion) entry.restart()
        else progress = 1
    }
    Connections {
        target: ForgeTheme
        function onMotionChanged() { if (!ForgeTheme.motion && !root.managedProgress) { entry.stop(); root.progress = 1 } }
    }
    NumberAnimation {
        id: entry
        target: root; property: "progress"; from: 0; to: 1
        duration: ForgeTheme.duration
        easing.type: Easing.OutCubic
    }
    NumberAnimation on signalPhase {
        running: root.signalRunning
        from: 0; to: 1
        duration: Math.round(14000 / ForgeTheme.speed)
        loops: Animation.Infinite
    }
    Shape {
        anchors.fill: parent
        ShapePath {
            strokeWidth: 1
            strokeColor: root.borderColor
            fillColor: Qt.rgba(root.color.r, root.color.g, root.color.b, root.color.a * (root.ornament && ForgeTheme.effects ? ForgeTheme.panelOpacity : 1))
            startX: 0; startY: root.edge
            PathLine { x: root.edge; y: 0 }
            PathLine { x: root.width - root.edge * 3; y: 0 }
            PathLine { x: root.width - root.edge * 3 + root.notch; y: root.notch }
            PathLine { x: root.width - root.edge; y: root.notch }
            PathLine { x: root.width; y: root.edge + root.notch }
            PathLine { x: root.width; y: root.height * 0.58 - root.notch }
            PathLine { x: root.width - root.notch; y: root.height * 0.58 }
            PathLine { x: root.width; y: root.height * 0.58 + root.notch }
            PathLine { x: root.width; y: root.height - root.edge }
            PathLine { x: root.width - root.edge; y: root.height }
            PathLine { x: root.edge * 3; y: root.height }
            PathLine { x: root.edge * 3 - root.notch; y: root.height - root.notch }
            PathLine { x: root.edge; y: root.height - root.notch }
            PathLine { x: 0; y: root.height - root.edge }
            PathLine { x: 0; y: root.height * 0.35 + root.notch }
            PathLine { x: root.notch; y: root.height * 0.35 }
            PathLine { x: 0; y: root.height * 0.35 - root.notch }
            PathLine { x: 0; y: root.edge }
        }
    }
    Rectangle {
        x: root.edge + ForgeTheme.px(8); y: 0
        width: Math.min(ForgeTheme.px(84), root.width / 4); height: 2
        color: ForgeTheme.danger
        visible: root.ornament
    }
    Rectangle {
        x: root.width - ForgeTheme.px(4); y: root.edge + ForgeTheme.px(22)
        width: ForgeTheme.px(3); height: Math.min(ForgeTheme.px(28), root.height / 5)
        color: ForgeTheme.accent
        visible: root.ornament
    }
    Repeater {
        model: root.ornament && ForgeTheme.effects ? 3 : 0
        Rectangle {
            required property int index
            x: root.edge + ForgeTheme.px(index * 8); y: root.height - ForgeTheme.px(3)
            width: ForgeTheme.px(4); height: ForgeTheme.px(2)
            rotation: -35
            color: index === 1 ? ForgeTheme.cyan : ForgeTheme.danger
        }
    }
    Rectangle {
        x: root.edge + (root.width - root.edge * 2 - width) * root.signalPhase
        y: 0; width: Math.min(ForgeTheme.px(56), root.width / 6); height: 2
        color: ForgeTheme.cyan
        opacity: 0.35 + ForgeTheme.intensity * 0.5
        visible: root.signalRunning
    }
    Rectangle {
        x: root.width - width - root.edge - (root.width - root.edge * 2 - width) * root.signalPhase
        y: root.height - 1; width: Math.min(ForgeTheme.px(34), root.width / 8); height: 1
        color: ForgeTheme.danger
        opacity: ForgeTheme.intensity * 0.7
        visible: root.signalRunning
    }
    Rectangle {
        x: root.edge; y: (root.height - 2) * root.signalPhase
        width: Math.max(0, root.width - root.edge * 2); height: 1
        color: ForgeTheme.cyan
        opacity: 0.035 * ForgeTheme.intensity
        visible: root.signalRunning && ForgeTheme.scanlines
    }
    Rectangle {
        x: root.edge; y: Math.max(0, root.height - 2) * root.progress
        width: Math.max(0, root.width - root.edge * 2); height: ForgeTheme.px(2)
        color: ForgeTheme.danger
        opacity: (1 - root.progress) * ForgeTheme.intensity
        visible: ForgeTheme.scanlines && root.progress < 1
    }
    Item { id: body; anchors.fill: parent }
}
