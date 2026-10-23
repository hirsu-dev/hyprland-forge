import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import QtQuick.Dialogs
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.hubOpen
    implicitWidth: Math.min(1050, screen ? screen.width - 32 : 1050)
    implicitHeight: Math.min(790, screen ? screen.height - 100 : 790)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    property var preferences: ({ bindings: {}, wallpapers: {}, profiles: {}, sensitivity: 0, naturalScroll: true, tapToClick: true, disableWhileTyping: true, gaming: false })
    property var wifi: ({ networks: [], connections: [], wifi: false })
    property var bluetooth: ({ devices: [], powered: false })
    property var statistics: ({})
    property var previousStatistics: null
    property int cpuPercent: 0
    property var backupList: []
    property var updateList: []
    property var wallpaperProjects: []
    property var wallpaperAssets: []
    property bool wallpaperRenderer: false
    property var pending: null
    property int countdown: 0
    property string logs: ""
    property string error: ""
    property string message: ""
    property string operation: ""
    property string requestText: ""
    property bool updateArmed: false
    property string restoreArmed: ""
    property string captureStatus: ""
    property bool recordingCapture: false
    property var shortcutDraft: ({})
    property var inputDraft: ({ sensitivity: 0, naturalScroll: true, tapToClick: true, disableWhileTyping: true })
    readonly property var audioNodes: Pipewire.nodes.values.filter(node => !node.isStream && node.audio !== null)
    readonly property var outputs: audioNodes.filter(node => node.isSink)
    readonly property var inputs: audioNodes.filter(node => !node.isSink)
    readonly property var pages: ["alerts", "connections", "customize", "hardware", "capture", "recovery"]
    readonly property bool busy: worker.running
    Component.onCompleted: request("preferences")
    function request(action, extra) {
        if (busy) return
        operation = action; error = ""; message = ""
        requestText = JSON.stringify(Object.assign({ action: action }, extra || {})) + "\n"
        worker.stdinEnabled = true
        worker.running = true
    }
    function refresh() {
        updateArmed = false; restoreArmed = ""
        const actions = { alerts: "preferences", connections: "network", customize: "preferences", hardware: "metrics", capture: "preferences", recovery: "backups" }
        request(actions[Desktop.hubPage] || "preferences")
    }
    function receive(result) {
        if (result.error) { error = result.error; return }
        if (result.preferences) {
            preferences = result.preferences
            shortcutDraft = Object.assign({}, preferences.bindings)
            inputDraft = { sensitivity: preferences.sensitivity, naturalScroll: preferences.naturalScroll, tapToClick: preferences.tapToClick, disableWhileTyping: preferences.disableWhileTyping }
        }
        if (result.networks) wifi = result
        if (result.devices) bluetooth = result
        if (result.memoryTotal !== undefined) {
            if (previousStatistics && result.cpuTotal > previousStatistics.cpuTotal) cpuPercent = Math.round(100 * (1 - (result.cpuIdle - previousStatistics.cpuIdle) / (result.cpuTotal - previousStatistics.cpuTotal)))
            previousStatistics = result; statistics = result
        }
        if (result.backups) backupList = result.backups
        if (result.updates) updateList = result.updates
        if (result.logs !== undefined) logs = result.logs
        if (result.message) message = result.message
        if (result.wallpaperProjects) wallpaperProjects = result.wallpaperProjects
        if (result.wallpaperAssets) wallpaperAssets = result.wallpaperAssets
        if (result.wallpaperRenderer) wallpaperRenderer = result.wallpaperRenderer.installed
        if (result.pending) pending = result.pending
    }
    function draft(key, value) { const next = Object.assign({}, inputDraft); next[key] = value; inputDraft = next }
    function capture(recording) {
        if (captureWorker.running) return
        recordingCapture = recording
        captureStatus = "SELECT A REGION / CAPTURE IN PROGRESS"
        captureWorker.command = [Quickshell.env("HOME") + "/.local/bin/forge-capture", "--mode", recording && captureMode.currentIndex === 2 ? "display" : ["region", "display", "desktop"][captureMode.currentIndex], "--delay", String([0, 3, 5, 10][captureDelay.currentIndex])]
        if (recording) captureWorker.command = captureWorker.command.concat(["--record"]).concat(captureAudio.checked ? ["--audio"] : [])
        else if (annotate.checked) captureWorker.command = captureWorker.command.concat(["--annotate"])
        Desktop.closePanels()
        captureWorker.running = true
    }
    onVisibleChanged: if (visible) { content.forceActiveFocus(); content.enter(); refresh() }
    Connections { target: Desktop; function onHubPageChanged() { if (panel.visible) panel.refresh() } }
    PwObjectTracker { objects: panel.audioNodes }
    Process {
        id: worker
        command: [Quickshell.env("HOME") + "/.local/bin/forge-control"]
        onStarted: { write(panel.requestText); stdinEnabled = false; panel.requestText = "" }
        stdout: StdioCollector { id: response }
        stderr: StdioCollector { id: failure }
        onExited: (code, status) => {
            try { panel.receive(JSON.parse(response.text)) } catch (_) { panel.error = failure.text || "Control service returned an invalid response" }
        }
    }
    Process {
        id: captureWorker
        onRunningChanged: Desktop.recording = running && panel.recordingCapture
        stdout: StdioCollector { id: captureResponse }
        onExited: (code, status) => {
            try {
                const result = JSON.parse(captureResponse.text)
                panel.captureStatus = result.error || (result.cancelled ? "Capture cancelled" : "SAVED / " + result.path)
            } catch (_) { panel.captureStatus = "Capture stopped without a result" }
            Desktop.exec(["notify-send", "Forge Capture", panel.captureStatus])
        }
    }
    Process {
        id: previewWorker
        stdout: StdioCollector { id: previewResponse }
        onExited: (code, status) => {
            if (code === 0) panel.pending = null
            else panel.error = "Display preview could not be completed"
        }
    }
    Timer {
        interval: 500; running: panel.pending !== null; repeat: true
        onTriggered: {
            panel.countdown = Math.max(0, Math.ceil(panel.pending.deadline - Date.now() / 1000))
            if (panel.countdown === 0) { panel.pending = null; panel.message = "Preview expired; display watchdog restores the previous configuration." }
        }
    }
    Timer { interval: 3000; running: panel.visible && Desktop.hubPage === "hardware"; repeat: true; onTriggered: if (!panel.busy) panel.request("metrics") }
    component Label: Text { Layout.fillWidth: true; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 12 }
    component Heading: Label { color: ForgeTheme.cyan; font.pixelSize: 13; font.bold: true; topPadding: 12 }
    component Field: TextField {
        Layout.fillWidth: true
        color: ForgeTheme.text; placeholderTextColor: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 12
        selectByMouse: true
        background: Rectangle { color: ForgeTheme.surface; border.color: parent.activeFocus ? ForgeTheme.cyan : ForgeTheme.line }
    }
    component Choice: ComboBox {
        Layout.fillWidth: true
        palette.buttonText: ForgeTheme.text; palette.text: ForgeTheme.text; palette.base: ForgeTheme.surface; palette.highlight: ForgeTheme.accent; palette.highlightedText: ForgeTheme.accentText
        font.family: ForgeTheme.font; font.pixelSize: 12
        background: Rectangle { color: ForgeTheme.surface; border.color: ForgeTheme.line }
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        Keys.onEscapePressed: Desktop.closePanels()
        RowLayout {
            anchors.fill: parent; anchors.margins: 24; spacing: 20
            ColumnLayout {
                Layout.preferredWidth: 164; Layout.fillHeight: true; spacing: 10
                Label { text: "FORGE /"; color: ForgeTheme.accent; font.pixelSize: 23; font.bold: true }
                Label { text: "SYSTEM DECK"; color: ForgeTheme.muted; font.pixelSize: 10 }
                Repeater {
                    model: panel.pages
                    ForgeButton {
                        required property string modelData
                        Layout.fillWidth: true
                        text: modelData.toUpperCase()
                        selected: Desktop.hubPage === modelData
                        enabled: !panel.busy
                        onClicked: Desktop.hubPage = modelData
                    }
                }
                Item { Layout.fillHeight: true }
                ForgeButton { Layout.fillWidth: true; text: "WINDOW GRID"; onClicked: Desktop.overview() }
                ForgeButton { Layout.fillWidth: true; text: "REFRESH"; enabled: !panel.busy; onClicked: panel.refresh() }
                ForgeButton { Layout.fillWidth: true; text: "CLOSE"; onClicked: Desktop.closePanels() }
            }
            Rectangle { width: 1; Layout.fillHeight: true; color: ForgeTheme.line }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10
                Label { text: "LOCAL SYSTEM / " + Desktop.hubPage.toUpperCase(); color: ForgeTheme.accent; font.pixelSize: 22 }
                Label { visible: panel.busy || panel.error !== "" || panel.message !== ""; text: panel.busy ? "WORKING…" : panel.error || panel.message; color: panel.error ? ForgeTheme.danger : ForgeTheme.cyan }
                ScrollView {
                    id: scroll
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    ColumnLayout {
                        width: scroll.availableWidth
                        spacing: 12
                        ColumnLayout {
                            visible: Desktop.hubPage === "alerts"; Layout.fillWidth: true; spacing: 12
                            RowLayout {
                                Layout.fillWidth: true
                                ForgeButton { text: Alerts.dnd ? "DND / ON" : "DND / OFF"; selected: Alerts.dnd; onClicked: Alerts.dnd = !Alerts.dnd }
                                ForgeButton { text: "CLEAR HISTORY"; onClicked: Alerts.clear() }
                            }
                            Label { text: "Up to 80 notifications are kept in memory only. History clears when the shell exits. Expired notifications no longer offer actions."; color: ForgeTheme.muted }
                            Label { visible: Alerts.history.length === 0; text: "NO NOTIFICATIONS / SIGNAL CLEAR" }
                            Repeater { model: Alerts.history; NotificationCard { required property var modelData; Layout.fillWidth: true; entry: modelData } }
                        }
                        ColumnLayout {
                            visible: Desktop.hubPage === "connections"; Layout.fillWidth: true; spacing: 10
                            Heading { text: "01 / AUDIO DEVICES" }
                            Label { text: "OUTPUT" }
                            Choice { model: panel.outputs.map(node => node.description || node.name); currentIndex: panel.outputs.indexOf(Desktop.sink); onActivated: Pipewire.preferredDefaultAudioSink = panel.outputs[currentIndex] }
                            Label { text: "MICROPHONE" }
                            Choice { model: panel.inputs.map(node => node.description || node.name); currentIndex: panel.inputs.indexOf(Desktop.source); onActivated: Pipewire.preferredDefaultAudioSource = panel.inputs[currentIndex] }
                            ForgeButton { text: Desktop.micMuted ? "MIC MUTED" : "MUTE MICROPHONE"; selected: Desktop.micMuted; enabled: Desktop.source !== null; onClicked: if (Desktop.source && Desktop.source.audio) Desktop.source.audio.muted = !Desktop.source.audio.muted }
                            Heading { text: "02 / WI-FI" }
                            RowLayout {
                                ForgeButton { text: panel.wifi.wifi ? "RADIO / ON" : "RADIO / OFF"; enabled: !panel.busy; onClicked: panel.request("wifi-power", { enabled: !panel.wifi.wifi }) }
                                ForgeButton { text: "REFRESH NETWORKS"; enabled: !panel.busy; onClicked: panel.request("network") }
                                ForgeButton { text: "ADVANCED"; onClicked: Desktop.exec(["nm-connection-editor"]) }
                            }
                            Choice { id: networks; model: panel.wifi.networks.map(item => (item.active === "*" ? "● " : "") + item.ssid + " / " + item.signal + "% / " + item.security) }
                            Field { id: wifiPassword; placeholderText: "WPA2 password / not saved"; echoMode: TextInput.Password; maximumLength: 64 }
                            ForgeButton {
                                text: "CONNECT SELECTED NETWORK"; enabled: !panel.busy && networks.currentIndex >= 0
                                onClicked: { panel.request("wifi-connect", { bssid: panel.wifi.networks[networks.currentIndex].bssid, password: wifiPassword.text }); wifiPassword.clear() }
                            }
                            Choice { id: savedConnections; model: panel.wifi.connections.map(item => item.name + (item.device ? " / " + item.device : "")) }
                            ForgeButton { text: "ACTIVATE SAVED CONNECTION"; enabled: !panel.busy && savedConnections.currentIndex >= 0; onClicked: panel.request("connection-up", { uuid: panel.wifi.connections[savedConnections.currentIndex].uuid }) }
                            Heading { text: "03 / BLUETOOTH" }
                            RowLayout {
                                ForgeButton { text: "REFRESH DEVICES"; enabled: !panel.busy; onClicked: panel.request("bluetooth") }
                                ForgeButton { text: panel.bluetooth.powered ? "POWER / ON" : "POWER / OFF"; enabled: !panel.busy; onClicked: panel.request("bluetooth-power", { enabled: !panel.bluetooth.powered }) }
                                ForgeButton { text: "PAIR NEW DEVICE"; onClicked: Desktop.exec(["blueman-manager"]) }
                            }
                            Repeater {
                                model: panel.bluetooth.devices
                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Label { text: modelData.name + (modelData.connected ? " / CONNECTED" : " / OFFLINE") }
                                    ForgeButton { text: modelData.connected ? "DISCONNECT" : "CONNECT"; enabled: !panel.busy && modelData.paired; onClicked: panel.request(modelData.connected ? "bluetooth-disconnect" : "bluetooth-connect", { address: modelData.address }) }
                                }
                            }
                            Label { text: "Pairing and enterprise/WPA3-only Wi-Fi use the advanced tools. Device availability depends on real hardware."; color: ForgeTheme.muted }
                        }
                        ColumnLayout {
                            visible: Desktop.hubPage === "customize"; Layout.fillWidth: true; spacing: 10
                            Heading { text: "01 / POINTER & TOUCHPAD" }
                            Label { text: "POINTER SENSITIVITY / " + Number(panel.inputDraft.sensitivity).toFixed(2) }
                            ForgeSlider { Layout.fillWidth: true; from: -1; to: 1; value: panel.inputDraft.sensitivity; onMoved: panel.draft("sensitivity", Math.round(value * 100) / 100) }
                            RowLayout {
                                ForgeButton { text: "NATURAL SCROLL"; selected: panel.inputDraft.naturalScroll; onClicked: panel.draft("naturalScroll", !panel.inputDraft.naturalScroll) }
                                ForgeButton { text: "TAP TO CLICK"; selected: panel.inputDraft.tapToClick; onClicked: panel.draft("tapToClick", !panel.inputDraft.tapToClick) }
                            }
                            ForgeButton { text: "DISABLE TOUCHPAD WHILE TYPING"; selected: panel.inputDraft.disableWhileTyping; onClicked: panel.draft("disableWhileTyping", !panel.inputDraft.disableWhileTyping) }
                            Heading { text: "02 / SHORTCUTS" }
                            Repeater {
                                model: Object.keys(panel.shortcutDraft)
                                RowLayout {
                                    required property string modelData
                                    Layout.fillWidth: true
                                    Label { text: modelData.toUpperCase(); Layout.preferredWidth: 100; Layout.fillWidth: false }
                                    Field { text: panel.shortcutDraft[modelData]; onTextEdited: { const next = Object.assign({}, panel.shortcutDraft); next[modelData] = text; panel.shortcutDraft = next } }
                                }
                            }
                            ForgeButton { text: "SAVE INPUT & SHORTCUTS"; selected: true; enabled: !panel.busy; onClicked: panel.request("save", { patch: Object.assign({}, panel.inputDraft, { bindings: panel.shortcutDraft }) }) }
                            Label { text: "Use SUPER / CTRL / ALT / SHIFT + key. Reserved system shortcuts cannot be replaced."; color: ForgeTheme.muted }
                            Heading { text: "03 / WALLPAPERS" }
                            ForgeButton { text: "BROWSE IMAGES"; onClicked: wallpaperDialog.open() }
                            Choice { id: wallpaperOutput; model: ["default"].concat(Quickshell.screens.map(output => output.name)) }
                            Field { id: wallpaperPath; placeholderText: "Absolute image path / e.g. /home/forge/Pictures/background.png" }
                            Image { Layout.fillWidth: true; Layout.preferredHeight: 150; fillMode: Image.PreserveAspectFit; source: wallpaperPath.text.startsWith("/") ? "file://" + wallpaperPath.text : ""; asynchronous: true; visible: source !== "" }
                            RowLayout {
                                ForgeButton { text: "APPLY IMAGE"; enabled: !panel.busy && wallpaperPath.text !== ""; onClicked: { const next = Object.assign({}, panel.preferences.wallpapers); next[wallpaperOutput.currentText] = wallpaperPath.text; panel.request("save", { patch: { wallpapers: next } }) } }
                                ForgeButton { text: "RESET OUTPUT"; enabled: !panel.busy; onClicked: { const next = Object.assign({}, panel.preferences.wallpapers); delete next[wallpaperOutput.currentText]; panel.request("save", { patch: { wallpapers: next } }) } }
                            }
                            Heading { text: "04 / LIVE WALLPAPER" }
                            LiveWallpaperSettings {
                                Layout.fillWidth: true
                                settings: panel.preferences.liveWallpaper || { enabled: false, project: "", assets: "", output: "primary", fps: 30, silent: true, pauseOnGaming: true }
                                projects: panel.wallpaperProjects
                                assets: panel.wallpaperAssets
                                installed: panel.wallpaperRenderer
                                busy: panel.busy
                                onSave: value => panel.request("save", { patch: { liveWallpaper: value } })
                                onScan: panel.request("wallpaper-library")
                            }
                            Heading { text: "05 / DISPLAY PROFILES" }
                            Field { id: profileName; placeholderText: "Profile name / Desk, Laptop, Gaming"; maximumLength: 32 }
                            ForgeButton { text: "SAVE CURRENT DISPLAYS"; enabled: !panel.busy; onClicked: panel.request("profile-save", { name: profileName.text }) }
                            Choice { id: profiles; model: Object.keys(panel.preferences.profiles) }
                            ForgeButton { text: "PREVIEW PROFILE / 20 SECONDS"; enabled: !panel.busy && !panel.pending && profiles.currentIndex >= 0; onClicked: panel.request("profile-preview", { name: profiles.currentText }) }
                            RowLayout {
                                visible: panel.pending !== null
                                Label { text: "KEEP DISPLAY PREVIEW? " + panel.countdown + "s"; color: ForgeTheme.danger }
                                ForgeButton { text: "KEEP"; enabled: !previewWorker.running; onClicked: { previewWorker.command = [Quickshell.env("HOME") + "/.local/bin/forge-settings", "--confirm", panel.pending.id]; previewWorker.running = true } }
                                ForgeButton { text: "REVERT"; enabled: !previewWorker.running; onClicked: { previewWorker.command = [Quickshell.env("HOME") + "/.local/bin/forge-settings", "--revert", panel.pending.id]; previewWorker.running = true } }
                            }
                        }
                        ColumnLayout {
                            visible: Desktop.hubPage === "hardware"; Layout.fillWidth: true; spacing: 12
                            Heading { text: "01 / SYSTEM TELEMETRY" }
                            Label { text: "CPU / " + panel.cpuPercent + "%"; font.pixelSize: 25; color: ForgeTheme.accent }
                            Label { text: "RAM / " + ((panel.statistics.memoryUsed || 0) / 1048576).toFixed(1) + " / " + ((panel.statistics.memoryTotal || 0) / 1048576).toFixed(1) + " GiB" }
                            Label { text: panel.statistics.gpu ? panel.statistics.gpu.name + " / " + panel.statistics.gpu.usage + "% / " + panel.statistics.gpu.temperature + "°C" : "NVIDIA / NOT AVAILABLE (normal in this VM)" }
                            Repeater { model: panel.statistics.temperatures || []; Label { required property var modelData; text: modelData.name + " / " + modelData.celsius.toFixed(1) + "°C" } }
                            Repeater { model: panel.statistics.batteries || []; Label { required property var modelData; text: modelData.name + " / " + modelData.percent + "% / " + modelData.status } }
                            Heading { text: "02 / GAMING PROFILE" }
                            GamingSettings {
                                Layout.fillWidth: true
                                settings: panel.preferences.gameOptions || { overlay: false, gamescope: false, width: 1920, height: 1080, fps: 120 }
                                busy: panel.busy
                                onSave: value => panel.request("save", { patch: { gameOptions: value } })
                            }
                            ForgeButton { text: panel.preferences.gaming ? "GAMING PROFILE / ON" : "GAMING PROFILE / OFF"; selected: panel.preferences.gaming; enabled: !panel.busy; onClicked: panel.request("save", { patch: { gaming: !panel.preferences.gaming } }) }
                            Label { text: "Gaming profile disables compositor blur and animations. Launch below uses GameMode on physical hardware, NVIDIA offload when available, and an idle inhibitor for the application lifetime. GameMode is skipped in VMs. No overclocking, driver or security-mitigation changes."; color: ForgeTheme.muted }
                            Choice { id: gamingApp; model: Tasks.applications.map(entry => entry.name) }
                            ForgeButton {
                                text: "LAUNCH WITH GAMEMODE"; enabled: gamingApp.currentIndex >= 0
                                onClicked: {
                                    const entry = Tasks.applications[gamingApp.currentIndex]
                                    const command = [Quickshell.env("HOME") + "/.local/bin/forge-game"].concat(entry.command)
                                    Desktop.exec(entry.runInTerminal ? ["kitty", "-e"].concat(command) : command)
                                }
                            }
                            Label { text: "Telemetry refreshes only while this page is open. Battery, temperatures and GPU readings are unavailable when hardware does not expose them."; color: ForgeTheme.muted }
                        }
                        ColumnLayout {
                            visible: Desktop.hubPage === "capture"; Layout.fillWidth: true; spacing: 12
                            Heading { text: "CAPTURE / LOCAL FILES ONLY" }
                            Label { text: "Screenshots: ~/Pictures/Forge · Recordings: ~/Videos/Forge. Screenshots also copy to the clipboard. Recording uses a region or the focused display at 30 FPS." }
                            Label { text: "CAPTURE AREA" }
                            Choice { id: captureMode; model: ["REGION", "FOCUSED DISPLAY", "ALL DISPLAYS / SCREENSHOTS ONLY"] }
                            Label { text: "DELAY" }
                            Choice { id: captureDelay; model: ["NONE", "3 SECONDS", "5 SECONDS", "10 SECONDS"] }
                            CheckBox { id: annotate; text: "Open screenshot in Satty for annotation"; palette.windowText: ForgeTheme.text }
                            CheckBox { id: captureAudio; text: "Include audio in recording"; palette.windowText: ForgeTheme.text }
                            RowLayout {
                                ForgeButton { text: "SCREENSHOT"; enabled: !captureWorker.running; onClicked: panel.capture(false) }
                                ForgeButton { text: "START RECORDING"; enabled: !captureWorker.running; danger: true; onClicked: panel.capture(true) }
                            }
                            ForgeButton { text: "STOP RECORDING / FINALIZE FILE"; visible: captureWorker.running; danger: true; onClicked: captureWorker.signal(2) }
                            Label { text: panel.captureStatus; color: ForgeTheme.cyan }
                            ForgeButton { text: "OPEN CAPTURE FOLDER"; onClicked: Desktop.exec(["thunar", Quickshell.env("HOME") + "/Pictures/Forge"]) }
                        }
                        ColumnLayout {
                            visible: Desktop.hubPage === "recovery"; Layout.fillWidth: true; spacing: 12
                            Heading { text: "01 / SYSTEM UPDATES" }
                            Label { text: "Update previews use an isolated package database. Applying an update opens a terminal and requires your sudo password and pacman confirmation. AUR packages are not managed here."; color: ForgeTheme.muted }
                            ForgeButton { text: "CHECK OFFICIAL UPDATES"; enabled: !panel.busy; onClicked: panel.request("updates") }
                            Repeater { model: panel.updateList; Label { required property string modelData; text: modelData } }
                            ForgeButton { text: panel.updateArmed ? "CONFIRM / OPEN PACMAN UPDATE" : "UPDATE ENTIRE SYSTEM"; danger: true; enabled: !panel.busy; onClicked: { if (!panel.updateArmed) panel.updateArmed = true; else { panel.updateArmed = false; Desktop.exec(["kitty", "-e", Quickshell.env("HOME") + "/.local/bin/forge-update"]) } } }
                            Heading { text: "02 / CONFIG RECOVERY" }
                            Label { text: "Undo restores config files only, preserving conflicting external edits. It does not undo package upgrades, restore boot files, or replace a full disk backup."; color: ForgeTheme.muted }
                            Repeater {
                                model: panel.backupList
                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Label { text: (modelData.group || "installer") + " / " + modelData.id + " / " + modelData.files + " files" }
                                    ForgeButton { text: panel.restoreArmed === modelData.id ? "CONFIRM UNDO" : "UNDO"; danger: true; enabled: !panel.busy; onClicked: { if (panel.restoreArmed !== modelData.id) panel.restoreArmed = modelData.id; else { panel.restoreArmed = ""; panel.request("restore", modelData) } } }
                                }
                            }
                            Heading { text: "03 / SESSION LOGS" }
                            ForgeButton { text: "READ USER SESSION LOGS"; enabled: !panel.busy; onClicked: panel.request("logs") }
                            TextArea { Layout.fillWidth: true; visible: panel.logs !== ""; text: panel.logs; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 10; background: Rectangle { color: ForgeTheme.surface } }
                        }
                    }
                }
            }
        }
    }
    IpcHandler {
        target: "forgeHub"
        function status(): string { return JSON.stringify({ open: Desktop.hubOpen, page: Desktop.hubPage, busy: panel.busy, error: panel.error, captureRunning: captureWorker.running, notifications: Alerts.history.length, cpu: panel.cpuPercent, preferences: panel.preferences }) }
        function request(value: string): void { const parsed = JSON.parse(value); panel.request(parsed.action, parsed) }
        function stopCapture(): void { if (captureWorker.running) captureWorker.signal(2) }
        function outputs(): string { return JSON.stringify(panel.outputs.map(node => ({ id: node.id, name: node.name, active: node === Desktop.sink }))) }
        function output(id: int): void { const node = panel.outputs.find(item => item.id === id); if (node) Pipewire.preferredDefaultAudioSink = node }
    }
    FileDialog {
        id: wallpaperDialog
        title: "Choose a Forge wallpaper"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.webp *.svg)"]
        onAccepted: wallpaperPath.text = decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))
    }
}
