pragma Singleton
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import Quickshell.Services.Mpris
import Quickshell.Services.UPower
import Quickshell.Services.SystemTray
import QtQuick

Singleton {
    id: root
    property bool controlsOpen: false
    property bool launcherOpen: false
    property bool powerOpen: false
    property bool settingsOpen: false
    property bool hubOpen: false
    property string hubPage: "alerts"
    property bool overviewOpen: false
    property bool recording: false
    property int settingsPage: 0
    property string powerAction: ""
    property string selectedScreen: ""
    readonly property var primaryScreen: Quickshell.screens.find(s => s.name === preferences.primary) || Quickshell.screens.find(s => s.name.startsWith("HDMI")) || Quickshell.screens[0] || null
    readonly property var panelScreen: Quickshell.screens.find(s => s.name === selectedScreen) || primaryScreen
    FileView {
        path: Quickshell.env("HOME") + "/.config/forge/desktop.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter { id: preferences; property string primary: "" }
    }
    readonly property var player: Mpris.players.values.find(p => p.playbackState === MprisPlaybackState.Playing) || Mpris.players.values[0] || null
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property bool micMuted: source && source.audio ? source.audio.muted : false
    readonly property int volume: sink && sink.audio ? Math.round(sink.audio.volume * 100) : 0
    readonly property bool muted: sink && sink.audio ? sink.audio.muted : false
    readonly property string battery: UPower.displayDevice.ready && UPower.displayDevice.isLaptopBattery ? Math.round(UPower.displayDevice.percentage * 100) + "%" : "AC"
    BatteryPolicy {
        available: UPower.displayDevice.ready && UPower.displayDevice.isLaptopBattery
        discharging: UPower.onBattery
        charge: UPower.displayDevice.percentage
        onWarning: (title, message, critical) => Alerts.systemNotice(title, message, critical)
    }
    readonly property string time: Qt.formatDateTime(clock.date, "hh:mm")
    readonly property string date: Qt.formatDateTime(clock.date, "dddd, MMMM d")
    PwObjectTracker { objects: [root.sink, root.source].filter(node => node !== null) }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    function exec(command) { Quickshell.execDetached(command) }
    function workspace(id) { exec(["hyprctl", "dispatch", "hl.dsp.focus({ workspace = " + Number(id) + " })"]) }
    function media(action) {
        if (!player) return
        if (action === "toggle" && player.canTogglePlaying) player.togglePlaying()
        else if (action === "next" && player.canGoNext) player.next()
        else if (action === "previous" && player.canGoPrevious) player.previous()
    }
    function setVolume(value) { if (Number.isFinite(value) && sink && sink.audio) sink.audio.volume = Math.max(0, Math.min(1, value)) }
    function toggleMute() { if (sink && sink.audio) sink.audio.muted = !sink.audio.muted }
    function toggleControls(screen) {
        hubOpen = false; overviewOpen = false
        settingsOpen = false
        if (screen) selectedScreen = screen.name
        launcherOpen = false
        powerOpen = false
        powerAction = ""
        controlsOpen = !controlsOpen
    }
    function toggleLauncher(screen) {
        hubOpen = false; overviewOpen = false
        settingsOpen = false
        if (screen) selectedScreen = screen.name
        controlsOpen = false
        powerOpen = false
        powerAction = ""
        launcherOpen = !launcherOpen
    }
    function togglePower(screen) {
        hubOpen = false; overviewOpen = false
        settingsOpen = false
        if (screen) selectedScreen = screen.name
        controlsOpen = false
        launcherOpen = false
        powerAction = ""
        powerOpen = !powerOpen
    }
    function requestPower(action) {
        if (["suspend", "reboot", "poweroff", "logout"].includes(action)) powerAction = action
    }
    function confirmPower() {
        const commands = { suspend: ["systemctl", "suspend"], reboot: ["systemctl", "reboot"], poweroff: ["systemctl", "poweroff"], logout: ["hyprshutdown"] }
        const command = commands[powerAction]
        if (!powerOpen || !command) return
        closePanels()
        exec(command)
    }
    function toggleSettings() {
        const next = !settingsOpen
        closePanels()
        settingsOpen = next
    }
    function openHub(page) { closePanels(); hubPage = page || "alerts"; hubOpen = true }
    function overview() { const next = !overviewOpen; closePanels(); overviewOpen = next }
    function closePanels() { controlsOpen = false; launcherOpen = false; powerOpen = false; settingsOpen = false; hubOpen = false; overviewOpen = false; powerAction = "" }
    IpcHandler {
        target: "forge"
        function launcher(): void { root.toggleLauncher(null) }
        function controls(): void { root.toggleControls(null) }
        function settings(): void { root.toggleSettings() }
        function appearance(): void { root.settingsPage = 1; if (!root.settingsOpen) root.toggleSettings() }
        function taskbar(): void { root.settingsPage = 2; if (!root.settingsOpen) root.toggleSettings() }
        function close(): void { root.closePanels() }
        function power(): void { root.togglePower(null) }
        function hub(page: string): void { root.openHub(page) }
        function overview(): void { root.overview() }
        function backlight(): void { Laptop.refresh() }
        function powerChoice(action: string): void { if (root.powerOpen) root.requestPower(action) }
        function brightness(percent: int): void { Laptop.setBrightness(percent) }
        function volume(value: real): void { root.setVolume(value) }
        function mute(): void { root.toggleMute() }
        function media(action: string): void { root.media(action) }
        function screen(name: string): void {
            if (Quickshell.screens.some(s => s.name === name)) root.selectedScreen = name
        }
        function status(): string {
            return JSON.stringify({ settings: root.settingsOpen, settingsPage: root.settingsPage, motion: ForgeTheme.motion, effects: ForgeTheme.effects, launcher: root.launcherOpen, controls: root.controlsOpen, power: root.powerOpen, powerAction: root.powerAction, hub: root.hubOpen, overview: root.overviewOpen, microphoneMuted: root.micMuted, screen: root.panelScreen ? root.panelScreen.name : "", screens: Quickshell.screens.length, accent: ForgeTheme.accent.toString(), trayItems: SystemTray.items.values.length, brightness: Laptop.brightness, backlight: Laptop.available, volume: root.volume, muted: root.muted, audio: root.sink !== null, track: root.player ? root.player.trackTitle : "", playing: root.player !== null && root.player.playbackState === MprisPlaybackState.Playing })
        }
    }
}
