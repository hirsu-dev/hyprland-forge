import QtQuick
import QtQuick.Controls

Slider {
    id: slider
    background: Rectangle {
        x: slider.leftPadding
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: slider.availableWidth
        height: 5; radius: 3
        color: ForgeTheme.raised
        Rectangle { width: parent.width * slider.visualPosition; height: parent.height; radius: 3; color: ForgeTheme.accent }
    }
    handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: 16; height: 16; radius: 8
        color: ForgeTheme.accent
    }
}
