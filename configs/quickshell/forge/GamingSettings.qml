import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var settings
    property bool busy: false
    signal save(var value)
    property bool overlay: settings.overlay
    property bool gamescope: settings.gamescope
    spacing: 10
    component Label: Text { Layout.fillWidth: true; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: 11; wrapMode: Text.Wrap; textFormat: Text.PlainText }
    RowLayout {
        ForgeButton { text: "MANGOHUD OVERLAY"; selected: root.overlay; onClicked: root.overlay = !root.overlay }
        ForgeButton { text: "GAMESCOPE"; selected: root.gamescope; onClicked: root.gamescope = !root.gamescope }
    }
    Label { text: "Gamescope is optional and can affect latency or compatibility. Leave it off for a direct Hyprland launch; use MangoHud for measured FPS and frame times." }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "GAMESCOPE RENDER SIZE" }
        TextField { id: widthField; Layout.preferredWidth: 90; text: String(root.settings.width); color: ForgeTheme.text; validator: IntValidator { bottom: 640; top: 3840 } background: Rectangle { color: ForgeTheme.surface; border.color: ForgeTheme.line } }
        Text { text: "×"; color: ForgeTheme.muted }
        TextField { id: heightField; Layout.preferredWidth: 90; text: String(root.settings.height); color: ForgeTheme.text; validator: IntValidator { bottom: 480; top: 2160 } background: Rectangle { color: ForgeTheme.surface; border.color: ForgeTheme.line } }
    }
    RowLayout {
        Label { text: "GAMESCOPE FRAME CAP" }
        ComboBox { id: cap; model: [30, 60, 90, 120, 144, 165, 240]; currentIndex: Math.max(0, model.indexOf(root.settings.fps)); palette.buttonText: ForgeTheme.text; palette.button: ForgeTheme.surface }
    }
    ForgeButton { text: "SAVE GAME LAUNCH OPTIONS"; enabled: !root.busy; onClicked: root.save({ overlay: root.overlay, gamescope: root.gamescope, width: Number(widthField.text), height: Number(heightField.text), fps: cap.currentValue }) }
    ForgeButton { text: "INSTALL STEAM + 32-BIT GAMING RUNTIMES"; onClicked: Desktop.exec(["kitty", "-e", Quickshell.env("HOME") + "/.local/bin/forge-optional", "gaming"]) }
    Label { text: "The optional runtime installer uses official Arch packages and requires [multilib]. It requests confirmation instead of changing repositories silently. For Steam games, use: ~/.local/bin/forge-game %command%" }
}
