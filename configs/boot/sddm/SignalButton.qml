import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool motion: true
    property bool primary: false
    implicitWidth: Math.max(150, contentItem.implicitWidth + 40)
    implicitHeight: 48
    leftPadding: 20; rightPadding: 20
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: 18
    opacity: enabled ? 1 : .45
    background: SignalPanel {
        motion: button.motion
        fill: button.primary ? (button.down ? "#3aa89e" : "#74f7df") : (button.hovered || button.down ? "#18313b" : "#101c27")
        stroke: button.activeFocus ? "#e9f4f5" : button.primary || button.hovered ? "#74f7df" : "#35535f"
    }
    contentItem: Text {
        text: button.text; font: button.font
        color: button.primary ? "#080d16" : "#e9f4f5"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
