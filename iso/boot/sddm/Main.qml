import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    width: 1920; height: 1080; color: "#10191f"
    property bool busy: false
    property string notice: "WELCOME BACK"
    property real reveal: 0
    property bool restartRequested: false
    readonly property real unit: Math.max(0.7, Math.min(width / 1280, height / 800))
    readonly property bool motion: String(config.Motion).toLowerCase() !== "false"
    Component.onCompleted: { reveal = 1; if (username.text) password.forceActiveFocus(); else username.forceActiveFocus(); }
    Behavior on reveal { NumberAnimation { duration: root.motion ? 650 : 0; easing.type: Easing.OutCubic } }
    function login() {
        if (!busy && username.text.trim() && password.text && sessions.currentIndex >= 0) {
            busy = true; notice = "VERIFYING...";
            sddm.login(username.text.trim(), password.text, sessions.currentIndex);
        }
    }
    Connections {
        target: sddm
        function onLoginFailed() { root.busy = false; password.text = ""; root.notice = "CHECK YOUR PASSWORD"; password.forceActiveFocus(); }
        function onLoginSucceeded() { password.text = ""; root.notice = "ACCESS GRANTED"; root.reveal = 0; }
    }
    Canvas {
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const c = getContext("2d"); c.reset(); c.strokeStyle = "#253740";
            const u = root.unit;
            for (let x = 32*u; x < width; x += 80*u) { c.beginPath();c.moveTo(x,0);c.lineTo(x,height);c.stroke(); }
            for (let y = 32*u; y < height; y += 80*u) { c.beginPath();c.moveTo(0,y);c.lineTo(width,y);c.stroke(); }
            c.strokeStyle = "#536d78"; c.lineWidth=2;
            c.beginPath();c.moveTo(width*.65,height*.2);c.lineTo(width*.84,height*.2);c.lineTo(width*.94,height*.35);c.lineTo(width*.94,height*.7);c.lineTo(width*.82,height*.85);c.lineTo(width*.62,height*.85);c.stroke();
        }
    }
    ColumnLayout {
        width: Math.min(430 * root.unit, parent.width - 80)
        anchors { left: parent.left; leftMargin: 90 * root.unit; verticalCenter: parent.verticalCenter }
        spacing: 24 * root.unit; opacity: root.reveal
        Text { text: "FORGE_"; color: "#e1edf0"; font.family: "JetBrainsMono Nerd Font"; font.bold: true; font.pixelSize: 64 * root.unit }
        Text { text: root.notice; color: "#94dce5"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 13 * root.unit; font.letterSpacing: 3 }
        TextField { id: username; Layout.fillWidth: true; placeholderText: "Username"; placeholderTextColor: "#a3b9c1"; text: userModel.lastUser || config.DefaultUser || ""; enabled: !root.busy; padding: 18 * root.unit; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 16 * root.unit; color: "#e1edf0"; onAccepted: password.forceActiveFocus(); background: Rectangle { color: "#19262e"; border.color: "#536d78" } }
        TextField { id: password; Layout.fillWidth: true; placeholderText: "Password"; placeholderTextColor: "#a3b9c1"; echoMode: TextInput.Password; enabled: !root.busy; padding: 18 * root.unit; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 16 * root.unit; color: "#e1edf0"; onAccepted: root.login(); background: Rectangle { color: "#19262e"; border.color: password.activeFocus ? "#94dce5" : "#536d78" } }
        ComboBox {
            id: sessions; Layout.fillWidth: true; implicitHeight: 46 * root.unit
            model: sessionModel; textRole: "name"; currentIndex: sessionModel.lastIndex; enabled: !root.busy
            palette.button: "#253740"; palette.buttonText: "#e1edf0"; palette.text: "#e1edf0"; palette.base: "#19262e"
            font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 14 * root.unit
            background: Rectangle { color: "#253740"; border.color: "#536d78" }
            contentItem: Text { text: sessions.displayText; font: sessions.font; color: "#e1edf0"; leftPadding: 14 * root.unit; verticalAlignment: Text.AlignVCenter }
        }
        Button {
            id: enter; text: root.busy ? "SIGNING IN..." : "ENTER FORGE  →"; Layout.fillWidth: true; padding: 18 * root.unit
            enabled: !root.busy && username.text.trim().length > 0 && password.text.length > 0 && sessions.currentIndex >= 0
            onClicked: root.login(); font.family: "JetBrainsMono Nerd Font"; font.bold: true; font.pixelSize: 16 * root.unit
            background: Rectangle { color: enter.enabled ? "#94dce5" : "#536d78" }
            contentItem: Text { text: enter.text; font: enter.font; color: "#10191f"; horizontalAlignment: Text.AlignHCenter }
        }
    }
    Row {
        anchors { right: parent.right; bottom: parent.bottom; margins: 40 * root.unit }
        spacing: 16 * root.unit
        Button { text: "RESTART"; enabled: !root.busy; palette.button: "#253740"; palette.buttonText: "#e1edf0"; onClicked: { root.restartRequested = true; powerConfirm.open(); } }
        Button { text: "POWER OFF"; enabled: !root.busy; palette.button: "#253740"; palette.buttonText: "#e1edf0"; onClicked: { root.restartRequested = false; powerConfirm.open(); } }
    }
    Dialog {
        id: powerConfirm; anchors.centerIn: parent; modal: true
        title: root.restartRequested ? "Restart this computer?" : "Power off this computer?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: { if (root.restartRequested) sddm.reboot(); else sddm.powerOff(); }
    }
}
