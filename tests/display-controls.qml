import Quickshell
import QtQuick
import QtTest

ShellRoot {
    Settings {
        id: settings
        TestCase {
            name: "DisplayControls"
            property string stage: "loading"
            parent: settings.contentItem
            when: settings.visible && settings.draft !== null && settings.editable
            function reveal(item) {
                const scroll = findChild(settings.contentItem, "settingsScroll").contentItem
                scroll.contentY = Math.max(0, Math.min(scroll.contentHeight - scroll.height, item.mapToItem(scroll.contentItem, 0, 0).y - 40))
                wait(100)
            }
            function select(control, value) {
                reveal(control)
                const index = control.model.indexOf(value)
                verify(index >= 0)
                control.forceActiveFocus()
                keyClick(Qt.Key_Space)
                tryCompare(control.popup, "visible", true)
                verify(control.popup.height > 0 && control.popup.height <= 300)
                keyClick(Qt.Key_Home)
                for (let i = 0; i < index; i++) keyClick(Qt.Key_Down)
                keyClick(Qt.Key_Return)
                tryCompare(control, "currentIndex", index)
            }
            function test_refresh_orientation_preview_keep() {
                wait(500)
                mouseClick(settings.contentItem, 12, 12)
                const resolution = findChild(settings.contentItem, "displayResolution")
                const refresh = findChild(settings.contentItem, "displayRefresh")
                verify(resolution !== null && refresh !== null)
                stage = "resolution"
                select(resolution, "800x600")
                compare(settings.displayResolution, "800x600")
                verify(settings.refreshModes.every(mode => mode.startsWith("800x600@")))
                select(resolution, "1280x800")
                stage = "refresh"
                select(refresh, "1280x800@59.81")
                compare(settings.output.mode, "1280x800@59.81")
                compare(settings.displayResolution, "1280x800")
                stage = "orientation"
                for (const index of [1, 2, 3, 0, 1]) {
                    const button = findChild(settings.contentItem, "displayOrientation" + index)
                    verify(button !== null)
                    reveal(button)
                    mouseClick(button, button.width / 2, button.height / 2)
                    compare(settings.output.rotation, index)
                }
                wait(500)
                grabImage(settings.contentItem).save("/tmp/forge-display-controls.png")
                stage = "preview"
                const preview = findChild(settings.contentItem, "previewDisplays")
                preview.forceActiveFocus()
                keyClick(Qt.Key_Space)
                tryVerify(() => settings.pending !== null || settings.error !== "", 8000)
                compare(settings.error, "")
                verify(settings.pending !== null)
                stage = "keep"
                const keep = findChild(settings.contentItem, "keepDisplays")
                tryVerify(() => keep.enabled)
                keep.forceActiveFocus()
                keyClick(Qt.Key_Space)
                tryVerify(() => settings.pending === null && settings.editable, 5000)
                compare(settings.error, "")
                console.log("FORGE_DISPLAY_UI_PASS")
                Qt.quit()
            }
            function cleanup() { console.log("FORGE_DISPLAY_UI_STAGE", stage, settings.error, JSON.stringify(settings.draft), JSON.stringify(settings.pending)) }
        }
    }
    Component.onCompleted: Desktop.settingsOpen = true
    Timer { interval: 25000; running: true; onTriggered: Qt.quit() }
}
