import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: launcher
    screen: Desktop.panelScreen
    visible: Desktop.launcherOpen
    implicitWidth: Math.min(720, screen ? screen.width - 40 : 720)
    implicitHeight: Math.min(560, screen ? screen.height - 90 : 560)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    readonly property var entries: DesktopEntries.applications.values.filter(a => a.name.toLowerCase().includes(search.text.toLowerCase())).sort((a,b) => a.name.localeCompare(b.name))
    onVisibleChanged: if (visible) { search.text = ""; search.forceActiveFocus(); apps.currentIndex = 0; content.enter() }
    function launchCurrent() {
        if (entries[apps.currentIndex]) { entries[apps.currentIndex].execute(); Desktop.closePanels() }
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 26
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Column {
                    spacing: 4
                    Text { text: "FORGE / EXECUTION INDEX"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: 10; font.letterSpacing: 1.5 }
                    Text { text: "JACK IN_"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.italic: true; font.pixelSize: 34 }
                }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "ESC / CLOSE"; onClicked: Desktop.closePanels() }
            }
            TextField {
                id: search
                Layout.fillWidth: true
                implicitHeight: 50
                leftPadding: 16
                placeholderText: "> SEARCH INSTALLED APPLICATIONS"
                color: ForgeTheme.cyan
                placeholderTextColor: ForgeTheme.muted
                selectionColor: ForgeTheme.accent
                selectedTextColor: ForgeTheme.accentText
                font.family: ForgeTheme.font
                font.pixelSize: 13
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
                spacing: 4
                highlightMoveDuration: ForgeTheme.duration / 2
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                model: launcher.entries
                delegate: ForgeFrame {
                    id: entry
                    required property var modelData
                    required property int index
                    readonly property bool current: index === apps.currentIndex
                    width: apps.width
                    height: 52
                    cut: 8
                    ornament: false
                    color: current ? ForgeTheme.accent : mouse.containsMouse ? ForgeTheme.raised : ForgeTheme.surface
                    borderColor: current ? ForgeTheme.accent : ForgeTheme.line
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 16
                        spacing: 14
                        Text { text: String(entry.index + 1).padStart(2, "0"); color: entry.current ? ForgeTheme.accentText : ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: 10 }
                        Image { source: Quickshell.iconPath(entry.modelData.icon, "application-x-executable"); sourceSize.width: 26; sourceSize.height: 26; Layout.preferredWidth: 26; Layout.preferredHeight: 26 }
                        Text { Layout.fillWidth: true; text: entry.modelData.name; textFormat: Text.PlainText; elide: Text.ElideRight; color: entry.current ? ForgeTheme.accentText : ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 13 }
                        Text { text: "↗"; color: entry.current ? ForgeTheme.accentText : ForgeTheme.cyan; font.pixelSize: 18 }
                    }
                    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { apps.currentIndex = entry.index; launcher.launchCurrent() } }
                }
                Text { anchors.centerIn: parent; visible: apps.count === 0; text: "NO SIGNAL / NO MATCHES"; color: ForgeTheme.muted; font.family: ForgeTheme.font }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "↑ ↓ SELECT   /   ENTER EXECUTE"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 10 }
                Item { Layout.fillWidth: true }
                Text { text: launcher.entries.length + " FILES"; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: 10 }
            }
        }
    }
}
