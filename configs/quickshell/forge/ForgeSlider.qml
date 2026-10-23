import QtQuick
import QtQuick.Controls

Slider {
    id: slider
    implicitHeight: 28
    opacity: enabled ? 1 : 0.35
    background: Rectangle {
        x: slider.leftPadding
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: slider.availableWidth
        height: 4
        color: ForgeTheme.line
        Rectangle { width: parent.width * slider.visualPosition; height: parent.height; color: ForgeTheme.cyan }
    }
    handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: 10; height: 20
        color: slider.activeFocus ? ForgeTheme.accent : ForgeTheme.cyan
        Rectangle { anchors.centerIn: parent; width: 2; height: 10; color: ForgeTheme.background }
    }
}
