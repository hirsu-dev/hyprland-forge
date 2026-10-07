import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: launcher
    screen: Desktop.panelScreen
    visible: Desktop.launcherOpen
    implicitWidth: Math.min(620, screen ? screen.width - 40 : 620)
    implicitHeight: Math.min(490, screen ? screen.height - 90 : 490)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    readonly property var entries: DesktopEntries.applications.values.filter(a => a.name.toLowerCase().includes(search.text.toLowerCase())).sort((a,b) => a.name.localeCompare(b.name))
    onVisibleChanged: if (visible) { search.text = ""; search.forceActiveFocus(); apps.currentIndex = 0 }
    function launchCurrent() {
        if (entries[apps.currentIndex]) { entries[apps.currentIndex].execute(); Desktop.closePanels() }
    }
    Rectangle {
        anchors.fill: parent
        opacity: launcher.visible ? 1 : 0
        scale: launcher.visible ? 1 : 0.96
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        radius: 24
        color: ForgeTheme.background
        border.color: ForgeTheme.line
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14
            Text { text: "F O R G E"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.pixelSize: 12 }
            TextField {
                id: search
                Layout.fillWidth: true
                implicitHeight: 50
                placeholderText: "Find an application…"
                color: ForgeTheme.text
                placeholderTextColor: ForgeTheme.muted
                font.family: ForgeTheme.font
                background: Rectangle { radius: 14; color: ForgeTheme.surface; border.color: ForgeTheme.line }
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
                spacing: 5
                highlightMoveDuration: 120
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                model: launcher.entries
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: apps.width
                    height: 48
                    radius: 12
                    color: ListView.isCurrentItem ? ForgeTheme.accent : mouse.containsMouse ? ForgeTheme.raised : "transparent"
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 14
                        Image { source: Quickshell.iconPath(modelData.icon, "application-x-executable"); sourceSize.width: 28; sourceSize.height: 28; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
                        Text { Layout.fillWidth: true; text: modelData.name; textFormat: Text.PlainText; elide: Text.ElideRight; color: index === apps.currentIndex ? ForgeTheme.accentText : ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 13 }
                    }
                    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; onClicked: { apps.currentIndex = parent.index; launcher.launchCurrent() } }
                }
                Text { anchors.centerIn: parent; visible: apps.count === 0; text: "No matching applications"; color: ForgeTheme.muted }
            }
        }
    }
}
