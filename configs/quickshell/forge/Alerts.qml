pragma Singleton
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications
import QtQuick

Singleton {
    id: root
    property bool dnd: false
    property var history: []
    property var popups: []
    property var deadlines: ({})
    property int localIdentity: -1
    readonly property var active: server.trackedNotifications.values
    function systemNotice(title, message, critical) {
        const entry = { id: localIdentity--, app: "FORGE / POWER", title: title.slice(0, 256), body: message.slice(0, 4096), critical: critical, time: Qt.formatDateTime(new Date(), "hh:mm"), until: Date.now() + (critical ? 15000 : 8000) }
        history = [entry].concat(history).slice(0, 80)
        if (!dnd || critical) popups = [entry].concat(popups).slice(0, 3)
    }
    function receive(notification) {
        notification.tracked = true
        const critical = notification.urgency === NotificationUrgency.Critical
        const entry = { id: notification.id, app: notification.appName.slice(0, 128), title: notification.summary.slice(0, 256), body: notification.body.slice(0, 4096), critical: critical, time: Qt.formatDateTime(new Date(), "hh:mm"), until: Date.now() + (critical ? 15000 : 6000) }
        if (!notification.transient) history = [entry].concat(history.filter(item => item.id !== entry.id)).slice(0, 80)
        if ((!dnd || critical) && !notification.lastGeneration) popups = [entry].concat(popups.filter(item => item.id !== entry.id)).slice(0, 3)
        const next = Object.assign({}, deadlines)
        next[entry.id] = notification.expireTimeout === 0 ? 0 : Date.now() + (notification.expireTimeout > 0 ? notification.expireTimeout : 8000)
        deadlines = next
        notification.closed.connect(() => {
            root.history = root.history.map(item => item.id === entry.id ? Object.assign({}, item, { title: notification.summary.slice(0, 256), body: notification.body.slice(0, 4096) }) : item)
            root.popups = root.popups.filter(item => item.id !== entry.id)
            const remaining = Object.assign({}, root.deadlines)
            delete remaining[entry.id]
            root.deadlines = remaining
        })
        if (active.length > 100) active[0].expire()
    }
    function find(id) { return active.find(item => item.id === id) || null }
    function dismiss(id) {
        const notification = find(id)
        if (notification) notification.dismiss()
        history = history.filter(item => item.id !== id)
        popups = popups.filter(item => item.id !== id)
    }
    function clear() { for (const item of active.slice()) item.dismiss(); history = []; popups = [] }
    onDndChanged: if (dnd) popups = popups.filter(item => item.critical)
    NotificationServer {
        id: server
        actionsSupported: true
        bodyMarkupSupported: false
        persistenceSupported: true
        onNotification: notification => root.receive(notification)
    }
    Timer {
        interval: 500
        running: root.active.length > 0 || root.popups.length > 0
        repeat: true
        onTriggered: {
            const now = Date.now()
            root.popups = root.popups.filter(item => item.until > now)
            for (const notification of root.active.slice()) {
                const deadline = root.deadlines[notification.id]
                if (deadline && deadline <= now) notification.expire()
            }
        }
    }
    IpcHandler {
        target: "forgeAlerts"
        function status(): string { return JSON.stringify({ dnd: root.dnd, history: root.history, popups: root.popups.length, active: root.active.length }) }
        function quiet(value: bool): void { root.dnd = value }
        function clear(): void { root.clear() }
        function dismiss(id: int): void { root.dismiss(id) }
        function invoke(id: int, index: int): void {
            const notification = root.find(id)
            if (notification && index >= 0 && index < notification.actions.length) notification.actions[index].invoke()
        }
    }
}
