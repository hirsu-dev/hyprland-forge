pragma Singleton
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import Quickshell.Services.Mpris
import Quickshell.Services.UPower
import QtQuick

Singleton {
    id: root
    property bool controlsOpen: false
    property bool launcherOpen: false
    property var panelScreen: Quickshell.screens.find(s => s.name.startsWith("HDMI")) || Quickshell.screens[0] || null
    readonly property var player: Mpris.players.values.find(p => p.playbackState === MprisPlaybackState.Playing) || Mpris.players.values[0] || null
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property int volume: sink && sink.audio ? Math.round(sink.audio.volume * 100) : 0
    readonly property bool muted: sink && sink.audio ? sink.audio.muted : false
    readonly property string battery: UPower.displayDevice.ready ? Math.round(UPower.displayDevice.percentage * 100) + "%" : "AC"
    readonly property string time: Qt.formatDateTime(clock.date, "hh:mm")
    readonly property string date: Qt.formatDateTime(clock.date, "dddd, MMMM d")
    PwObjectTracker { objects: root.sink ? [root.sink] : [] }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    function exec(command) { Quickshell.execDetached(command) }
    function workspace(id) { exec(["hyprctl", "dispatch", "hl.dsp.focus({ workspace = " + Number(id) + " })"]) }
    function toggleControls(screen) {
        panelScreen = screen || panelScreen
        launcherOpen = false
        controlsOpen = !controlsOpen
    }
    function toggleLauncher(screen) {
        panelScreen = screen || panelScreen
        controlsOpen = false
        launcherOpen = !launcherOpen
    }
    function closePanels() { controlsOpen = false; launcherOpen = false }
    IpcHandler {
        target: "forge"
        function launcher(): void { root.toggleLauncher(null) }
        function controls(): void { root.toggleControls(null) }
        function close(): void { root.closePanels() }
    }
}
