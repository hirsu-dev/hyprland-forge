import QtQuick

Item {
    id: root
    property bool active: true
    readonly property bool animating: active && visible && !!Window.window && Window.window.visible && ForgeTheme.ambient
    implicitWidth: ForgeTheme.px(66)
    implicitHeight: ForgeTheme.px(26)
    Row {
        anchors.bottom: parent.bottom
        spacing: ForgeTheme.px(3)
        Repeater {
            model: 9
            Rectangle {
                id: band
                required property int index
                width: ForgeTheme.px(4)
                height: ForgeTheme.px(5 + (index * 7) % 18)
                anchors.bottom: parent.bottom
                color: index % 3 === 0 ? ForgeTheme.danger : index % 3 === 1 ? ForgeTheme.accent : ForgeTheme.cyan
                opacity: 0.35 + ForgeTheme.intensity * 0.55
                SequentialAnimation on height {
                    running: root.animating
                    loops: Animation.Infinite
                    NumberAnimation { to: ForgeTheme.px(5 + (band.index * 11 + 5) % 20); duration: Math.round((650 + band.index * 67) / ForgeTheme.speed); easing.type: Easing.InOutSine }
                    NumberAnimation { to: ForgeTheme.px(4 + (band.index * 7) % 19); duration: Math.round((800 + band.index * 53) / ForgeTheme.speed); easing.type: Easing.InOutSine }
                }
            }
        }
    }
}
