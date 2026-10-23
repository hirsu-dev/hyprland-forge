import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.settingsOpen
    implicitWidth: Math.min(1040, screen ? screen.width - 32 : 1040)
    implicitHeight: Math.min(800, screen ? screen.height - 90 : 800)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    readonly property int page: Desktop.settingsPage
    property var draft: null
    property var hardware: []
    property var pending: null
    property int selected: 0
    property int seconds: 0
    property string error: ""
    property string notice: ""
    property string operation: ""
    readonly property var output: draft && draft.outputs[selected] ? draft.outputs[selected] : null
    readonly property var displayModes: output ? (hardware.find(m => m.name === output.name) || { modes: ["preferred"] }).modes : []
    readonly property bool editable: !process.running && !pending

    function run(action, value) {
        if (process.running) return
        operation = action
        error = ""
        process.command = [Quickshell.env("HOME") + "/.local/bin/forge-settings", action].concat(value === undefined ? [] : [value])
        process.running = true
    }
    function update(field, value) {
        if (!output) return
        const next = JSON.parse(JSON.stringify(draft))
        next.outputs[selected][field] = value
        draft = next
    }
    function choose(field, value) {
        const next = JSON.parse(JSON.stringify(draft))
        next[field] = value
        draft = next
    }
    function saveFields() {
        if (!output) return
        const next = JSON.parse(JSON.stringify(draft))
        next.outputs[selected].scale = scaleField.text.trim() === "" ? null : Number(scaleField.text)
        next.outputs[selected].x = xField.text.trim() === "" ? null : Number(xField.text)
        next.outputs[selected].y = yField.text.trim() === "" ? null : Number(yField.text)
        draft = next
    }
    function receive(code, text, errors) {
        if (code !== 0) {
            try { error = JSON.parse(errors).error } catch (_) { error = errors || "Settings could not be loaded" }
            return
        }
        try {
            const result = JSON.parse(text)
            if (operation === "--query") {
                draft = result.settings
                hardware = result.monitors
                pending = result.pending
                const outcome = result.last_result
                notice = outcome && outcome.status === "reverted-with-conflicts" ? "Preview ended. Kept your externally edited files: " + outcome.conflicts.join(", ") : outcome && outcome.status === "reverted" ? "The previous preview was reverted." : ""
                selected = Math.min(selected, draft.outputs.length - 1)
            } else if (operation === "--set") {
                pending = result
                notice = ""
            } else {
                pending = null
                Qt.callLater(() => run("--query"))
            }
            seconds = pending ? Math.max(0, Math.ceil(pending.deadline - Date.now() / 1000)) : 0
        } catch (_) { error = "Invalid response from desktop settings" }
    }
    function appearance(option, value) {
        if (appearanceProcess.running) return
        error = ""
        appearanceProcess.command = [Quickshell.env("HOME") + "/.local/bin/forge-appearance", option, value, "--apply"]
        appearanceProcess.running = true
    }
    onVisibleChanged: if (visible) { content.forceActiveFocus(); content.enter(); run("--query") }
    Process {
        id: appearanceProcess
        stderr: StdioCollector { id: appearanceFailure }
        onExited: (code, status) => { if (code !== 0) panel.error = appearanceFailure.text || "Appearance could not be saved" }
    }
    Process {
        id: process
        stdout: StdioCollector { id: response }
        stderr: StdioCollector { id: failure }
        onExited: (exitCode, exitStatus) => panel.receive(exitCode, response.text, failure.text)
    }
    Timer {
        interval: 500
        running: panel.pending !== null
        repeat: true
        onTriggered: {
            panel.seconds = Math.max(0, Math.ceil(panel.pending.deadline - Date.now() / 1000))
            if (panel.seconds === 0 && !process.running) panel.run("--query")
        }
    }
    component Caption: Text {
        color: ForgeTheme.muted
        font.family: ForgeTheme.font
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }
    component Choice: ComboBox {
        Layout.fillWidth: true
        palette.button: ForgeTheme.surface
        palette.buttonText: ForgeTheme.text
        palette.base: ForgeTheme.surface
        palette.text: ForgeTheme.text
        palette.highlight: ForgeTheme.accent
        palette.highlightedText: ForgeTheme.accentText
        font.family: ForgeTheme.font
        font.pixelSize: 12
        background: Rectangle { color: ForgeTheme.surface; border.color: parent.activeFocus ? ForgeTheme.cyan : ForgeTheme.line }
    }
    component Field: TextField {
        Layout.fillWidth: true
        color: ForgeTheme.text
        selectByMouse: true
        font.family: ForgeTheme.font
        background: Rectangle { color: ForgeTheme.surface; border.color: parent.activeFocus ? ForgeTheme.cyan : ForgeTheme.line }
    }
    ForgeFrame {
        id: content
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 26
            spacing: 18
            RowLayout {
                Layout.fillWidth: true
                Column {
                    spacing: 4
                    Text { text: "FORGE / SYSTEM CONFIGURATION"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: 10; font.letterSpacing: 1.5 }
                    Text { text: "CONTROL YOUR RIG_"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.italic: true; font.pixelSize: 28 }
                }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "ESC / CLOSE"; onClicked: Desktop.closePanels() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 22
                ColumnLayout {
                    Layout.preferredWidth: 152
                    Layout.fillHeight: true
                    spacing: 8
                    Caption { text: "LOCAL / CONFIG"; color: ForgeTheme.cyan; font.pixelSize: 10 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: 44; text: "01  WORKSPACE"; selected: panel.page === 0; onClicked: Desktop.settingsPage = 0 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: 44; text: "02  INTERFACE"; selected: panel.page === 1; onClicked: Desktop.settingsPage = 1 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: 44; text: "03  TASKBAR"; selected: panel.page === 2; onClicked: Desktop.settingsPage = 2 }
                    Item { Layout.fillHeight: true }
                    Caption { Layout.fillWidth: true; text: "HYPRLAND / ARCH\n\nEXTERNAL FIRST\nDUAL LAYOUT\nLOCAL PREFERENCES"; font.pixelSize: 9; lineHeight: 1.5 }
                    Rectangle { Layout.fillWidth: true; height: 2; color: ForgeTheme.danger }
                }
                Rectangle { Layout.fillHeight: true; width: 1; color: ForgeTheme.line }
                ScrollView {
                    id: settingsScroll
                    contentWidth: availableWidth
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ColumnLayout {
                        width: settingsScroll.availableWidth - 14
                        spacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: panel.page === 0
                            spacing: 14
                            Caption { text: "01 / WINDOW BEHAVIOR"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            RowLayout {
                                Layout.fillWidth: true
                                enabled: panel.editable && panel.draft !== null
                                ForgeButton { Layout.fillWidth: true; implicitHeight: 44; text: "WINDOWS / SNAP"; selected: panel.draft && panel.draft.tiling === "windows"; onClicked: panel.choose("tiling", "windows") }
                                ForgeButton { Layout.fillWidth: true; implicitHeight: 44; text: "CAELESTIA / TILE"; selected: panel.draft && panel.draft.tiling === "caelestia"; onClicked: panel.choose("tiling", "caelestia") }
                            }
                            Caption {
                                Layout.fillWidth: true
                                text: panel.draft && panel.draft.tiling === "windows" ? "Floating windows. Super + Left/Right snaps; Up maximizes; Down restores. Super + Ctrl + Home/Page Up/End/Page Down snaps to corners." : "Automatic dwindle tiles. Super + arrows focuses a window; Super + Shift + arrows moves it. Super + V toggles floating."
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                            Caption { text: "02 / DISPLAY ROUTING"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                Repeater {
                                    model: panel.draft ? panel.draft.outputs : []
                                    ForgeButton {
                                        required property var modelData
                                        required property int index
                                        text: modelData.name + (panel.draft.primary === modelData.name ? " / MAIN" : "")
                                        selected: panel.selected === index
                                        implicitHeight: 42
                                        onClicked: panel.selected = index
                                    }
                                }
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 18
                                rowSpacing: 12
                                enabled: panel.editable && panel.output !== null
                                Caption { text: "DISPLAY STATE" }
                                RowLayout {
                                    ForgeButton { text: panel.output && panel.output.enabled ? "ENABLED" : "DISABLED"; selected: panel.output && panel.output.enabled; onClicked: panel.update("enabled", !panel.output.enabled) }
                                    ForgeButton { text: "MAIN DISPLAY"; selected: panel.output && panel.draft.primary === panel.output.name; onClicked: { panel.update("enabled", true); panel.choose("primary", panel.output.name) } }
                                }
                                Caption { text: "MODE / REFRESH" }
                                Choice { model: panel.displayModes; currentIndex: panel.output ? Math.max(0, panel.displayModes.indexOf(panel.output.mode)) : 0; onActivated: index => panel.update("mode", panel.displayModes[index]) }
                                Caption { text: "SCALE FACTOR" }
                                Field { id: scaleField; text: panel.output ? String(panel.output.scale) : "1"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "ROTATION" }
                                Choice { model: ["Normal", "90°", "180°", "270°"]; currentIndex: panel.output ? panel.output.rotation : 0; onActivated: index => panel.update("rotation", index) }
                                Caption { text: "POSITION / X" }
                                Field { id: xField; text: panel.output ? String(panel.output.x) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "POSITION / Y" }
                                Field { id: yField; text: panel.output ? String(panel.output.y) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "VARIABLE REFRESH" }
                                Choice { model: ["Off", "On", "Fullscreen only"]; currentIndex: panel.output ? panel.output.vrr : 0; onActivated: index => panel.update("vrr", index) }
                            }
                            Caption { Layout.fillWidth: true; text: "Logical pixels after scaling and rotation. Negative X/Y places a display left or above. Preview reverts after 20 seconds unless confirmed."; lineHeight: 1.4 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: panel.page === 1
                            spacing: 18
                            Caption { text: "01 / COLOR FREQUENCY"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            Text { text: "OVERDRIVE"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.italic: true; font.bold: true; font.pixelSize: 42 }
                            Caption { Layout.fillWidth: true; text: "Sharp geometry. Redline signal. Your interface, on your terms."; lineHeight: 1.5 }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                rowSpacing: 10; columnSpacing: 10
                                enabled: !appearanceProcess.running
                                Repeater {
                                    model: [{ name: "overdrive", color: "#fcee0a" }, { name: "redline", color: "#ff4d61" }, { name: "icewire", color: "#74f7ef" }, { name: "monolith", color: "#e9e1ec" }]
                                    ForgeButton {
                                        id: themeOption
                                        required property var modelData
                                        Layout.fillWidth: true
                                        implicitHeight: 58
                                        text: modelData.name.toUpperCase()
                                        selected: ForgeTheme.accent.toString() === modelData.color
                                        onClicked: panel.appearance("--preset", modelData.name)
                                        Rectangle { x: 8; y: 15; width: 3; height: parent.height - 30; color: themeOption.modelData.color }
                                    }
                                }
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                            Caption { text: "02 / SIGNAL & ACCESSIBILITY"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            RowLayout {
                                Layout.fillWidth: true
                                Caption { Layout.fillWidth: true; text: "PANEL TRANSITIONS\nDisable for reduced motion."; lineHeight: 1.8 }
                                ForgeButton { text: ForgeTheme.motion ? "MOTION ON" : "MOTION OFF"; selected: ForgeTheme.motion; enabled: !appearanceProcess.running; onClicked: panel.appearance("--motion", ForgeTheme.motion ? "off" : "on") }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Caption { Layout.fillWidth: true; text: "SIGNAL EFFECTS\nEntry scan, never continuous flashing."; lineHeight: 1.8 }
                                ForgeButton { text: ForgeTheme.effects ? "SIGNAL" : "CLEAN"; selected: ForgeTheme.effects; enabled: !appearanceProcess.running; onClicked: panel.appearance("--effects", ForgeTheme.effects ? "off" : "on") }
                            }
                            Caption { Layout.fillWidth: true; text: "Changes save immediately. Controls, search, and display recovery remain usable with motion and effects disabled."; lineHeight: 1.6 }
                        }
                        TaskbarSettings { Layout.fillWidth: true; visible: panel.page === 2 }
                    }
                }
            }
            Caption { Layout.fillWidth: true; visible: panel.error !== "" || panel.notice !== ""; text: panel.error || panel.notice; color: panel.error ? ForgeTheme.danger : ForgeTheme.cyan }
            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
            RowLayout {
                Layout.fillWidth: true
                Caption { Layout.fillWidth: true; text: panel.pending ? "REVERTING IN " + panel.seconds + "s / KEEP THESE SETTINGS?" : process.running || appearanceProcess.running ? "SAVING / WAIT…" : panel.page === 0 ? "SUPER + I / WORKSPACE CONFIGURATION" : panel.page === 1 ? "INTERFACE / SAVED LOCALLY" : "TASKBAR / SAVED LOCALLY"; color: panel.pending ? ForgeTheme.danger : ForgeTheme.muted; font.pixelSize: 10 }
                ForgeButton { visible: !panel.pending && panel.page === 0; text: "REFRESH"; enabled: !process.running; onClicked: panel.run("--query") }
                ForgeButton { visible: !panel.pending && panel.page === 0; text: "PREVIEW →"; selected: true; enabled: panel.editable && panel.draft !== null; onClicked: { panel.saveFields(); panel.run("--set", JSON.stringify(panel.draft)) } }
                ForgeButton { visible: panel.pending !== null; text: "REVERT"; danger: true; enabled: !process.running; onClicked: panel.run("--revert", panel.pending.id) }
                ForgeButton { visible: panel.pending !== null; text: "KEEP"; selected: true; enabled: !process.running && panel.seconds > 0; onClicked: panel.run("--confirm", panel.pending.id) }
            }
        }
    }
}
