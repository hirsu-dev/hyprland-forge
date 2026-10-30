import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#080d16"
    property bool motion: String(config.Motion).toLowerCase() !== "false"
    property bool busy: false
    property bool denied: false
    property real errorShift: 0
    property string notice: "LOCAL SESSION / SECURE SIGN-IN"
    property real reveal: 0
    readonly property real unit: Math.min(width / 1920, height / 1080)
    readonly property color yellow: "#74f7df"
    readonly property color cyan: "#74f7df"
    readonly property color ink: "#e9f4f5"
    readonly property string typeface: "JetBrainsMono Nerd Font"
    onMotionChanged: { if (!motion) { rejectMotion.stop(); errorShift = 0; } }

    function login() {
        if (busy || !username.text.trim() || !password.text || sessions.currentIndex < 0)
            return;
        busy = true;
        denied = false;
        notice = "VERIFYING IDENTITY...";
        sddm.login(username.text.trim(), password.text, sessions.currentIndex);
    }

    Component.onCompleted: {
        reveal = 1;
        if (username.text) password.forceActiveFocus(); else username.forceActiveFocus();
    }
    Behavior on reveal { NumberAnimation { duration: root.motion ? 750 : 0; easing.type: Easing.OutCubic } }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false;
            root.denied = true;
            password.text = "";
            root.notice = "ACCESS DENIED / CHECK YOUR PASSWORD";
            password.forceActiveFocus();
            if (root.motion) rejectMotion.restart();
        }
        function onLoginSucceeded() {
            password.text = "";
            root.notice = "ACCESS GRANTED / ENTERING FORGE";
            root.reveal = 0;
        }
    }

    SequentialAnimation {
        id: rejectMotion
        NumberAnimation { target: root; property: "errorShift"; to: -8; duration: 45 }
        NumberAnimation { target: root; property: "errorShift"; to: 6; duration: 65 }
        NumberAnimation { target: root; property: "errorShift"; to: -3; duration: 65 }
        NumberAnimation { target: root; property: "errorShift"; to: 0; duration: 100; easing.type: Easing.OutCubic }
    }
    SignalField { anchors.centerIn: parent; scale: root.unit; motion: root.motion }
    Item {
        id: layout
        width: 1920
        height: 1080
        anchors.centerIn: parent
        scale: root.unit

        Text { x: 96; y: 72; text: "F /  OVERDRIVE SYSTEMS"; color: root.yellow; font.pixelSize: 20; font.family: root.typeface }
        Rectangle { x: 96; y: 118; width: 1728; height: 2; color: "#263b48" }
        Text { x: 1450; y: 72; text: "FORGE // LOCAL SESSION"; color: "#839ba8"; font.pixelSize: 16; font.family: root.typeface }
        Text { x: 96; y: 194; text: "03 / SESSION ACCESS"; color: root.cyan; font.pixelSize: 20; font.family: root.typeface }
        Text { x: 88; y: 246; text: "FORGE"; color: root.ink; font.pixelSize: 118; font.bold: true; font.family: root.typeface }
        Text { x: 96; y: 394; text: "YOUR MACHINE. YOUR SIGNAL."; color: root.ink; font.pixelSize: 24; font.family: root.typeface }
        Rectangle { x: 96; y: 452; width: 694; height: 3; color: "#ff4264" }

        Column {
            id: form
            x: 96 - (1 - root.reveal) * 28 + root.errorShift
            y: 492
            width: 694
            spacing: 14
            opacity: root.reveal
            enabled: !root.busy
            Text { text: "LINUX ACCOUNT"; color: "#839ba8"; font.pixelSize: 16; font.family: root.typeface }
            TextField {
                id: username
                objectName: "forgeUsername"
                width: parent.width
                height: 54
                text: userModel.lastUser || config.DefaultUser || ""
                placeholderText: "Username"
                color: root.ink
                placeholderTextColor: "#839ba8"
                selectByMouse: true
                font.pixelSize: 22
                font.family: root.typeface
                leftPadding: 18
                background: SignalPanel { motion: root.motion; stroke: username.activeFocus ? root.cyan : "#263b48" }
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
                placeholderTextColor: "#839ba8"
                echoMode: TextInput.Password
                passwordMaskDelay: 0
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                font.pixelSize: 24
                font.family: root.typeface
                leftPadding: 18
                background: SignalPanel { motion: root.motion; stroke: root.denied ? "#ff4264" : password.activeFocus ? root.cyan : "#263b48" }
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
                palette.button: "#101c27"
                palette.buttonText: root.ink
                palette.highlight: root.yellow
                palette.highlightedText: "#080d16"
                background: SignalPanel { motion: root.motion; stroke: sessions.activeFocus ? root.cyan : "#35535f" }
                contentItem: Text { text: sessions.displayText; font: sessions.font; color: root.ink; leftPadding: 18; verticalAlignment: Text.AlignVCenter }
                indicator: Text { x: sessions.width - 34; y: (sessions.height - height) / 2; text: sessions.popup.visible ? "-" : "+"; color: root.cyan; font.family: root.typeface; font.pixelSize: 22 }
                delegate: ItemDelegate {
                    id: sessionOption
                    width: sessions.width; height: 48
                    text: model.name; font: sessions.font
                    highlighted: sessions.highlightedIndex === index
                    background: SignalPanel { motion: root.motion; fill: sessionOption.highlighted ? "#18313b" : "#101c27"; stroke: sessionOption.highlighted ? root.cyan : "#263b48" }
                    contentItem: Text { text: sessionOption.text; font: sessionOption.font; color: root.ink; leftPadding: 12; verticalAlignment: Text.AlignVCenter }
                }
                popup: Popup {
                    objectName: "forgeSessionPopup"
                    y: sessions.height + 4; width: sessions.width
                    implicitHeight: contentItem.implicitHeight + 8
                    padding: 4
                    background: SignalPanel { motion: root.motion; stroke: "#35535f" }
                    contentItem: ListView {
                        clip: true; implicitHeight: Math.min(contentHeight, 260)
                        model: sessions.popup.visible ? sessions.delegateModel : null
                        currentIndex: sessions.highlightedIndex
                    }
                }
                KeyNavigation.tab: enter
            }
            SignalButton {
                id: enter
                objectName: "forgeEnter"
                width: parent.width
                height: 62
                text: "ENTER FORGE   >"
                motion: root.motion
                primary: true
                font.pixelSize: 22
                font.bold: true
                font.family: root.typeface
                onClicked: root.login()
                KeyNavigation.tab: username
            }
        }
        Text { x: 96; y: 852; width: 760; text: root.notice; color: root.denied ? "#ff4264" : root.cyan; font.pixelSize: 18; font.family: root.typeface; wrapMode: Text.Wrap }
        Text { x: 96; y: 902; text: String(config.BootGate).toLowerCase() === "true" ? "BOOT PASSWORD AND ACCOUNT PASSWORD ARE SEPARATE" : "YOUR LOCAL ACCOUNT / YOUR ENVIRONMENT"; color: "#839ba8"; font.pixelSize: 16; font.family: root.typeface }
        Rectangle { x: 96; y: 972; width: 1728; height: 2; color: "#263b48" }
        Row {
            x: 96
            y: 990
            spacing: 16
            SignalButton { text: root.motion ? "MOTION ON" : "MOTION OFF"; motion: root.motion; onClicked: root.motion = !root.motion }
            SignalButton { text: "RESTART"; motion: root.motion; enabled: sddm.canReboot && !root.busy; onClicked: restart.open() }
            SignalButton { text: "POWER OFF"; motion: root.motion; enabled: sddm.canPowerOff && !root.busy; onClicked: shutdown.open() }
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
