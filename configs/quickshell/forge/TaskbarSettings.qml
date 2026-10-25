import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    spacing: ForgeTheme.gap(18)
    component Caption: Text {
        color: ForgeTheme.muted
        font.family: ForgeTheme.font
        font.pixelSize: ForgeTheme.fontSize(11)
        wrapMode: Text.WordWrap
    }
    Caption { text: "01 / EXECUTION RAIL"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
    Text { text: "YOUR TASKS. YOUR RULES."; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.bold: true; font.italic: true; font.pixelSize: ForgeTheme.fontSize(24) }
    Caption { Layout.fillWidth: true; text: "Pinned launchers, real running windows, and quick access to your clipboard. Right-click an app for window and pin controls."; lineHeight: 1.5 }
    GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: ForgeTheme.gap(18); rowSpacing: ForgeTheme.gap(14)
        enabled: !Tasks.busy
        Caption { text: "TASKBAR" }
        ForgeButton { Layout.fillWidth: true; text: Tasks.enabled ? "ENABLED" : "DISABLED"; selected: Tasks.enabled; onClicked: Tasks.change("enabled", !Tasks.enabled) }
        Caption { text: "MONITORS" }
        ForgeButton { Layout.fillWidth: true; text: Tasks.primaryOnly ? "MAIN DISPLAY ONLY" : "ALL DISPLAYS"; selected: Tasks.primaryOnly; onClicked: Tasks.change("primaryOnly", !Tasks.primaryOnly) }
        Caption { text: "WINDOW SCOPE" }
        ForgeButton { Layout.fillWidth: true; text: Tasks.currentMonitorOnly ? "THIS DISPLAY" : "ALL WINDOWS"; selected: Tasks.currentMonitorOnly; onClicked: Tasks.change("currentMonitorOnly", !Tasks.currentMonitorOnly) }
        Caption { text: "WINDOW BUTTONS" }
        ForgeButton { Layout.fillWidth: true; text: Tasks.showTitles ? "ICONS + TITLES" : "ICONS ONLY"; selected: Tasks.showTitles; onClicked: Tasks.change("showTitles", !Tasks.showTitles) }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: ForgeTheme.line }
    Caption { text: "02 / PINNED APPLICATIONS"; color: ForgeTheme.cyan; font.letterSpacing: 1 }
    Flow {
        Layout.fillWidth: true
        spacing: ForgeTheme.gap(8)
        Repeater {
            model: Tasks.pins
            ForgeButton {
                required property string modelData
                readonly property var application: Tasks.entryFor(modelData)
                text: (application ? application.name : modelData) + "  ×"
                enabled: !Tasks.busy
                onClicked: Tasks.write("--unpin", modelData)
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        ComboBox {
            id: applications
            Layout.fillWidth: true
            model: Tasks.applications.map(entry => entry.name)
            enabled: !Tasks.busy
            font.family: ForgeTheme.font
            font.pixelSize: ForgeTheme.fontSize(12)
            palette.buttonText: ForgeTheme.text
            palette.text: ForgeTheme.text
            palette.base: ForgeTheme.surface
            palette.highlight: ForgeTheme.accent
            palette.highlightedText: ForgeTheme.accentText
            background: Rectangle { color: ForgeTheme.surface; border.color: applications.activeFocus ? ForgeTheme.cyan : ForgeTheme.line }
        }
        ForgeButton {
            text: "PIN APP +"
            selected: true
            enabled: !Tasks.busy && Tasks.pins.length < 12 && applications.currentIndex >= 0
            onClicked: Tasks.write("--pin", Tasks.applications[applications.currentIndex].id)
        }
    }
    Caption { Layout.fillWidth: true; text: "Click a pin above to remove it. You can also pin applications directly from launcher search with a right-click. Up to 12 pins."; lineHeight: 1.5 }
    Caption { Layout.fillWidth: true; text: "A running pin focuses its window; repeated clicks cycle that app's windows. Middle-click opens a new window. Fullscreen applications hide the taskbar automatically."; lineHeight: 1.5 }
    ForgeButton { text: "UNDO LAST CHANGE"; visible: Tasks.lastTransaction !== ""; enabled: !Tasks.busy; onClicked: Tasks.write("--rollback", Tasks.lastTransaction) }
    Caption { Layout.fillWidth: true; visible: Tasks.busy || Tasks.error !== ""; text: Tasks.busy ? "SAVING TASKBAR PREFERENCES…" : Tasks.error; color: Tasks.error ? ForgeTheme.danger : ForgeTheme.cyan }
}
