import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

PanelWindow {
    id: panel
    screen: Desktop.panelScreen
    visible: Desktop.settingsOpen
    implicitWidth: Math.min(820, screen ? screen.width - 32 : 820)
    implicitHeight: Math.min(750, screen ? screen.height - 90 : 750)
    exclusionMode: ExclusionMode.Ignore
    focusable: true
    color: "transparent"
    property var draft: null
    property var hardware: []
    property var pending: null
    property int selected: 0
    property int seconds: 0
    property string error: ""
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
                selected = Math.min(selected, draft.outputs.length - 1)
            } else if (operation === "--set") {
                pending = result
            } else {
                pending = null
                Qt.callLater(() => run("--query"))
            }
            seconds = pending ? Math.max(0, Math.ceil(pending.deadline - Date.now() / 1000)) : 0
        } catch (_) { error = "Invalid response from desktop settings" }
    }
    onVisibleChanged: if (visible) { content.forceActiveFocus(); run("--query") }
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
        font.pixelSize: 12
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
    }
    component Field: TextField {
        Layout.fillWidth: true
        color: ForgeTheme.text
        selectByMouse: true
        font.family: ForgeTheme.font
        background: Rectangle { radius: 8; color: ForgeTheme.surface; border.color: ForgeTheme.line }
    }
    Rectangle {
        id: content
        anchors.fill: parent
        radius: 24
        color: ForgeTheme.background
        border.color: ForgeTheme.line
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Desktop & displays"; color: ForgeTheme.text; font.family: ForgeTheme.font; font.pixelSize: 24 }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "×"; onClicked: Desktop.closePanels() }
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ColumnLayout {
                    width: panel.width - 62
                    spacing: 14
                    Caption { text: "WINDOW LAYOUT" }
                    RowLayout {
                        Layout.fillWidth: true
                        enabled: panel.editable && panel.draft !== null
                        ForgeButton { Layout.fillWidth: true; text: "Windows snapping"; selected: panel.draft && panel.draft.tiling === "windows"; onClicked: panel.choose("tiling", "windows") }
                        ForgeButton { Layout.fillWidth: true; text: "Caelestia-style tiling"; selected: panel.draft && panel.draft.tiling === "caelestia"; onClicked: panel.choose("tiling", "caelestia") }
                    }
                    Caption {
                        Layout.fillWidth: true
                        text: panel.draft && panel.draft.tiling === "windows" ? "Floating windows. Super + Left/Right snaps; Up maximizes; Down restores. Super + Ctrl + Home/Page Up/End/Page Down snaps to corners." : "Automatic dwindle tiles. Super + arrows focuses a window; Super + Shift + arrows moves it. Super + V toggles floating."
                    }
                    Caption { text: "CONNECTED DISPLAYS" }
                    Choice {
                        model: panel.draft ? panel.draft.outputs.map(o => o.name + (o.name === panel.draft.primary ? " · main" : "")) : []
                        currentIndex: panel.selected
                        onActivated: index => panel.selected = index
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 20
                        rowSpacing: 12
                        enabled: panel.editable && panel.output !== null
                        Caption { text: "Display state" }
                        RowLayout {
                            ForgeButton { text: panel.output && panel.output.enabled ? "Enabled" : "Disabled"; selected: panel.output && panel.output.enabled; onClicked: panel.update("enabled", !panel.output.enabled) }
                            ForgeButton { text: "Main display"; selected: panel.output && panel.draft.primary === panel.output.name; onClicked: { panel.update("enabled", true); panel.choose("primary", panel.output.name) } }
                        }
                        Caption { text: "Resolution / refresh" }
                        Choice { model: panel.displayModes; currentIndex: panel.output ? Math.max(0, panel.displayModes.indexOf(panel.output.mode)) : 0; onActivated: index => panel.update("mode", panel.displayModes[index]) }
                        Caption { text: "Scale" }
                        Field { id: scaleField; text: panel.output ? String(panel.output.scale) : "1"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                        Caption { text: "Rotation" }
                        Choice { model: ["Normal", "90°", "180°", "270°"]; currentIndex: panel.output ? panel.output.rotation : 0; onActivated: index => panel.update("rotation", index) }
                        Caption { text: "Horizontal position" }
                        Field { id: xField; text: panel.output ? String(panel.output.x) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                        Caption { text: "Vertical position" }
                        Field { id: yField; text: panel.output ? String(panel.output.y) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                        Caption { text: "Variable refresh" }
                        Choice { model: ["Off", "On", "Fullscreen only"]; currentIndex: panel.output ? panel.output.vrr : 0; onActivated: index => panel.update("vrr", index) }
                    }
                    Caption { Layout.fillWidth: true; text: "Positions use logical pixels after scaling and rotation. Negative positions place a display to the left or above. Changes revert after 20 seconds unless you keep them." }
                }
            }
            Caption { Layout.fillWidth: true; visible: panel.error !== ""; text: panel.error; color: ForgeTheme.accent }
            RowLayout {
                Layout.fillWidth: true
                Caption { Layout.fillWidth: true; text: panel.pending ? "Keep these settings? Reverting in " + panel.seconds + "s" : process.running ? "Working…" : "Super + I opens desktop settings" }
                ForgeButton { visible: !panel.pending; text: "Refresh"; enabled: !process.running; onClicked: panel.run("--query") }
                ForgeButton { visible: !panel.pending; text: "Apply"; selected: true; enabled: panel.editable && panel.draft !== null; onClicked: { panel.saveFields(); panel.run("--set", JSON.stringify(panel.draft)) } }
                ForgeButton { visible: panel.pending !== null; text: "Revert"; enabled: !process.running; onClicked: panel.run("--revert", panel.pending.id) }
                ForgeButton { visible: panel.pending !== null; text: "Keep"; selected: true; enabled: !process.running && panel.seconds > 0; onClicked: panel.run("--confirm", panel.pending.id) }
            }
        }
    }
}
