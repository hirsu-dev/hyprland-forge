import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#100d16"
    property bool motion: String(config.Motion).toLowerCase() !== "false"
    property bool busy: false
    property string notice: "LOCAL SESSION / SECURE SIGN-IN"
    property real reveal: 0
    readonly property real unit: Math.min(width / 1920, height / 1080)
    readonly property color yellow: "#fcee0a"
    readonly property color cyan: "#74f7ef"
    readonly property color ink: "#f4edf5"
    readonly property string typeface: "JetBrainsMono Nerd Font"

    function login() {
        if (busy || !username.text.trim() || !password.text || sessions.currentIndex < 0)
            return;
        busy = true;
        notice = "VERIFYING IDENTITY...";
        sddm.login(username.text.trim(), password.text, sessions.currentIndex);
    }

    Component.onCompleted: {
        reveal = 1;
        password.forceActiveFocus();
    }
    Behavior on reveal { NumberAnimation { duration: root.motion ? 750 : 0; easing.type: Easing.OutCubic } }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false;
            password.text = "";
            root.notice = "ACCESS DENIED / CHECK YOUR PASSWORD";
            password.forceActiveFocus();
        }
        function onLoginSucceeded() {
            password.text = "";
            root.notice = "ACCESS GRANTED / ENTERING FORGE";
            root.reveal = 0;
        }
    }

    Canvas {
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.scale(width / 1920, height / 1080);
            ctx.strokeStyle = "#281d2a";
            ctx.lineWidth = 1;
            for (let x = 48; x < 1920; x += 64) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 1080); ctx.stroke();
            }
            for (let y = 42; y < 1080; y += 64) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(1920, y); ctx.stroke();
            }
            ctx.strokeStyle = "#693642";
            for (let n = 0; n < 150; n += 30) {
                ctx.beginPath();
                ctx.moveTo(1140+n, 178+n); ctx.lineTo(1530-n, 178+n);
                ctx.lineTo(1770-n, 418); ctx.lineTo(1770-n, 742-n);
                ctx.lineTo(1560-n, 930-n); ctx.lineTo(1170+n, 930-n);
                ctx.lineTo(970+n, 730-n); ctx.lineTo(970+n, 340+n);
                ctx.closePath(); ctx.stroke();
            }
            ctx.fillStyle = "#fcee0a";
            ctx.beginPath();
            ctx.moveTo(1200,330); ctx.lineTo(1560,330); ctx.lineTo(1500,400);
            ctx.lineTo(1300,400); ctx.lineTo(1270,465); ctx.lineTo(1460,465);
            ctx.lineTo(1405,532); ctx.lineTo(1240,532); ctx.lineTo(1160,713);
            ctx.lineTo(1065,713); ctx.closePath(); ctx.fill();
            ctx.strokeStyle = "#74f7ef";
            ctx.lineWidth = 3;
            ctx.beginPath(); ctx.moveTo(1000,796); ctx.lineTo(1128,924); ctx.lineTo(1440,924); ctx.stroke();
        }
    }
    Rectangle {
        width: parent.width
        height: Math.max(1, root.unit * 2)
        color: root.cyan
        opacity: root.motion ? 0.055 : 0
        SequentialAnimation on y {
            running: root.motion && root.visible && !root.busy
            loops: Animation.Infinite
            NumberAnimation { from: 0; to: root.height; duration: 9000 }
        }
    }
    Item {
        id: layout
        width: 1920
        height: 1080
        anchors.centerIn: parent
        scale: root.unit

        Text { x: 96; y: 72; text: "F /  OVERDRIVE SYSTEMS"; color: root.yellow; font.pixelSize: 20; font.family: root.typeface }
        Rectangle { x: 96; y: 118; width: 1728; height: 2; color: "#693642" }
        Text { x: 1450; y: 72; text: "FORGE // LOCAL SESSION"; color: "#bdaab8"; font.pixelSize: 16; font.family: root.typeface }
        Text { x: 96; y: 194; text: "03 / SESSION ACCESS"; color: root.cyan; font.pixelSize: 20; font.family: root.typeface }
        Text { x: 88; y: 246; text: "FORGE"; color: root.yellow; font.pixelSize: 118; font.bold: true; font.family: root.typeface }
        Text { x: 96; y: 394; text: "YOUR MACHINE. YOUR SIGNAL."; color: root.ink; font.pixelSize: 24; font.family: root.typeface }
        Rectangle { x: 96; y: 452; width: 694; height: 3; color: "#ff4d61" }

        Column {
            id: form
            x: 96 - (1 - root.reveal) * 28
            y: 492
            width: 694
            spacing: 14
            opacity: root.reveal
            enabled: !root.busy
            Text { text: "LINUX ACCOUNT"; color: "#bdaab8"; font.pixelSize: 16; font.family: root.typeface }
            TextField {
                id: username
                objectName: "forgeUsername"
                width: parent.width
                height: 54
                text: userModel.lastUser
                placeholderText: "Username"
                color: root.ink
                placeholderTextColor: "#bdaab8"
                selectByMouse: true
                font.pixelSize: 22
                font.family: root.typeface
                leftPadding: 18
                background: Rectangle { color: "#1d141f"; border.color: username.activeFocus ? root.cyan : "#693642"; border.width: 2 }
                KeyNavigation.tab: password
                onAccepted: password.forceActiveFocus()
            }
            TextField {
                id: password
                objectName: "forgePassword"
                width: parent.width
                height: 62
                placeholderText: "Account password"
                color: root.ink
                placeholderTextColor: "#bdaab8"
                echoMode: TextInput.Password
                passwordMaskDelay: 0
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                font.pixelSize: 24
                font.family: root.typeface
                leftPadding: 18
                background: Rectangle { color: "#1d141f"; border.color: password.activeFocus ? root.yellow : "#693642"; border.width: 2 }
                KeyNavigation.tab: sessions
                onAccepted: root.login()
            }
            ComboBox {
                id: sessions
                objectName: "forgeSessions"
                width: parent.width
                height: 48
                model: sessionModel
                textRole: "name"
                currentIndex: sessionModel.lastIndex
                font.pixelSize: 18
                font.family: root.typeface
                palette.button: "#1d141f"
                palette.buttonText: root.ink
                palette.highlight: root.yellow
                palette.highlightedText: "#100d16"
                KeyNavigation.tab: enter
            }
            Button {
                id: enter
                objectName: "forgeEnter"
                width: parent.width
                height: 62
                text: "ENTER FORGE   >"
                font.pixelSize: 22
                font.bold: true
                font.family: root.typeface
                palette.buttonText: "#100d16"
                background: Rectangle { color: enter.down ? root.cyan : root.yellow; border.color: enter.activeFocus ? root.ink : root.yellow; border.width: 3 }
                onClicked: root.login()
                KeyNavigation.tab: username
            }
        }
        Text { x: 96; y: 852; width: 760; text: root.notice; color: root.busy ? root.yellow : root.cyan; font.pixelSize: 18; font.family: root.typeface; wrapMode: Text.Wrap }
        Text { x: 96; y: 902; text: "BOOT PASSWORD AND ACCOUNT PASSWORD ARE SEPARATE"; color: "#bdaab8"; font.pixelSize: 16; font.family: root.typeface }
        Rectangle { x: 96; y: 972; width: 1728; height: 2; color: "#693642" }
        Row {
            x: 96
            y: 990
            spacing: 16
            Button { text: root.motion ? "MOTION ON" : "MOTION OFF"; onClicked: root.motion = !root.motion; palette.button: "#1d141f"; palette.buttonText: root.ink }
            Button { text: "RESTART"; enabled: sddm.canReboot && !root.busy; onClicked: restart.open(); palette.button: "#1d141f"; palette.buttonText: root.ink }
            Button { text: "POWER OFF"; enabled: sddm.canPowerOff && !root.busy; onClicked: shutdown.open(); palette.button: "#1d141f"; palette.buttonText: root.ink }
        }
    }
    Dialog {
        id: restart
        anchors.centerIn: parent
        title: "Restart this computer?"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: sddm.reboot()
    }
    Dialog {
        id: shutdown
        anchors.centerIn: parent
        title: "Power off this computer?"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: sddm.powerOff()
    }
}
