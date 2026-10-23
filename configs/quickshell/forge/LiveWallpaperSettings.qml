import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var settings
    property var projects: []
    property var assets: []
    property bool installed: false
    property bool busy: false
    property bool useLive: settings.enabled
    property bool silent: settings.silent
    property bool pauseGaming: settings.pauseOnGaming
    property string folderTarget: "project"
    signal save(var value)
    signal scan()
    spacing: 10
    onAssetsChanged: if (!assetPath.text && assets.length) assetPath.text = assets[0]
    component Label: Text { Layout.fillWidth: true; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 11; wrapMode: Text.Wrap; textFormat: Text.PlainText }
    component Field: TextField { Layout.fillWidth: true; color: ForgeTheme.text; placeholderTextColor: ForgeTheme.muted; selectByMouse: true; font.family: ForgeTheme.font; background: Rectangle { color: ForgeTheme.surface; border.color: ForgeTheme.line } }
    component Choice: ComboBox { Layout.fillWidth: true; palette.buttonText: ForgeTheme.text; palette.button: ForgeTheme.surface; palette.base: ForgeTheme.surface; palette.text: ForgeTheme.text }
    Label { text: "WALLPAPER ENGINE / LINUX COMPATIBILITY"; color: ForgeTheme.cyan; font.bold: true }
    Label { text: "Uses the community Linux renderer, not the Windows app. Requires your owned Steam assets and downloaded wallpapers. Compatibility varies; executable wallpapers are blocked. Static backgrounds remain as a fallback." }
    RowLayout {
        ForgeButton { text: "DETECT STEAM LIBRARIES"; enabled: !root.busy; onClicked: root.scan() }
        ForgeButton { text: root.installed ? "RENDERER INSTALLED" : "INSTALL RENDERER"; enabled: !root.installed; onClicked: Desktop.exec(["kitty", "-e", Quickshell.env("HOME") + "/.local/bin/forge-optional", "wallpaper"]) }
    }
    Choice { id: choices; model: root.projects.map(item => item.title + " / " + item.type); onActivated: projectPath.text = root.projects[currentIndex].path }
    Label { visible: root.projects.length === 0; text: "No downloaded Linux Steam wallpapers detected yet. Download your owned content through Steam, or choose the existing assets and project folders on a mounted library." }
    RowLayout {
        Layout.fillWidth: true
        Field { id: projectPath; text: root.settings.project; placeholderText: "Wallpaper folder containing project.json" }
        ForgeButton { text: "FOLDER"; onClicked: { root.folderTarget = "project"; picker.open() } }
    }
    RowLayout {
        Layout.fillWidth: true
        Field { id: assetPath; text: root.settings.assets; placeholderText: "Wallpaper Engine assets folder" }
        ForgeButton { text: "FOLDER"; onClicked: { root.folderTarget = "assets"; picker.open() } }
    }
    Choice { id: output; model: ["primary"].concat(Quickshell.screens.map(screen => screen.name)); currentIndex: Math.max(0, model.indexOf(root.settings.output)) }
    RowLayout {
        Label { text: "BACKGROUND FPS CAP" }
        Choice { id: cap; model: [15, 24, 30, 60]; currentIndex: Math.max(0, model.indexOf(root.settings.fps)) }
    }
    Flow {
        Layout.fillWidth: true; spacing: 6
        ForgeButton { text: "LIVE WALLPAPER"; selected: root.useLive; enabled: root.installed; onClicked: root.useLive = !root.useLive }
        ForgeButton { text: "MUTE + NO AUDIO PROCESSING"; selected: root.silent; onClicked: root.silent = !root.silent }
        ForgeButton { text: "PAUSE WHILE GAMING"; selected: root.pauseGaming; onClicked: root.pauseGaming = !root.pauseGaming }
    }
    ForgeButton {
        text: "SAVE LIVE WALLPAPER"; enabled: !root.busy
        onClicked: root.save({ enabled: root.useLive, project: projectPath.text, assets: assetPath.text, output: output.currentText, fps: cap.currentValue, silent: root.silent, pauseOnGaming: root.pauseGaming })
    }
    Label { text: "Muted at 30 FPS by default. The renderer pauses for fullscreen apps. With Pause While Gaming enabled, Forge unloads it during its gaming preset or a tracked game, then restores it afterward. Custom or mounted Steam libraries can be selected manually." }
    FolderDialog {
        id: picker
        title: root.folderTarget === "project" ? "Choose downloaded wallpaper folder" : "Choose Wallpaper Engine assets folder"
        onAccepted: { const path = decodeURIComponent(selectedFolder.toString().replace(/^file:\/\//, "")); if (root.folderTarget === "project") projectPath.text = path; else assetPath.text = path }
    }
}
