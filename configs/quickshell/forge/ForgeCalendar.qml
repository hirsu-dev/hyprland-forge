import Quickshell.Io
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property date today: new Date()
    property int year: today.getFullYear()
    property int month: today.getMonth()
    property string selectedDate: Qt.formatDateTime(today, "yyyy-MM-dd")
    property real monthProgress: 1
    property int direction: 1
    readonly property var cells: {
        const first = new Date(year, month, 1, 12)
        const offset = (first.getDay() + 6) % 7
        return Array.from({length: 42}, (_, index) => {
            const date = new Date(year, month, index - offset + 1, 12)
            return { day: date.getDate(), month: date.getMonth(), year: date.getFullYear(), key: Qt.formatDateTime(date, "yyyy-MM-dd"), label: Qt.formatDateTime(date, "dddd, MMMM d, yyyy") }
        })
    }
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: ForgeTheme.gap(8)
    function navigate(offset) {
        const next = new Date(year, month + offset, 1, 12)
        if (next.getFullYear() < 1900 || next.getFullYear() > 2100) return
        direction = offset < 0 ? -1 : 1
        year = next.getFullYear(); month = next.getMonth()
        if (ForgeTheme.motion) { monthProgress = 0; monthTravel.restart() }
        else monthProgress = 1
    }
    function resetToday() { today = new Date(); year = today.getFullYear(); month = today.getMonth(); selectedDate = Qt.formatDateTime(today, "yyyy-MM-dd") }
    function choose(index) {
        if (index < 0 || index >= cells.length) return
        const cell = cells[index]
        selectedDate = cell.key; year = cell.year; month = cell.month
    }
    onVisibleChanged: if (!visible) { monthTravel.stop(); monthProgress = 1 }
    Connections { target: Desktop; function onDateChanged() { root.today = new Date() } }
    Connections { target: ForgeTheme; function onMotionChanged() { if (!ForgeTheme.motion) monthTravel.complete() } }
    NumberAnimation { id: monthTravel; target: root; property: "monthProgress"; to: 1; duration: ForgeTheme.duration; easing.type: Easing.OutCubic }
    RowLayout {
        Layout.fillWidth: true
        spacing: ForgeTheme.gap(4)
        Text { Layout.fillWidth: true; text: Qt.formatDateTime(new Date(root.year, root.month, 1, 12), "MMMM yyyy").toUpperCase(); elide: Text.ElideRight; color: ForgeTheme.accent; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(12) }
        ForgeButton { text: "‹"; implicitWidth: ForgeTheme.px(30); Accessible.name: "Previous month"; onClicked: root.navigate(-1) }
        ForgeButton { text: "TODAY"; implicitWidth: ForgeTheme.px(62); onClicked: root.resetToday() }
        ForgeButton { text: "›"; implicitWidth: ForgeTheme.px(30); Accessible.name: "Next month"; onClicked: root.navigate(1) }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 7
        columnSpacing: ForgeTheme.gap(3)
        rowSpacing: ForgeTheme.gap(4)
        opacity: 0.4 + root.monthProgress * 0.6
        transform: Translate { x: (1 - root.monthProgress) * root.direction * ForgeTheme.px(14) }
        Repeater {
            model: ["M", "T", "W", "T", "F", "S", "S"]
            Text { required property string modelData; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: modelData; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(9) }
        }
        Repeater {
            model: root.cells
            ForgeButton {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitWidth: ForgeTheme.px(24)
                implicitHeight: ForgeTheme.px(29)
                cut: ForgeTheme.px(4)
                text: String(modelData.day)
                Accessible.name: modelData.label
                selected: root.selectedDate === modelData.key
                opacity: modelData.month === root.month ? 1 : 0.4
                borderColor: modelData.key === Qt.formatDateTime(root.today, "yyyy-MM-dd") ? ForgeTheme.cyan : selected ? ForgeTheme.accent : "transparent"
                onClicked: root.choose(index)
            }
        }
    }
    Text { Layout.fillWidth: true; text: "SELECTED / " + root.selectedDate; color: ForgeTheme.muted; font.family: ForgeTheme.font; font.pixelSize: ForgeTheme.fontSize(9) }
    IpcHandler {
        target: "forgeCalendar"
        function status(): string { return JSON.stringify({ year: root.year, month: root.month, selected: root.selectedDate, cells: root.cells, moving: monthTravel.running }) }
        function navigate(offset: int): void { if (offset >= -12 && offset <= 12) root.navigate(offset) }
        function today(): void { root.resetToday() }
        function choose(index: int): void { root.choose(index) }
    }
}
