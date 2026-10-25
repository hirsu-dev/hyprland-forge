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
    margins { top: ForgeTheme.px(56) + ForgeTheme.gap(8); right: ForgeTheme.gap(12) }
    implicitWidth: Math.min(ForgeTheme.px(430), screen ? screen.width - ForgeTheme.gap(24) : ForgeTheme.px(430))
    implicitHeight: ForgeTheme.panelHeight(screen, 830)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    onVisibleChanged: if (visible) { content.forceActiveFocus(); content.enter() }
    component Caption: Text {
        color: ForgeTheme.muted
        font.family: ForgeTheme.font
        font.pixelSize: ForgeTheme.fontSize(10)
        font.letterSpacing: 1
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ScrollView {
            id: controlScroll
            contentWidth: availableWidth
            anchors.fill: parent
            anchors.margins: ForgeTheme.gap(24)
            clip: true
            ColumnLayout {
                width: controlScroll.availableWidth
                spacing: ForgeTheme.gap(14)
                RowLayout {
                    Layout.fillWidth: true
                    Caption { text: "FORGE / CONTROL LINK"; color: ForgeTheme.danger }
                    Item { Layout.fillWidth: true }
                    ForgeButton { text: "×"; implicitWidth: ForgeTheme.px(30); implicitHeight: ForgeTheme.px(28); onClicked: Desktop.closePanels() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: Desktop.time; font.pixelSize: ForgeTheme.fontSize(46); font.bold: true; font.family: ForgeTheme.font; color: ForgeTheme.accent }
                    Item { Layout.fillWidth: true }
                    Column {
                        spacing: ForgeTheme.gap(5)
                        Caption { text: "POWER SOURCE" }
                        Text { text: Desktop.battery; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(18) }
                    }
                }
                Caption { text: Desktop.date.toUpperCase() }
                Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                ForgeButton { Layout.fillWidth: true; text: "SYSTEM CONFIGURATION  ↗"; onClicked: Desktop.toggleSettings() }
                RowLayout {
                    Layout.fillWidth: true
                    ForgeButton { Layout.fillWidth: true; text: "CONNECTIONS"; onClicked: Desktop.openHub("connections") }
                    ForgeButton { Layout.fillWidth: true; text: "SYSTEM DECK"; onClicked: Desktop.openHub("hardware") }
                }
                Caption { text: "01 / AUDIO SIGNAL"; color: ForgeTheme.cyan }
                ForgeFrame {
                    Layout.fillWidth: true
                    implicitHeight: ForgeTheme.px(92)
                    cut: ForgeTheme.px(9)
                    ornament: false
                    color: ForgeTheme.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: ForgeTheme.gap(14)
                        RowLayout {
                            Text { text: "OUTPUT GAIN"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11) }
                            Item { Layout.fillWidth: true }
                            ForgeButton { text: Desktop.muted ? "MUTED" : Desktop.volume + "%"; implicitHeight: ForgeTheme.px(28); onClicked: Desktop.toggleMute() }
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
                    implicitHeight: ForgeTheme.px(128)
                    cut: ForgeTheme.px(10)
                    ornament: false
                    color: ForgeTheme.surface
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: ForgeTheme.gap(16)
                        spacing: ForgeTheme.gap(16)
                        Rectangle {
                            width: ForgeTheme.px(42); height: 80
                            color: ForgeTheme.background
                            border.color: ForgeTheme.line
                            Text { anchors.centerIn: parent; text: "♫"; color: ForgeTheme.cyan; font.pixelSize: ForgeTheme.fontSize(28) }
                            Rectangle { x: 0; y: parent.height - 3; width: parent.width; height: 3; color: Desktop.player ? ForgeTheme.accent : ForgeTheme.line }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackTitle || "Untitled" : "NO ACTIVE STREAM"; textFormat: Text.PlainText; elide: Text.ElideRight; font.family: ForgeTheme.font; font.bold: true; color: ForgeTheme.text; font.pixelSize: ForgeTheme.fontSize(12) }
                            Text { Layout.fillWidth: true; text: Desktop.player ? Desktop.player.trackArtist : "Your media appears here"; textFormat: Text.PlainText; elide: Text.ElideRight; font.family: ForgeTheme.font; color: ForgeTheme.muted; font.pixelSize: ForgeTheme.fontSize(10) }
                            Row {
                                spacing: ForgeTheme.gap(5)
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
                    ForgeButton { Layout.fillWidth: true; text: "DEVICES"; onClicked: Desktop.openHub("connections") }
                    ForgeButton { Layout.fillWidth: true; text: "ALERTS " + Alerts.history.length; onClicked: Desktop.openHub("alerts") }
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
                    implicitHeight: ForgeTheme.px(82)
                    cut: ForgeTheme.px(9)
                    ornament: false
                    color: ForgeTheme.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: ForgeTheme.gap(14)
                        RowLayout {
                            Text { text: "PANEL LUMINANCE"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11) }
                            Item { Layout.fillWidth: true }
                            Text { text: Laptop.available ? Laptop.brightness + "%" : "NO BACKLIGHT"; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
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
                Caption { text: "LOCAL CONTROL / NO CLOUD REQUIRED"; font.pixelSize: ForgeTheme.fontSize(9) }
            }
        }
    }
}
