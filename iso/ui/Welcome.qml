import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    minimumWidth: 800
    minimumHeight: 600
    visibility: previewMode ? Window.Windowed : Window.FullScreen
    title: "Forge Setup"
    color: "#10191f"
    property real progress: 0
    property real phase: 0
    property bool motion: true
    property var selectedApps: []
    readonly property real unit: Math.max(0.75, Math.min(width / 1280, height / 800))
    readonly property color accent: "#94dce5"
    readonly property color ink: "#e1edf0"
    readonly property color dim: "#a3b9c1"
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: Math.round(14 * unit)
    palette.window: "#19262e"
    palette.windowText: ink
    palette.text: ink
    palette.base: "#10191f"
    palette.button: "#253740"
    palette.buttonText: ink
    palette.highlight: accent
    palette.highlightedText: "#10191f"
    component ForgeText: Text { font.family: root.font.family }
    function toggleApp(id, checked) {
        let next = selectedApps.filter(value => value !== id);
        if (checked) {
            if (id === "discord") next = next.filter(value => value !== "equicord");
            if (id === "equicord") next = next.filter(value => value !== "discord");
            next.push(id);
        }
        selectedApps = next;
    }
    Component.onCompleted: { if (previewApps) Qt.callLater(() => appPicker.open()); }

    NumberAnimation on progress { from: 0; to: 1; duration: 2600; easing.type: Easing.OutCubic; running: root.motion }
    NumberAnimation on phase { from: 0; to: 1; duration: 9000; loops: Animation.Infinite; running: root.motion && root.visible }

    Canvas {
        id: field
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d"); ctx.reset();
            const u = root.unit;
            ctx.strokeStyle = "#1c2b34"; ctx.lineWidth = 1;
            for (let x = 32 * u; x < width; x += 72 * u) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,height); ctx.stroke(); }
            for (let y = 32 * u; y < height; y += 72 * u) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(width,y); ctx.stroke(); }
            ctx.save(); ctx.translate(width * 0.78, height * 0.5);
            for (let n = 0; n < 7; n++) {
                const radius = (150 + n * 28) * u;
                ctx.strokeStyle = n === 2 ? "#789aa7" : "#344b57";
                ctx.lineWidth = n === 2 ? 2 : 1;
                ctx.beginPath();
                for (let k = 0; k <= 8; k++) { const a = k * Math.PI / 4 + Math.PI / 8; const x = Math.cos(a) * radius; const y = Math.sin(a) * radius; if (!k) ctx.moveTo(x,y); else ctx.lineTo(x,y); }
                ctx.stroke();
            }
            ctx.fillStyle = "#b4d9de";
            ctx.beginPath(); ctx.moveTo(-70*u,-110*u);ctx.lineTo(110*u,-110*u);ctx.lineTo(72*u,-62*u);ctx.lineTo(-35*u,-62*u);ctx.lineTo(-55*u,-15*u);ctx.lineTo(53*u,-15*u);ctx.lineTo(16*u,32*u);ctx.lineTo(-75*u,32*u);ctx.lineTo(-116*u,130*u);ctx.lineTo(-173*u,130*u);ctx.closePath();ctx.fill();
            ctx.restore();
        }
    }
    Rectangle {
        width: parent.width; height: 2 * root.unit; color: root.accent; opacity: 0.12
        y: root.phase * root.height
        visible: root.motion
    }
    RowLayout {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 38 * root.unit }
        ForgeText { text: "F / FORGE"; color: root.ink; font.bold: true; font.letterSpacing: 3 * root.unit; font.pixelSize: 18 * root.unit }
        Item { Layout.fillWidth: true }
        ForgeText { text: "INSTALLATION ENVIRONMENT   /   EXPERIMENTAL"; color: root.dim; font.pixelSize: 11 * root.unit }
    }
    ColumnLayout {
        anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 72 * root.unit }
        width: Math.min(parent.width * 0.52, 660 * root.unit)
        spacing: 22 * root.unit
        opacity: Math.min(1, root.progress * 2)
        transform: Translate { x: (1 - root.progress) * -40 * root.unit }
        ForgeText { text: "YOUR NEXT SESSION"; color: root.accent; font.pixelSize: 13 * root.unit; font.letterSpacing: 5 * root.unit }
        ForgeText { text: "WELCOME\nTO FORGE_"; color: root.ink; font.bold: true; font.pixelSize: 62 * root.unit; lineHeight: 0.95 }
        ForgeText {
            Layout.fillWidth: true; text: "An Arch desktop, built around you.\nChoose your language, disks and account in the guided setup."; wrapMode: Text.WordWrap
            color: root.dim; font.pixelSize: 16 * root.unit; lineHeight: 1.4
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: "#536d78" }
        CheckBox { id: gaming; text: "Steam and gaming tools"; checked: true; palette.windowText: root.ink; palette.text: root.ink; palette.highlight: root.accent; font.pixelSize: 15 * root.unit }
        CheckBox { text: "Animations"; checked: true; onToggled: { root.motion = checked; root.progress = 1; } palette.windowText: root.ink; palette.text: root.ink; palette.highlight: root.accent; font.pixelSize: 15 * root.unit }
        RowLayout {
            spacing: 14 * root.unit
            Button {
                id: begin; text: installer.busy ? "SETUP IS OPEN" : "BEGIN SETUP  →"; enabled: !installer.busy
                padding: 18 * root.unit; font.bold: true; font.pixelSize: 14 * root.unit
                contentItem: Text { text: begin.text; color: "#10191f"; font: begin.font; horizontalAlignment: Text.AlignHCenter }
                background: Rectangle { color: begin.down ? "#e1edf0" : begin.hovered ? "#c6edf1" : root.accent }
                onClicked: appPicker.open()
            }
            Button { text: "NETWORK"; padding: 18 * root.unit; onClicked: installer.network(); palette.button: "#253740"; palette.buttonText: root.ink }
        }
        ForgeText { Layout.fillWidth: true; text: installer.status; wrapMode: Text.WordWrap; color: root.dim; font.pixelSize: 11 * root.unit; lineHeight: 1.3 }
    }
    RowLayout {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 38 * root.unit }
        ForgeText { text: previewMode ? "INTERFACE PREVIEW" : "01 / PREPARE YOUR INSTALLATION"; color: root.dim; font.pixelSize: 11 * root.unit }
        Item { Layout.fillWidth: true }
        Button { text: "RESTART"; enabled: !installer.busy; flat: true; palette.buttonText: root.dim; onClicked: confirmRestart.open() }
    }
    Dialog {
        id: appPicker
        objectName: "appPicker"
        anchors.centerIn: parent
        width: Math.min(root.width - 70, 1100 * root.unit)
        height: Math.min(root.height - 70, 690 * root.unit)
        modal: true
        padding: 28 * root.unit
        title: "CHOOSE YOUR APPS_"
        background: Rectangle { color: "#19262e"; border.color: "#536d78" }
        contentItem: ColumnLayout {
            spacing: 18 * root.unit
            ForgeText { text: "Optional apps are installed automatically with Forge.\nYou can change your choices before the final disk review."; color: root.dim; font.pixelSize: 13 * root.unit; lineHeight: 1.4 }
            ScrollView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                GridLayout {
                    width: parent.width
                    columns: appPicker.width > 800 ? 2 : 1
                    columnSpacing: 16 * root.unit
                    rowSpacing: 16 * root.unit
                    Repeater {
                        model: installer.apps
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; Layout.preferredWidth: 370 * root.unit
                            implicitHeight: 94 * root.unit
                            color: appCheck.checked ? "#253740" : "#10191f"
                            border.color: appCheck.checked ? "#94dce5" : "#344b57"
                            CheckBox {
                                id: appCheck
                                anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 12 * root.unit }
                                checked: root.selectedApps.indexOf(modelData.id) >= 0
                                onToggled: root.toggleApp(modelData.id, checked)
                            }
                            Column {
                                anchors { left: appCheck.right; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 * root.unit }
                                spacing: 8 * root.unit
                                ForgeText { text: modelData.name; color: root.ink; font.pixelSize: 15 * root.unit; font.bold: true }
                                ForgeText { text: modelData.description; color: root.dim; font.pixelSize: 11 * root.unit; width: parent.width; wrapMode: Text.WordWrap }
                            }
                            TapHandler { onTapped: root.toggleApp(modelData.id, !appCheck.checked) }
                        }
                    }
                }
            }
        }
        footer: DialogButtonBox {
            padding: 20 * root.unit
            Button { text: "BACK"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "CONTINUE SETUP  →"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: installer.start(gaming.checked, root.motion, root.selectedApps)
    }
    Dialog {
        id: confirmRestart; anchors.centerIn: parent; modal: true; title: "Restart this computer?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: installer.reboot()
        Label { text: "Unsaved work in the live session will be lost." }
    }
}
