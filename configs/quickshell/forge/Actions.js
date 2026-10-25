.pragma library

const entries = [
    { id: "appearance", name: "Interface & motion", keywords: "theme animation scale colors", icon: "preferences-desktop-theme" },
    { id: "connections", name: "Connections", keywords: "wifi bluetooth network", icon: "preferences-system-network" },
    { id: "wallpapers", name: "Wallpapers", keywords: "background live engine", icon: "preferences-desktop-wallpaper" },
    { id: "capture", name: "Capture studio", keywords: "screenshot record video", icon: "camera-photo" },
    { id: "hardware", name: "System monitor", keywords: "cpu ram hardware temperature", icon: "utilities-system-monitor" },
    { id: "alerts", name: "Notification center", keywords: "history alerts dnd", icon: "preferences-desktop-notification" },
    { id: "recovery", name: "Updates & recovery", keywords: "health backup logs repair", icon: "system-software-update" },
    { id: "settings", name: "Display & workspace", keywords: "monitor resolution tiling windows", icon: "preferences-desktop-display" },
    { id: "overview", name: "Window overview", keywords: "apps focus switch", icon: "view-grid" },
    { id: "clipboard", name: "Clipboard history", keywords: "copy paste text image", icon: "edit-paste" },
    { id: "power", name: "Session controls", keywords: "logout power suspend restart", icon: "system-shutdown" }
]

function search(value) {
    const words = value.toLowerCase().trim().split(/\s+/).filter(word => word.length)
    return entries.filter(entry => words.every(word => (entry.name + " " + entry.keywords).toLowerCase().includes(word)))
}
