import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ForgePanel {
    id: panel
    screen: Desktop.panelScreen
    opened: Desktop.settingsOpen
    implicitWidth: Math.min(ForgeTheme.px(1040), screen ? screen.width - ForgeTheme.gap(32) : ForgeTheme.px(1040))
    implicitHeight: ForgeTheme.panelHeight(screen, 800)
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    readonly property int page: Desktop.settingsPage
    readonly property bool compact: width < ForgeTheme.px(900) || height < ForgeTheme.px(620)
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
    readonly property string displayResolution: output ? output.mode.split("@")[0] : "preferred"
    readonly property var displayResolutions: [...new Set(displayModes.map(mode => mode.split("@")[0]))]
    readonly property var refreshModes: displayModes.filter(mode => mode.split("@")[0] === displayResolution)
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
    function resolution(value) {
        const choices = displayModes.filter(mode => mode.split("@")[0] === value)
        if (!choices.length) return
        const rate = Number(output.mode.split("@")[1])
        const selected = choices.reduce((best, mode) => {
            const next = Number(mode.split("@")[1])
            const previous = Number(best.split("@")[1])
            return Number.isFinite(rate) ? Math.abs(next - rate) < Math.abs(previous - rate) ? mode : best : next > previous ? mode : best
        })
        update("mode", selected)
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
    onOpenedChanged: if (opened) { Qt.callLater(() => content.forceActiveFocus()); run("--query") }
    IpcHandler {
        target: "forgeInterface"
        function status(): string { return JSON.stringify({ values: ForgeTheme.interfaceValues, open: panel.visible, width: panel.width, height: panel.height, compact: panel.compact, viewportWidth: settingsScroll.availableWidth, viewportHeight: settingsScroll.availableHeight, animationsActive: interfaceControls.animationsActive }) }
    }
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
        font.pixelSize: ForgeTheme.fontSize(11)
        wrapMode: Text.WordWrap
    }
    component Choice: ComboBox {
        id: choice
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: ForgeTheme.px(38)
        popup.popupType: Popup.Item
        popup.modal: true
        popup.dim: false
        popup.height: Math.min(ForgeTheme.px(300), Math.max(ForgeTheme.px(80), panel.height - ForgeTheme.px(80)), popup.contentItem.implicitHeight + popup.topPadding + popup.bottomPadding)
        palette.button: ForgeTheme.surface
        palette.buttonText: ForgeTheme.text
        palette.base: ForgeTheme.surface
        palette.text: ForgeTheme.text
        palette.highlight: ForgeTheme.accent
        palette.highlightedText: ForgeTheme.accentText
        font.family: ForgeTheme.font
        font.pixelSize: ForgeTheme.fontSize(12)
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
        managedProgress: true
        progress: panel.reveal
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: Desktop.closePanels()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Math.min(ForgeTheme.gap(26), panel.height / 16)
            spacing: Math.min(ForgeTheme.gap(18), panel.height / 32)
            RowLayout {
                Layout.fillWidth: true
                visible: panel.height >= ForgeTheme.px(320)
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: ForgeTheme.gap(4)
                    Text { visible: !panel.compact; text: "FORGE / SYSTEM CONFIGURATION"; color: ForgeTheme.danger; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); font.letterSpacing: 1.5 }
                    Text { Layout.fillWidth: true; elide: Text.ElideRight; text: "CONTROL YOUR RIG_"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.italic: true; font.pixelSize: ForgeTheme.fontSize(panel.compact ? 20 : 28) }
                }
                Item { Layout.fillWidth: true }
                ForgeButton { text: "ESC / CLOSE"; onClicked: Desktop.closePanels() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
            RowLayout {
                visible: panel.compact
                Layout.fillWidth: true
                Choice {
                    model: ["01 / WORKSPACE", "02 / INTERFACE", "03 / TASKBAR"]
                    currentIndex: panel.page
                    onActivated: index => Desktop.settingsPage = index
                }
                ForgeButton { visible: panel.height < ForgeTheme.px(320); text: "×"; implicitWidth: ForgeTheme.px(34); implicitHeight: ForgeTheme.px(32); onClicked: Desktop.closePanels() }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: ForgeTheme.gap(22)
                ColumnLayout {
                    visible: !panel.compact
                    Layout.preferredWidth: ForgeTheme.px(152)
                    Layout.fillHeight: true
                    spacing: ForgeTheme.gap(8)
                    Caption { text: "LOCAL / CONFIG"; color: ForgeTheme.cyan; font.pixelSize: ForgeTheme.fontSize(10) }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "01  WORKSPACE"; selected: panel.page === 0; onClicked: Desktop.settingsPage = 0 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "02  INTERFACE"; selected: panel.page === 1; onClicked: Desktop.settingsPage = 1 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "03  TASKBAR"; selected: panel.page === 2; onClicked: Desktop.settingsPage = 2 }
                    ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "04  SYSTEM DECK"; onClicked: Desktop.openHub("customize") }
                    Item { Layout.fillHeight: true }
                    Caption { Layout.fillWidth: true; text: "HYPRLAND / ARCH\n\nEXTERNAL FIRST\nDUAL LAYOUT\nLOCAL PREFERENCES"; font.pixelSize: ForgeTheme.fontSize(9); lineHeight: 1.5 }
                    Rectangle { Layout.fillWidth: true; height: 2; color: ForgeTheme.danger }
                }
                Rectangle { visible: !panel.compact; Layout.fillHeight: true; width: 1; color: ForgeTheme.line }
                ScrollView {
                    id: settingsScroll
                    objectName: "settingsScroll"
                    Layout.minimumWidth: 0
                    Layout.minimumHeight: 0
                    contentWidth: availableWidth
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ColumnLayout {
                        width: settingsScroll.availableWidth - 14
                        spacing: ForgeTheme.gap(16)
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: panel.page === 0
                            spacing: ForgeTheme.gap(14)
                            Caption { text: "01 / WINDOW BEHAVIOR"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            RowLayout {
                                Layout.fillWidth: true
                                enabled: panel.editable && panel.draft !== null
                                ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "WINDOWS / SNAP"; selected: panel.draft && panel.draft.tiling === "windows"; onClicked: panel.choose("tiling", "windows") }
                                ForgeButton { Layout.fillWidth: true; implicitHeight: ForgeTheme.px(44); text: "CAELESTIA / TILE"; selected: panel.draft && panel.draft.tiling === "caelestia"; onClicked: panel.choose("tiling", "caelestia") }
                            }
                            Caption {
                                Layout.fillWidth: true
                                text: panel.draft && panel.draft.tiling === "windows" ? "Floating windows. Super + Left/Right snaps; Up maximizes; Down restores. Super + Ctrl + Home/Page Up/End/Page Down snaps to corners." : "Automatic dwindle tiles. Super + arrows focuses a window; Super + Shift + arrows moves it. Super + V toggles floating."
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                            Caption { text: "02 / DISPLAY ROUTING"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            Flow {
                                Layout.fillWidth: true
                                spacing: ForgeTheme.gap(8)
                                Repeater {
                                    model: panel.draft ? panel.draft.outputs : []
                                    ForgeButton {
                                        required property var modelData
                                        required property int index
                                        text: modelData.name + (panel.draft.primary === modelData.name ? " / MAIN" : "")
                                        selected: panel.selected === index
                                        implicitHeight: ForgeTheme.px(42)
                                        onClicked: panel.selected = index
                                    }
                                }
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: panel.compact ? 1 : 2
                                columnSpacing: ForgeTheme.gap(18)
                                rowSpacing: ForgeTheme.gap(12)
                                enabled: panel.editable && panel.output !== null
                                Caption { text: "DISPLAY STATE" }
                                RowLayout {
                                    ForgeButton { text: panel.output && panel.output.enabled ? "ENABLED" : "DISABLED"; selected: panel.output && panel.output.enabled; onClicked: panel.update("enabled", !panel.output.enabled) }
                                    ForgeButton { text: "MAIN DISPLAY"; selected: panel.output && panel.draft.primary === panel.output.name; onClicked: { panel.update("enabled", true); panel.choose("primary", panel.output.name) } }
                                }
                                Caption { text: "RESOLUTION" }
                                Choice { objectName: "displayResolution"; model: panel.displayResolutions; displayText: currentText === "preferred" ? "Automatic / preferred" : currentText; currentIndex: Math.max(0, panel.displayResolutions.indexOf(panel.displayResolution)); onActivated: index => panel.resolution(panel.displayResolutions[index]) }
                                Caption { text: "REFRESH RATE" }
                                Choice {
                                    id: refreshChoice
                                    objectName: "displayRefresh"
                                    model: panel.refreshModes
                                    displayText: currentText === "preferred" ? "Automatic / preferred" : currentText.split("@")[1] + " Hz"
                                    currentIndex: panel.output ? Math.max(0, panel.refreshModes.indexOf(panel.output.mode)) : 0
                                    delegate: ItemDelegate {
                                        required property string modelData
                                        required property int index
                                        width: ListView.view.width
                                        text: modelData === "preferred" ? "Automatic / preferred" : modelData.split("@")[1] + " Hz"
                                        highlighted: index === refreshChoice.highlightedIndex
                                    }
                                    onActivated: index => panel.update("mode", panel.refreshModes[index])
                                }
                                Caption { text: "SCALE FACTOR" }
                                Field { id: scaleField; text: panel.output ? String(panel.output.scale) : "1"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "ORIENTATION" }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: ForgeTheme.gap(6)
                                    Repeater {
                                        model: ["LANDSCAPE", "PORTRAIT / 90°", "FLIPPED / 180°", "PORTRAIT / 270°"]
                                        ForgeButton {
                                            required property string modelData
                                            required property int index
                                            objectName: "displayOrientation" + index
                                            text: modelData
                                            selected: panel.output !== null && panel.output.rotation === index
                                            onClicked: panel.update("rotation", index)
                                        }
                                    }
                                }
                                Caption { text: "POSITION / X" }
                                Field { id: xField; text: panel.output ? String(panel.output.x) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "POSITION / Y" }
                                Field { id: yField; text: panel.output ? String(panel.output.y) : "0"; inputMethodHints: Qt.ImhFormattedNumbersOnly; onEditingFinished: panel.saveFields() }
                                Caption { text: "VARIABLE REFRESH" }
                                Choice { model: ["Off", "On", "Fullscreen only"]; currentIndex: panel.output ? panel.output.vrr : 0; onActivated: index => panel.update("vrr", index) }
                            }
                            Caption { Layout.fillWidth: true; text: "Choose a resolution to see its supported refresh rates. Select orientation, then Preview and Keep. Changes revert after 20 seconds unless confirmed. X/Y uses logical pixels after scaling and rotation."; lineHeight: 1.4 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: panel.page === 1
                            spacing: ForgeTheme.gap(18)
                            InterfaceSettings { id: interfaceControls; busy: appearanceProcess.running; onApplyRequested: patch => panel.appearance("--interface", JSON.stringify(patch)) }
                            Caption { text: "01 / COLOR FREQUENCY"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
                            Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: "GHOSTWIRE_"; elide: Text.ElideRight; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.italic: true; font.bold: true; font.pixelSize: ForgeTheme.fontSize(36) }
                            Caption { Layout.fillWidth: true; text: "Smoky glass. Cut metal edges. A quieter signal over your wallpaper."; lineHeight: 1.5 }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: panel.compact ? 1 : 2
                                rowSpacing: ForgeTheme.gap(10); columnSpacing: ForgeTheme.gap(10)
                                enabled: !appearanceProcess.running
                                Repeater {
                                    model: [{ name: "ghostwire", color: "#b4d9de", base: "#10191f" }, { name: "overdrive", color: "#fcee0a", base: "#100d16" }, { name: "redline", color: "#ff4d61", base: "#100d16" }, { name: "icewire", color: "#74f7ef", base: "#100d16" }, { name: "monolith", color: "#e9e1ec", base: "#100d16" }]
                                    ThemeCard {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        preview: modelData
                                        onClicked: panel.appearance("--preset", modelData.name)
                                    }
                                }
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
                        }
                        TaskbarSettings { Layout.fillWidth: true; visible: panel.page === 2 }
                    }
                }
            }
            Caption { Layout.fillWidth: true; visible: panel.error !== "" || panel.notice !== ""; text: panel.error || panel.notice; color: panel.error ? ForgeTheme.danger : ForgeTheme.cyan }
            Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
            RowLayout {
                Layout.fillWidth: true
                Caption { visible: !panel.compact || panel.pending !== null; Layout.fillWidth: true; text: panel.pending ? "REVERTING IN " + panel.seconds + "s / KEEP THESE SETTINGS?" : process.running || appearanceProcess.running ? "SAVING / WAIT…" : panel.page === 0 ? "SUPER + I / WORKSPACE CONFIGURATION" : panel.page === 1 ? "INTERFACE / SAVED LOCALLY" : "TASKBAR / SAVED LOCALLY"; color: panel.pending ? ForgeTheme.danger : ForgeTheme.muted; font.pixelSize: ForgeTheme.fontSize(10) }
                ForgeButton { visible: !panel.pending && panel.page === 0; text: "REFRESH"; enabled: !process.running; onClicked: panel.run("--query") }
                ForgeButton { objectName: "previewDisplays"; visible: !panel.pending && panel.page === 0; text: "PREVIEW →"; selected: true; enabled: panel.editable && panel.draft !== null; onClicked: { panel.saveFields(); panel.run("--set", JSON.stringify(panel.draft)) } }
                ForgeButton { visible: panel.pending !== null; text: "REVERT"; danger: true; enabled: !process.running; onClicked: panel.run("--revert", panel.pending.id) }
                ForgeButton { objectName: "keepDisplays"; visible: panel.pending !== null; text: "KEEP"; selected: true; enabled: !process.running && panel.seconds > 0; onClicked: panel.run("--confirm", panel.pending.id) }
            }
        }
    }
}
