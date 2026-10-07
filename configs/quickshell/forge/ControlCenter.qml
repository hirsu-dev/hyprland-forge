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
    implicitHeight: Math.min(610, screen ? screen.height - 90 : 610)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) content.forceActiveFocus()
    Rectangle {
        id: content
        anchors.fill: parent
        radius: 24
        color: ForgeTheme.background
        border.color: ForgeTheme.line
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
                    Text { text: Desktop.time; font.pixelSize: 46; font.family: ForgeTheme.font; color: ForgeTheme.text }
                    Item { Layout.fillWidth: true }
                    ForgeButton { text: "×"; onClicked: Desktop.closePanels() }
                }
                Text { text: Desktop.date; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "󰖩 Network"; onClicked: { Desktop.exec(["kitty", "-e", "nmtui"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "󰂯 Bluetooth"; onClicked: { Desktop.exec(["blueman-manager"]); Desktop.closePanels() } }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 88
                    radius: 18
                    color: ForgeTheme.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        RowLayout {
                            Text { text: "Output volume"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 12 }
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
                            background: Rectangle {
                                x: parent.leftPadding
                                y: parent.topPadding + parent.availableHeight / 2 - height / 2
                                width: parent.availableWidth
                                height: 5
                                radius: 3
                                color: ForgeTheme.raised
                                Rectangle { width: parent.width * (parent.parent.visualPosition); height: parent.height; radius: 3; color: ForgeTheme.accent }
                            }
                            handle: Rectangle {
                                x: parent.leftPadding + parent.visualPosition * (parent.availableWidth - width)
                                y: parent.topPadding + parent.availableHeight / 2 - height / 2
                                width: 16; height: 16; radius: 8
                                color: ForgeTheme.accent
                            }
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 128
                    color: ForgeTheme.surface
                    radius: 18
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16
                        Rectangle {
                            width: 72; height: 72; radius: 36
                            color: ForgeTheme.raised
                            border.color: ForgeTheme.accent
                            border.width: 2
                            Rectangle { anchors.centerIn: parent; width: 24; height: 24; radius: 12; color: ForgeTheme.accent }
                            Rectangle { x: 33; y: 5; width: 6; height: 13; radius: 3; color: ForgeTheme.muted }
                            RotationAnimator on rotation { from: 0; to: 360; duration: 14000; loops: Animation.Infinite; running: panel.visible && Desktop.player !== null && Desktop.player.playbackState === MprisPlaybackState.Playing }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackTitle || "Untitled" : "Nothing playing"; textFormat: Text.PlainText; elide: Text.ElideRight; font.bold: true; color: ForgeTheme.text; font.pixelSize: 13 }
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackArtist : "Your next soundtrack"; textFormat: Text.PlainText; elide: Text.ElideRight; color: ForgeTheme.muted; font.pixelSize: 11 }
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
                Text { text: "Power profile"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "Saver"; selected: PowerProfiles.profile === PowerProfile.PowerSaver; onClicked: PowerProfiles.profile = PowerProfile.PowerSaver }
                    ForgeButton { Layout.fillWidth: true; text: "Balanced"; selected: PowerProfiles.profile === PowerProfile.Balanced; onClicked: PowerProfiles.profile = PowerProfile.Balanced }
                    ForgeButton { Layout.fillWidth: true; text: "Performance"; enabled: PowerProfiles.hasPerformanceProfile; selected: PowerProfiles.profile === PowerProfile.Performance; onClicked: PowerProfiles.profile = PowerProfile.Performance }
                }
                Text { text: "Accent"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    Repeater {
                        model: ["sage", "ocean", "plum", "ember"]
                        ForgeButton {
                            required property string modelData
                            Layout.fillWidth: true
                            text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                            onClicked: Desktop.exec([Quickshell.env("HOME") + "/.local/bin/forge-appearance", "--preset", modelData, "--apply"])
                        }
                    }
                }
            }
        }
    }
}
