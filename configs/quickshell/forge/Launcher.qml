import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: launcher
    screen: Desktop.panelScreen
    visible: Desktop.launcherOpen
    implicitWidth: Math.min(ForgeTheme.px(720), screen ? screen.width - ForgeTheme.gap(40) : ForgeTheme.px(720))
    implicitHeight: ForgeTheme.panelHeight(screen, 560)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    readonly property var entries: DesktopEntries.applications.values.filter(a => a.name.toLowerCase().includes(search.text.toLowerCase())).sort((a,b) => a.name.localeCompare(b.name))
    onVisibleChanged: if (visible) { search.text = ""; search.forceActiveFocus(); apps.currentIndex = 0; content.enter() }
    function launchCurrent() {
        if (entries[apps.currentIndex]) { Tasks.launch(entries[apps.currentIndex]) }
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: ForgeTheme.gap(26)
            spacing: ForgeTheme.gap(16)
            RowLayout {
                Layout.fillWidth: true
                Column {
                    spacing: ForgeTheme.gap(4)
                    Text { text: "FORGE / EXECUTION INDEX"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); font.letterSpacing: 1.5 }
                    Text { text: "JACK IN_"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.italic: true; font.pixelSize: ForgeTheme.fontSize(34) }
                }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "ESC / CLOSE"; onClicked: Desktop.closePanels() }
            }
            TextField {
                id: search
                Layout.fillWidth: true
                implicitHeight: ForgeTheme.px(50)
                leftPadding: 16
                placeholderText: "> SEARCH INSTALLED APPLICATIONS"
                color: ForgeTheme.cyan
                placeholderTextColor: ForgeTheme.muted
                selectionColor: ForgeTheme.accent
                selectedTextColor: ForgeTheme.accentText
                font.family: ForgeTheme.font
                font.pixelSize: ForgeTheme.fontSize(13)
                background: Rectangle {
                    color: ForgeTheme.surface
                    border.color: search.activeFocus ? ForgeTheme.cyan : ForgeTheme.line
                    Rectangle { x: 0; y: parent.height - 2; width: parent.width * 0.2; height: 2; color: ForgeTheme.accent }
                }
                onTextChanged: apps.currentIndex = 0
                onAccepted: launcher.launchCurrent()
                Keys.onEscapePressed: Desktop.closePanels()
                Keys.onDownPressed: apps.currentIndex = Math.min(apps.count - 1, apps.currentIndex + 1)
                Keys.onUpPressed: apps.currentIndex = Math.max(0, apps.currentIndex - 1)
            }
            ListView {
                id: apps
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: ForgeTheme.gap(4)
                highlightMoveDuration: ForgeTheme.duration / 2
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                model: launcher.entries
                delegate: ForgeFrame {
                    id: entry
                    required property var modelData
                    required property int index
                    readonly property bool current: index === apps.currentIndex
                    width: apps.width
                    height: ForgeTheme.px(52)
                    cut: ForgeTheme.px(8)
                    ornament: false
                    color: current ? ForgeTheme.accent : mouse.containsMouse ? ForgeTheme.raised : ForgeTheme.surface
                    borderColor: current ? ForgeTheme.accent : ForgeTheme.line
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: ForgeTheme.gap(14)
                        anchors.rightMargin: ForgeTheme.gap(16)
                        spacing: ForgeTheme.gap(14)
                        Text { text: String(entry.index + 1).padStart(2, "0"); color: entry.current ? ForgeTheme.accentText : ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
                        Image { source: Quickshell.iconPath(entry.modelData.icon, "application-x-executable"); sourceSize.width: ForgeTheme.px(26); sourceSize.height: ForgeTheme.px(26); Layout.preferredWidth: ForgeTheme.px(26); Layout.preferredHeight: ForgeTheme.px(26) }
                        Text { Layout.fillWidth: true; text: entry.modelData.name; textFormat: Text.PlainText; elide: Text.ElideRight; color: entry.current ? ForgeTheme.accentText : ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(13) }
                        Text { text: "↗"; color: entry.current ? ForgeTheme.accentText : ForgeTheme.cyan; font.pixelSize: ForgeTheme.fontSize(18) }
                    }
                    Menu {
                        id: appMenu
                        MenuItem { text: Tasks.pinned(entry.modelData) ? "Unpin from taskbar" : "Pin to taskbar"; enabled: !Tasks.busy; onTriggered: Tasks.togglePin(entry.modelData) }
                    }
                    MouseArea {
                        id: mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: event => {
                            apps.currentIndex = entry.index
                            if (event.button === Qt.RightButton) appMenu.popup()
                            else launcher.launchCurrent()
                        }
                    }
                }
                Text { anchors.centerIn: parent; visible: apps.count === 0; text: "NO SIGNAL / NO MATCHES"; color: ForgeTheme.muted; font.family: ForgeTheme.font }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "↑ ↓ SELECT   /   ENTER EXECUTE"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
                Item { Layout.fillWidth: true }
                Text { text: launcher.entries.length + " FILES"; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
            }
        }
    }
}
