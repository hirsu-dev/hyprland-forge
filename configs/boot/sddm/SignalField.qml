import QtQuick

Item {
    id: field
    width: 1920
    height: 1080
    property bool motion: true
    property real clock: 0
    readonly property color cyan: "#74f7df"
    readonly property color red: "#ff4264"
    onMotionChanged: tracers.requestPaint()
    Timer {
        interval: 33
        repeat: true
        running: field.motion && field.visible
        onTriggered: { field.clock = (field.clock + 33) % 196608; tracers.requestPaint(); }
    }
    Canvas {
        anchors.fill: parent
        onPaint: {
            const c = getContext("2d"); c.reset();
            c.lineWidth = 1; c.strokeStyle = "#12222e";
            for (let x = 64; x < 1920; x += 96) { c.beginPath(); c.moveTo(x, 128); c.lineTo(x, 944); c.stroke(); }
            for (let y = 176; y < 944; y += 96) { c.beginPath(); c.moveTo(64, y); c.lineTo(1856, y); c.stroke(); }
            c.strokeStyle = "#263b48";
            for (let n = 0; n < 4; n++) {
                c.beginPath();
                for (let p = 0; p <= 16; p++) {
                    const a = p * Math.PI / 8 - Math.PI / 2;
                    const x = 1392 + Math.cos(a) * (242 + n * 36), y = 548 + Math.sin(a) * (278 + n * 33);
                    if (p === 0) c.moveTo(x, y); else c.lineTo(x, y);
                }
                c.stroke();
            }
            const mark = [[80,0],[360,0],[310,60],[130,60],[104,120],[280,120],[230,180],[78,180],[0,360],[-76,360]];
            for (const shadow of [true, false]) {
                c.beginPath();
                for (let i = 0; i < mark.length; i++) {
                    const x = 1274 + mark[i][0] * 300 / 360 + (shadow ? 6 : 0);
                    const y = 372 + mark[i][1] * 300 / 360 + (shadow ? 6 : 0);
                    if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
                }
                c.closePath(); c.fillStyle = shadow ? "#14363d" : field.cyan; c.fill();
            }
            c.strokeStyle = field.cyan; c.lineWidth = 2;
            c.beginPath(); c.moveTo(1220,754); c.lineTo(1290,824); c.lineTo(1510,824); c.stroke();
            c.strokeStyle = "#839ba8";
            for (const corner of [[40,38,1,1],[1880,38,-1,1],[40,1042,1,-1],[1880,1042,-1,-1]]) {
                c.beginPath(); c.moveTo(corner[0]+corner[2]*36,corner[1]); c.lineTo(corner[0],corner[1]); c.lineTo(corner[0],corner[1]+corner[3]*24); c.stroke();
            }
        }
    }
    Canvas {
        id: tracers
        x: 950; y: 128; width: 860; height: 820
        onPaint: {
            const c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height); c.translate(-950, -128);
            const time = field.motion ? field.clock : 0;
            for (let ring = 0; ring < 4; ring++) {
                const position = ((time * (2 + ring) + ring * 1300) % 16384) / 1024;
                for (let tail = 0; tail < 3; tail++) {
                    const step = (position + 16 - tail * .22) % 16;
                    const edge = Math.floor(step), part = step - edge;
                    const a = edge * Math.PI / 8 - Math.PI / 2, b = a + Math.PI / 8;
                    const radiusX = 242 + ring * 36, radiusY = 278 + ring * 33;
                    const x = 1392 + (Math.cos(a) + (Math.cos(b) - Math.cos(a)) * part) * radiusX;
                    const y = 548 + (Math.sin(a) + (Math.sin(b) - Math.sin(a)) * part) * radiusY;
                    const end = Math.min(1, part + .19);
                    const ex = 1392 + (Math.cos(a) + (Math.cos(b) - Math.cos(a)) * end) * radiusX;
                    const ey = 548 + (Math.sin(a) + (Math.sin(b) - Math.sin(a)) * end) * radiusY;
                    c.strokeStyle = ring % 2 === 0 ? field.cyan : field.red;
                    c.globalAlpha = .12 - tail * .03; c.lineWidth = 8;
                    c.beginPath(); c.moveTo(x,y); c.lineTo(ex,ey); c.stroke();
                    c.globalAlpha = 1 - tail * .27; c.lineWidth = 2;
                    c.beginPath(); c.moveTo(x,y); c.lineTo(ex,ey); c.stroke();
                }
            }
            c.globalAlpha = 1;
            for (let n = 0; n < 28; n++) {
                const step = (time / 55 + n * 37) % 96;
                const h = 8 + (step < 48 ? step : 96 - step) / 2;
                c.fillStyle = n % 7 === 0 ? field.red : "#346268";
                c.fillRect(1190+n*16,920-h,5,h);
            }
        }
    }
    Text { x: 1250; y: 862; text: "FORGE / GHOSTWIRE"; color: "#839ba8"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 16; font.letterSpacing: 3 }
}
