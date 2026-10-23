pragma Singleton
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import QtQuick

Singleton {
    id: root
    readonly property bool enabled: preferences.enabled
    readonly property bool primaryOnly: preferences.primaryOnly
    readonly property bool currentMonitorOnly: preferences.currentMonitorOnly
    readonly property bool showTitles: preferences.showTitles
    readonly property var pins: preferences.pins
    readonly property var windows: ToplevelManager.toplevels.values
    readonly property var activeWindow: ToplevelManager.activeToplevel
    readonly property var applications: DesktopEntries.applications.values.filter(entry => !entry.noDisplay).sort((a, b) => a.name.localeCompare(b.name))
    readonly property bool busy: writer.running
    property string error: ""
    property string lastTransaction: ""
    FileView {
        id: config
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/forge/taskbar.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        JsonAdapter {
            id: preferences
            property bool enabled: true
            property bool primaryOnly: false
            property bool currentMonitorOnly: false
            property bool showTitles: true
            property var pins: ["kitty", "thunar", "firefox"]
        }
    }
    Process {
        id: writer
        stdout: StdioCollector { id: response }
        stderr: StdioCollector { id: failure }
        onExited: (code, status) => {
            if (code !== 0) {
                try { root.error = JSON.parse(failure.text).error } catch (_) { root.error = failure.text || "Taskbar preferences could not be saved" }
            } else {
                try { root.lastTransaction = JSON.parse(response.text).transaction || "" } catch (_) { root.lastTransaction = "" }
                config.reload()
            }
        }
    }
    Timer {
        id: workspaceRefresh
        interval: 32
        onTriggered: { Hyprland.refreshMonitors(); Hyprland.refreshToplevels() }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (/workspace|focusedmon|movewindow/.test(event.name)) workspaceRefresh.restart()
        }
    }
    function identity(value) { return String(value || "").toLowerCase().replace(/\.desktop$/, "") }
    function entryFor(value) {
        const key = identity(value)
        if (!key) return null
        return DesktopEntries.applications.values.find(entry => identity(entry.id) === key || identity(entry.startupClass) === key) || null
    }
    function matches(window, entry) {
        if (!window || !entry) return false
        const key = identity(window.appId)
        return key !== "" && (key === identity(entry.id) || key === identity(entry.startupClass))
    }
    function windowsFor(entry) { return windows.filter(window => matches(window, entry)) }
    function nativeWindow(window) { return Hyprland.toplevels.values.find(item => item.wayland === window) || null }
    function onScreen(window, screen) {
        const native = nativeWindow(window)
        return native && native.monitor ? native.monitor.name === screen.name : window.screens.some(output => output.name === screen.name)
    }
    function forScreen(screen) { return windows.filter(window => !currentMonitorOnly || onScreen(window, screen)) }
    function fullscreenOn(screen) {
        const monitor = Hyprland.monitorFor(screen)
        return windows.some(window => {
            if (!window.fullscreen || !onScreen(window, screen)) return false
            const native = nativeWindow(window)
            if (monitor && monitor.activeWorkspace && native && native.workspace) return monitor.activeWorkspace.id === native.workspace.id
            return window.activated
        })
    }
    function visibleOn(screen) { return enabled && (!primaryOnly || screen === Desktop.primaryScreen) && !fullscreenOn(screen) }
    function activate(window) {
        if (!window || !windows.includes(window)) return
        Desktop.closePanels()
        window.activate()
    }
    function launch(entry) {
        if (!entry) return
        Desktop.closePanels()
        if (entry.runInTerminal) {
            Quickshell.execDetached({ command: ["kitty", "-e"].concat(entry.command), workingDirectory: entry.workingDirectory })
        } else entry.execute()
    }
    function launchOrFocus(entry) {
        if (!entry) return
        const matching = windowsFor(entry)
        if (!matching.length) { launch(entry); return }
        const index = matching.indexOf(activeWindow)
        activate(matching[(index + 1) % matching.length])
    }
    function write(option, value) {
        if (busy) return
        error = ""
        writer.command = [Quickshell.env("HOME") + "/.local/bin/forge-taskbar", option, value, "--apply"]
        writer.running = true
    }
    function change(key, value) {
        const patch = {}
        patch[key] = value
        write("--set", JSON.stringify(patch))
    }
    function pinned(entry) { return entry !== null && pins.some(pin => identity(pin) === identity(entry.id)) }
    function togglePin(entry) { if (entry) write(pinned(entry) ? "--unpin" : "--pin", entry.id) }
    IpcHandler {
        target: "forgeTasks"
        function status(): string {
            return JSON.stringify({ enabled: root.enabled, primaryOnly: root.primaryOnly, currentMonitorOnly: root.currentMonitorOnly, showTitles: root.showTitles, pins: root.pins, busy: root.busy, error: root.error, transaction: root.lastTransaction, monitorWorkspaces: Hyprland.monitors.values.map(monitor => ({ name: monitor.name, workspace: monitor.activeWorkspace ? monitor.activeWorkspace.id : null })), bars: Quickshell.screens.map(screen => ({ name: screen.name, visible: root.visibleOn(screen) })), windows: root.windows.map(window => ({ appId: window.appId, title: window.title, workspace: root.nativeWindow(window) && root.nativeWindow(window).workspace ? root.nativeWindow(window).workspace.id : null, active: window.activated, fullscreen: window.fullscreen, screens: window.screens.map(screen => screen.name) })) })
        }
        function activate(index: int): void { root.activate(root.windows[index]) }
        function configure(patch: string): void { root.write("--set", patch) }
        function pin(id: string): void { root.write("--pin", id) }
        function unpin(id: string): void { root.write("--unpin", id) }
        function undo(): void { if (root.lastTransaction) root.write("--rollback", root.lastTransaction) }
        function pinAction(id: string): void { root.launchOrFocus(root.entryFor(id)) }
    }
}
