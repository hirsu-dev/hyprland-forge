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
    margins { top: 64; right: 12 }
    implicitWidth: Math.min(430, screen ? screen.width - 24 : 430)
    implicitHeight: Math.min(830, screen ? screen.height - 90 : 830)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) { content.forceActiveFocus(); content.enter() }
    component Caption: Text {
        color: ForgeTheme.muted
        font.family: ForgeTheme.font
        font.pixelSize: 10
        font.letterSpacing: 1
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ScrollView {
            anchors.fill: parent
            anchors.margins: 24
            clip: true
            ColumnLayout {
                width: panel.width - 62
                spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    Caption { text: "FORGE / CONTROL LINK"; color: ForgeTheme.danger }
                    Item { Layout.fillWidth: true }
                    ForgeButton { text: "×"; implicitWidth: 30; implicitHeight: 28; onClicked: Desktop.closePanels() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: Desktop.time; font.pixelSize: 46; font.bold: true; font.family: ForgeTheme.font; color: ForgeTheme.accent }
                    Item { Layout.fillWidth: true }
                    Column {
                        spacing: 5
                        Caption { text: "POWER SOURCE" }
                        Text { text: Desktop.battery; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: 18 }
                    }
                }
                Caption { text: Desktop.date.toUpperCase() }
                Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                ForgeButton { Layout.fillWidth: true; text: "SYSTEM CONFIGURATION  ↗"; onClicked: Desktop.toggleSettings() }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "NETWORK"; onClicked: { Desktop.exec(["kitty", "-e", "nmtui"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "BLUETOOTH"; onClicked: { Desktop.exec(["blueman-manager"]); Desktop.closePanels() } }
                }
                Caption { text: "01 / AUDIO SIGNAL"; color: ForgeTheme.cyan }
                ForgeFrame {
                    Layout.fillWidth: true
                    implicitHeight: 92
                    cut: 9
                    ornament: false
                    color: ForgeTheme.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        RowLayout {
                            Text { text: "OUTPUT GAIN"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 11 }
                            Item { Layout.fillWidth: true }
                            ForgeButton { text: Desktop.muted ? "MUTED" : Desktop.volume + "%"; implicitHeight: 28; onClicked: Desktop.toggleMute() }
                        }
                        ForgeSlider {
                            Layout.fillWidth: true
                            from: 0; to: 1
                            value: Desktop.sink && Desktop.sink.audio ? Desktop.sink.audio.volume : 0
                            enabled: Desktop.sink !== null
                            onMoved: Desktop.setVolume(value)
                        }
                    }
                }
                ForgeFrame {
                    Layout.fillWidth: true
                    implicitHeight: 128
                    cut: 10
                    ornament: false
                    color: ForgeTheme.surface
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16
                        Rectangle {
                            width: 42; height: 80
                            color: ForgeTheme.background
                            border.color: ForgeTheme.line
                            Text { anchors.centerIn: parent; text: "♫"; color: ForgeTheme.cyan; font.pixelSize: 28 }
                            Rectangle { x: 0; y: parent.height - 3; width: parent.width; height: 3; color: Desktop.player ? ForgeTheme.accent : ForgeTheme.line }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackTitle || "Untitled" : "NO ACTIVE STREAM"; textFormat: Text.PlainText; elide: Text.ElideRight; font.family: ForgeTheme.font; font.bold: true; color: ForgeTheme.text; font.pixelSize: 12 }
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackArtist : "Your media appears here"; textFormat: Text.PlainText; elide: Text.ElideRight; font.family: ForgeTheme.font; color: ForgeTheme.muted; font.pixelSize: 10 }
                            Row {
                                spacing: 5
                                ForgeButton { text: "PREV"; enabled: Desktop.player !== null; onClicked: Desktop.media("previous") }
                                ForgeButton { text: Desktop.player && Desktop.player.playbackState === MprisPlaybackState.Playing ? "PAUSE" : "PLAY"; enabled: Desktop.player !== null; selected: true; onClicked: Desktop.media("toggle") }
                                ForgeButton { text: "NEXT"; enabled: Desktop.player !== null; onClicked: Desktop.media("next") }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "LOCK"; onClicked: { Desktop.exec(["hyprlock"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "MIXER"; onClicked: { Desktop.exec(["pavucontrol"]); Desktop.closePanels() } }
                    ForgeButton { Layout.fillWidth: true; text: "CLEAR ALERTS"; onClicked: Desktop.exec(["makoctl", "dismiss", "--all"]) }
                }
                Caption { text: "02 / POWER POLICY"; color: ForgeTheme.cyan }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "SAVER"; selected: PowerProfiles.profile === PowerProfile.PowerSaver; onClicked: PowerProfiles.profile = PowerProfile.PowerSaver }
                    ForgeButton { Layout.fillWidth: true; text: "BALANCED"; selected: PowerProfiles.profile === PowerProfile.Balanced; onClicked: PowerProfiles.profile = PowerProfile.Balanced }
                    ForgeButton { Layout.fillWidth: true; text: "BOOST"; enabled: PowerProfiles.hasPerformanceProfile; selected: PowerProfiles.profile === PowerProfile.Performance; onClicked: PowerProfiles.profile = PowerProfile.Performance }
                }
                ForgeFrame {
                    Layout.fillWidth: true
                    implicitHeight: 82
                    cut: 9
                    ornament: false
                    color: ForgeTheme.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        RowLayout {
                            Text { text: "PANEL LUMINANCE"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 11 }
                            Item { Layout.fillWidth: true }
                            Text { text: Laptop.available ? Laptop.brightness + "%" : "NO BACKLIGHT"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 10 }
                        }
                        ForgeSlider {
                            Layout.fillWidth: true
                            from: 2; to: 100
                            value: Laptop.brightness
                            enabled: Laptop.available
                            onMoved: Laptop.setBrightness(value)
                        }
                    }
                }
                Caption { text: "03 / INTERFACE SIGNAL"; color: ForgeTheme.cyan }
                RowLayout {
                    Layout.fillWidth: true
                    Repeater {
                        model: ["overdrive", "redline", "icewire", "monolith"]
                        ForgeButton {
                            required property string modelData
                            Layout.fillWidth: true
                            text: modelData.toUpperCase()
                            onClicked: Desktop.exec([Quickshell.env("HOME") + "/.local/bin/forge-appearance", "--preset", modelData, "--apply"])
                        }
                    }
                }
                Caption { text: "LOCAL CONTROL / NO CLOUD REQUIRED"; font.pixelSize: 9 }
            }
        }
    }
}
