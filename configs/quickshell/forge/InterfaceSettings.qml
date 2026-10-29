import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property bool busy: false
    property var queued: ({})
    readonly property bool animationsActive: preview.signalRunning || meter.animating
    signal applyRequested(var patch)
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: ForgeTheme.gap(16)
    function queue(patch) { queued = Object.assign({}, queued, patch); save.restart() }
    Timer {
        id: save
        interval: 180
        onTriggered: {
            if (root.busy) { restart(); return }
            const patch = root.queued
            root.queued = ({})
            if (Object.keys(patch).length) root.applyRequested(patch)
        }
    }
    Text { text: "02 / SIGNAL LAB"; color: ForgeTheme.cyan; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11); font.letterSpacing: 1 }
    ForgeFrame {
        id: preview
        Layout.fillWidth: true
        implicitHeight: ForgeTheme.px(106)
        color: ForgeTheme.surface
        RowLayout {
            anchors.fill: parent
            anchors.margins: Math.min(ForgeTheme.gap(20), preview.height / 5)
            spacing: ForgeTheme.gap(16)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: ForgeTheme.gap(5)
                Text { Layout.fillWidth: true; text: "SIGNAL / ONLINE_"; elide: Text.ElideRight; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(22); font.bold: true; font.italic: true }
                Text { Layout.fillWidth: true; elide: Text.ElideRight; text: "YOUR INTERFACE. YOUR FREQUENCY."; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(9) }
            }
            ForgeSignal { id: meter; Layout.alignment: Qt.AlignVCenter; visible: root.width > ForgeTheme.px(420) }
            ForgeButton { text: "REPLAY"; onClicked: preview.enter() }
        }
    }
    Flow {
        Layout.fillWidth: true
        spacing: ForgeTheme.gap(8)
        Repeater {
            model: [
                { label: "GHOST GLASS", patch: { motion: true, effects: true, panelOpacity: 0.86, jaggedness: 1.2, spacing: 1.3, speed: 0.9, intensity: 0.35, ambient: true, scanlines: false } },
                { label: "BALANCED", patch: { motion: true, effects: true, scale: 1, textScale: 1, spacing: 1.2, jaggedness: 1.4, speed: 1, intensity: 0.65, ambient: true, scanlines: true } },
                { label: "KINETIC", patch: { motion: true, effects: true, jaggedness: 1.8, speed: 1.25, intensity: 1, ambient: true, scanlines: true } },
                { label: "SPACIOUS", patch: { scale: 1.1, textScale: 1.05, spacing: 1.45, jaggedness: 1.6 } },
                { label: "COMPACT", patch: { scale: 0.9, textScale: 1, spacing: 0.85, jaggedness: 1 } },
                { label: "QUIET", patch: { motion: false, effects: false, ambient: false, scanlines: false } }
            ]
            ForgeButton { required property var modelData; text: modelData.label; onClicked: root.queue(modelData.patch) }
        }
    }
    Flow {
        Layout.fillWidth: true
        spacing: ForgeTheme.gap(8)
        Repeater {
            model: [{ key: "motion", label: "MOTION" }, { key: "effects", label: "SIGNAL FX" }, { key: "ambient", label: "TRACERS" }, { key: "scanlines", label: "SCANLINES" }]
            ForgeButton {
                required property var modelData
                text: modelData.label + (ForgeTheme.interfaceValues[modelData.key] ? " / ON" : " / OFF")
                selected: ForgeTheme.interfaceValues[modelData.key]
                onClicked: { const patch = {}; patch[modelData.key] = !ForgeTheme.interfaceValues[modelData.key]; root.queue(patch) }
            }
        }
    }
    Repeater {
        model: [
            { key: "panelOpacity", label: "GLASS OPACITY", low: 0.7, high: 1, step: 0.05 },
            { key: "scale", label: "UI SCALE", low: 0.75, high: 1.75, step: 0.05 },
            { key: "textScale", label: "TEXT SIZE", low: 0.85, high: 1.25, step: 0.05 },
            { key: "spacing", label: "SPACE & DENSITY", low: 0.75, high: 1.6, step: 0.05 },
            { key: "jaggedness", label: "EDGE CUTS", low: 0, high: 2, step: 0.1 },
            { key: "speed", label: "ANIMATION SPEED", low: 0.5, high: 2, step: 0.1 },
            { key: "intensity", label: "SIGNAL INTENSITY", low: 0, high: 1, step: 0.05 }
        ]
        ColumnLayout {
            required property var modelData
            Layout.fillWidth: true
            spacing: ForgeTheme.gap(6)
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: modelData.label; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10) }
                Text { text: Number(adjust.value).toFixed(2) + "×"; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(11) }
            }
            ForgeSlider {
                id: adjust
                Layout.fillWidth: true
                from: modelData.low; to: modelData.high; stepSize: modelData.step
                value: ForgeTheme.interfaceValues[modelData.key]
                Accessible.name: modelData.label
                function commit() { const patch = {}; patch[modelData.key] = Math.round(value * 100) / 100; root.queue(patch) }
                onMoved: if (!pressed) commit()
                onPressedChanged: if (!pressed) commit()
            }
        }
    }
    Text { Layout.fillWidth: true; text: "Scale, text and spacing change independently. QUIET stops motion and signal effects. Ambient animations stop while panels are hidden."; wrapMode: Text.WordWrap; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(10); lineHeight: 1.5 }
}
