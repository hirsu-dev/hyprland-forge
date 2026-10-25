import Quickshell
import Quickshell.Hyprland
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ForgePanel {
    id: panel
    screen: Desktop.panelScreen
    opened: Desktop.overviewOpen
    implicitWidth: Math.min(ForgeTheme.px(960), screen ? screen.width - ForgeTheme.gap(32) : ForgeTheme.px(960))
    implicitHeight: Math.min(ForgeTheme.px(640), screen ? screen.height - ForgeTheme.gap(130) : ForgeTheme.px(640))
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    property int selected: 0
    onOpenedChanged: if (opened) { selected = Math.max(0, Tasks.windows.indexOf(Tasks.activeWindow)); Qt.callLater(() => content.forceActiveFocus()) }
    ForgeFrame {
        id: content
        managedProgress: true
        progress: panel.reveal
        anchors.fill: parent
        Keys.onEscapePressed: Desktop.closePanels()
        Keys.onTabPressed: panel.selected = (panel.selected + 1) % Math.max(1, Tasks.windows.length)
        Keys.onBacktabPressed: panel.selected = (panel.selected + Tasks.windows.length - 1) % Math.max(1, Tasks.windows.length)
        Keys.onRightPressed: panel.selected = (panel.selected + 1) % Math.max(1, Tasks.windows.length)
        Keys.onLeftPressed: panel.selected = (panel.selected + Tasks.windows.length - 1) % Math.max(1, Tasks.windows.length)
        Keys.onReturnPressed: Tasks.activate(Tasks.windows[panel.selected])
        ColumnLayout {
            anchors.fill: parent; anchors.margins: ForgeTheme.gap(24); spacing: ForgeTheme.gap(18)
            RowLayout {
                Text { text: "FORGE / WINDOW GRID"; font.family: ForgeTheme.font; color: ForgeTheme.accent; font.pixelSize: ForgeTheme.fontSize(22) }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "CLOSE"; onClicked: Desktop.closePanels() }
            }
            Flow {
                Layout.fillWidth: true; spacing: ForgeTheme.gap(5)
                Repeater { model: 10; ForgeButton { required property int index; text: "WS " + (index + 1); onClicked: { Desktop.workspace(index + 1); Desktop.closePanels() } } }
            }
            Text { text: "TAB / ARROWS TO SELECT · ENTER TO FOCUS · ESC TO CANCEL"; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); color: ForgeTheme.muted }
            ScrollView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                Flow {
                    width: panel.width - 64; spacing: ForgeTheme.gap(10)
                    Repeater {
                        model: Tasks.windows
                        ForgeButton {
                            required property var modelData
                            required property int index
                            readonly property var nativeWindow: Tasks.nativeWindow(modelData)
                            width: Math.max(210, (panel.width - 90) / 3)
                            implicitHeight: ForgeTheme.px(100)
                            text: ""
                            selected: panel.selected === index
                            onClicked: Tasks.activate(modelData)
                            Column {
                                anchors.fill: parent; anchors.margins: ForgeTheme.gap(14); spacing: ForgeTheme.gap(10)
                                Text { width: parent.width; text: modelData.appId + " / WS " + (nativeWindow && nativeWindow.workspace ? nativeWindow.workspace.id : "?"); textFormat: Text.PlainText; elide: Text.ElideRight; color: parent.parent.selected ? ForgeTheme.accentText : ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
                                Text { width: parent.width; text: modelData.title; textFormat: Text.PlainText; elide: Text.ElideRight; color: parent.parent.selected ? ForgeTheme.accentText : ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(12) }
                            }
                        }
                    }
                }
            }
            Text { visible: Tasks.windows.length === 0; text: "NO OPEN WINDOWS"; color: ForgeTheme.muted; font.family: ForgeTheme.font }
        }
    }
}
