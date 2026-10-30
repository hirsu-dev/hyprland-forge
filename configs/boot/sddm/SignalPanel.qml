import QtQuick

Canvas {
    id: panel
    property color fill: "#101c27"
    property color stroke: "#263b48"
    property bool motion: true
    property real cut: Math.min(16, height / 3)
    onFillChanged: requestPaint()
    onStrokeChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onCutChanged: requestPaint()
    Behavior on fill { ColorAnimation { duration: panel.motion ? 140 : 0 } }
    Behavior on stroke { ColorAnimation { duration: panel.motion ? 140 : 0 } }
    onPaint: {
        const c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height);
        c.beginPath(); c.moveTo(cut, 1); c.lineTo(width - 1, 1);
        c.lineTo(width - 1, height - cut); c.lineTo(width - cut, height - 1);
        c.lineTo(1, height - 1); c.lineTo(1, cut); c.closePath();
        c.fillStyle = fill; c.fill(); c.strokeStyle = stroke; c.lineWidth = 2; c.stroke();
    }
}
