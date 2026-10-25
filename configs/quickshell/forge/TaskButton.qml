import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ForgeFrame {
    id: root
    property var window: null
    property var entry: null
    property bool showTitle: false
    readonly property var running: window ? [window] : Tasks.windowsFor(entry)
    readonly property bool active: running.some(item => item.activated)
    readonly property string label: window ? window.title || window.appId || "Untitled window" : entry ? entry.name : "Application unavailable"
    implicitWidth: ForgeTheme.px(showTitle ? 184 : 46)
    implicitHeight: ForgeTheme.px(36)
    cut: ForgeTheme.px(8)
    ornament: false
    activeFocusOnTab: true
    color: active ? ForgeTheme.raised : pointer.containsMouse || activeFocus ? ForgeTheme.surface : ForgeTheme.background
    borderColor: active ? ForgeTheme.accent : pointer.containsMouse || activeFocus ? ForgeTheme.cyan : ForgeTheme.line
    Behavior on color { ColorAnimation { duration: ForgeTheme.duration / 2 } }
    Behavior on borderColor { ColorAnimation { duration: ForgeTheme.duration / 2 } }
    transform: Translate {
        y: ForgeTheme.motion && pointer.containsMouse ? -ForgeTheme.px(2) : 0
        Behavior on y { NumberAnimation { duration: ForgeTheme.duration / 2; easing.type: Easing.OutCubic } }
    }
    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.onPressAction: activate()
    Keys.onReturnPressed: activate()
    Keys.onSpacePressed: activate()
    function activate() { if (window) Tasks.activate(window); else Tasks.launchOrFocus(entry) }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: ForgeTheme.gap(12)
        anchors.rightMargin: ForgeTheme.gap(12)
        spacing: ForgeTheme.gap(9)
        Image {
            source: Quickshell.iconPath(root.entry && root.entry.icon ? root.entry.icon : root.window ? root.window.appId : "", "application-x-executable")
            sourceSize.width: ForgeTheme.px(20); sourceSize.height: ForgeTheme.px(20)
            Layout.preferredWidth: ForgeTheme.px(20); Layout.preferredHeight: ForgeTheme.px(20)
        }
        Text {
            visible: root.showTitle
            Layout.fillWidth: true
            text: root.label
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: root.active ? ForgeTheme.text : ForgeTheme.muted
            font.family: ForgeTheme.font
            font.pixelSize: ForgeTheme.fontSize(11)
        }
    }
    Rectangle {
        x: 10; y: parent.height - 2
        width: root.active ? parent.width - 20 : Math.min(16, parent.width - 20)
        height: 2
        visible: root.running.length > 0
        color: root.active ? ForgeTheme.accent : ForgeTheme.cyan
        Behavior on width { NumberAnimation { duration: ForgeTheme.duration } }
    }
    Text {
        visible: !root.window && root.running.length > 1
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: ForgeTheme.gap(3)
        text: root.running.length
        font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(8)
        color: ForgeTheme.cyan
    }
    ToolTip {
        visible: pointer.containsMouse && !context.visible
        delay: 450
        text: root.label
        contentItem: Text { text: root.label; textFormat: Text.PlainText; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11) }
        background: Rectangle { color: ForgeTheme.background; border.color: ForgeTheme.cyan }
    }
    Menu {
        id: context
        palette.window: ForgeTheme.surface
        palette.windowText: ForgeTheme.text
        palette.text: ForgeTheme.text
        palette.highlight: ForgeTheme.raised
        palette.highlightedText: ForgeTheme.accent
        MenuItem { text: "Focus window"; visible: root.running.length > 0; onTriggered: Tasks.activate(root.window || root.running[0]) }
        MenuItem { text: "New window"; visible: root.entry !== null; onTriggered: Tasks.launch(root.entry) }
        MenuItem { text: Tasks.pinned(root.entry) ? "Unpin application" : "Pin application"; visible: root.entry !== null; enabled: !Tasks.busy; onTriggered: Tasks.togglePin(root.entry) }
        MenuSeparator { visible: root.window !== null }
        MenuItem { text: "Close window"; visible: root.window !== null; onTriggered: if (root.window) root.window.close() }
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) context.popup()
            else if (mouse.button === Qt.MiddleButton) Tasks.launch(root.entry)
            else root.activate()
        }
    }
}
