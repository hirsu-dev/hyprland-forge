import Quickshell
import Quickshell.Services.Mpris
import Quickshell.Services.UPower
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.controlsOpen
    anchors { top: true; right: true }
    margins { top: 64; right: 14 }
    implicitWidth: Math.min(392, screen ? screen.width - 28 : 392)
    implicitHeight: Math.min(540, screen ? screen.height - 90 : 540)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) content.forceActiveFocus()
    Rectangle {
        id: content
        anchors.fill: parent
        radius: 24
        color: Palette.background
        border.color: Palette.line
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ScrollView {
            anchors.fill: parent
            anchors.margins: 22
            clip: true
            ColumnLayout {
                width: panel.width - 44
                spacing: 16
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: Desktop.time; font.pixelSize: 46; font.family: Palette.font; color: Palette.text }
                    Item { Layout.fillWidth: true }
                    ForgeButton { text: "×"; onClicked: Desktop.closePanels() }
                }
                Text { text: Desktop.date; color: Palette.muted; font.family: Palette.font; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "󰖩 Network"; onClicked: { Desktop.exec(["kitty", "-e", "nmtui"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "󰂯 Bluetooth"; onClicked: { Desktop.exec(["blueman-manager"]); Desktop.closePanels() } }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 88
                    radius: 18
                    color: Palette.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        RowLayout {
                            Text { text: "Output volume"; color: Palette.text; font.family: Palette.font; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            ForgeButton {
                                text: Desktop.muted ? "Muted" : Desktop.volume + "%"
                                onClicked: { if (Desktop.sink && Desktop.sink.audio) Desktop.sink.audio.muted = !Desktop.sink.audio.muted }
                            }
                        }
                        Slider {
                            Layout.fillWidth: true
                            from: 0; to: 1
                            value: Desktop.sink && Desktop.sink.audio ? Desktop.sink.audio.volume : 0
                            enabled: Desktop.sink !== null
                            onMoved: { if (Desktop.sink && Desktop.sink.audio) Desktop.sink.audio.volume = value }
                            palette.highlight: Palette.accent
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 128
                    color: Palette.surface
                    radius: 18
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16
                        Rectangle {
                            width: 72; height: 72; radius: 36
                            color: Palette.raised
                            border.color: Palette.accent
                            border.width: 2
                            Rectangle { anchors.centerIn: parent; width: 24; height: 24; radius: 12; color: Palette.accent }
                            Rectangle { x: 33; y: 5; width: 6; height: 13; radius: 3; color: Palette.muted }
                            RotationAnimator on rotation { from: 0; to: 360; duration: 14000; loops: Animation.Infinite; running: panel.visible && Desktop.player !== null && Desktop.player.playbackState === MprisPlaybackState.Playing }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackTitle || "Untitled" : "Nothing playing"; textFormat: Text.PlainText; elide: Text.ElideRight; font.bold: true; color: Palette.text; font.pixelSize: 13 }
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackArtist : "Your next soundtrack"; textFormat: Text.PlainText; elide: Text.ElideRight; color: Palette.muted; font.pixelSize: 11 }
                            Row {
                                spacing: 5
                                ForgeButton { text: "󰒮"; onClicked: { if (Desktop.player && Desktop.player.canGoPrevious) Desktop.player.previous() } }
                                ForgeButton { text: "󰐎"; selected: true; onClicked: { if (Desktop.player && Desktop.player.canTogglePlaying) Desktop.player.togglePlaying() } }
                                ForgeButton { text: "󰒭"; onClicked: { if (Desktop.player && Desktop.player.canGoNext) Desktop.player.next() } }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "󰌾 Lock"; onClicked: { Desktop.exec(["hyprlock"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "󰒓 Audio"; onClicked: { Desktop.exec(["pavucontrol"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "󰆴 Alerts"; onClicked: Desktop.exec(["makoctl", "dismiss", "--all"]) }
                }
                Text { text: "Power profile"; color: Palette.muted; font.family: Palette.font; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "Saver"; selected: PowerProfiles.profile === PowerProfile.PowerSaver; onClicked: PowerProfiles.profile = PowerProfile.PowerSaver }
                    ForgeButton { Layout.fillWidth: true; text: "Balanced"; selected: PowerProfiles.profile === PowerProfile.Balanced; onClicked: PowerProfiles.profile = PowerProfile.Balanced }
                    ForgeButton { Layout.fillWidth: true; text: "Performance"; enabled: PowerProfiles.hasPerformanceProfile; selected: PowerProfiles.profile === PowerProfile.Performance; onClicked: PowerProfiles.profile = PowerProfile.Performance }
                }
            }
        }
    }
}
