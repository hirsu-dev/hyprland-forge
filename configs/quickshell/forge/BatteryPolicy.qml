import QtQuick

QtObject {
    id: root
    property bool available: false
    property bool discharging: false
    property real charge: 1
    property int notified: 0
    signal warning(string title, string message, bool critical)
    function evaluate() {
        if (!available || !Number.isFinite(charge) || charge < 0 || charge > 1) return
        if (!discharging || charge > 0.2) { notified = 0; return }
        const level = charge <= 0.05 ? 2 : charge <= 0.15 ? 1 : 0
        if (level <= notified) return
        notified = level
        const remaining = Math.round(charge * 100)
        warning(level === 2 ? "BATTERY CRITICAL / " + remaining + "%" : "LOW BATTERY / " + remaining + "%", level === 2 ? "Connect your charger now and save your work." : "Connect your charger soon. Battery saver is available in Control Center.", level === 2)
    }
    onAvailableChanged: evaluate()
    onDischargingChanged: evaluate()
    onChargeChanged: evaluate()
}
