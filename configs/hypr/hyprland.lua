local directory = (os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hypr/"
package.path = directory .. "?.lua;" .. package.path
require("forge.monitors")
local tiling = require("forge.tiling")

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")

hl.config({
    general = {
        gaps_in = 5,
        gaps_out = 12,
        border_size = 2,
        layout = "dwindle",
        resize_on_border = true,
        col = { active_border = "rgba(fcee0aff)", inactive_border = "rgba(693642ff)" },
    },
    decoration = {
        rounding = 0,
        active_opacity = 1,
        inactive_opacity = 1,
        blur = { enabled = true, size = 5, passes = 2 },
        shadow = { enabled = true, range = 18, render_power = 3, color = "rgba(090d1480)" },
    },
    animations = { enabled = true },
    input = { kb_layout = "us", follow_mouse = 1, touchpad = { natural_scroll = true, tap_to_click = true, disable_while_typing = true } },
    dwindle = { preserve_split = true },
    misc = { disable_hyprland_logo = true, force_default_wallpaper = -1 },
})

hl.curve("forge", { type = "bezier", points = { { 0.22, 1 }, { 0.36, 1 } } })
hl.animation({ leaf = "windows", enabled = true, speed = 4, bezier = "forge", style = "slide" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 4, bezier = "forge", style = "slide" })
hl.animation({ leaf = "fade", enabled = true, speed = 3, bezier = "forge" })
hl.animation({ leaf = "layers", enabled = true, speed = 3, bezier = "forge", style = "fade" })

local commands = {
    ["SUPER + Return"] = "kitty",
    ["SUPER + E"] = "thunar",
    ["SUPER + B"] = "firefox",
    ["SUPER + Space"] = "~/.local/bin/forge-launcher",
    ["SUPER + A"] = "quickshell -c forge ipc call forge controls",
    ["SUPER + I"] = "quickshell -c forge ipc call forge settings",
    ["SUPER + L"] = "~/.local/bin/forge-lock",
    ["SUPER + CTRL + V"] = "~/.local/bin/forge-clipboard",
    ["SUPER + SHIFT + R"] = "hyprctl reload",
    ["Print"] = "~/.local/bin/forge-screenshot",
    ["SUPER + Print"] = "quickshell -c forge ipc call forge hub capture",
    ["SUPER + SHIFT + Escape"] = "hyprshutdown",
    ["ALT + Tab"] = "quickshell -c forge ipc call forge overview",
    ["SUPER + O"] = "quickshell -c forge ipc call forge overview",
    ["SUPER + N"] = "quickshell -c forge ipc call forge hub alerts",
    ["SUPER + G"] = "quickshell -c forge ipc call forge hub hardware",
}
local shortcut_file = io.open(directory .. "forge/shortcuts.lua", "r")
if shortcut_file then
    shortcut_file:close()
    local shortcuts = dofile(directory .. "forge/shortcuts.lua")
    local defaults = { terminal = "SUPER + Return", files = "SUPER + E", browser = "SUPER + B", launcher = "SUPER + Space", controls = "SUPER + A", settings = "SUPER + I", lock = "SUPER + L" }
    local remapped = {}
    for name, key in pairs(defaults) do remapped[name] = commands[key]; commands[key] = nil end
    for name, command in pairs(remapped) do commands[shortcuts[name] or defaults[name]] = command end
end
for key, command in pairs(commands) do hl.bind(key, hl.dsp.exec_cmd(command)) end
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
hl.bind("SUPER + S", hl.dsp.workspace.toggle_special("scratch"))
hl.bind("SUPER + SHIFT + S", hl.dsp.window.move({ workspace = "special:scratch" }))
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
for _, direction in ipairs({ "left", "right", "up", "down" }) do
    hl.bind("SUPER + " .. direction, function() tiling.arrow(direction) end)
    hl.bind("SUPER + SHIFT + " .. direction, hl.dsp.window.move({ direction = direction }))
end
for key, zone in pairs({ Home = "top_left", Prior = "top_right", End = "bottom_left", Next = "bottom_right" }) do
    hl.bind("SUPER + CTRL + " .. key, function() tiling.snap(zone) end)
end
for i = 1, 10 do
    hl.bind("SUPER + " .. i % 10, hl.dsp.focus({ workspace = i }))
    hl.bind("SUPER + SHIFT + " .. i % 10, hl.dsp.window.move({ workspace = i }))
end
local media = {
    XF86AudioRaiseVolume = "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+",
    XF86AudioLowerVolume = "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",
    XF86AudioMute = "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
    XF86AudioMicMute = "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle",
    XF86MonBrightnessUp = "~/.local/bin/forge-backlight up",
    XF86MonBrightnessDown = "~/.local/bin/forge-backlight down",
    XF86AudioPlay = "playerctl play-pause",
    XF86AudioNext = "playerctl next",
    XF86AudioPrev = "playerctl previous",
}
for key, command in pairs(media) do hl.bind(key, hl.dsp.exec_cmd(command), { locked = true, repeating = true }) end
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
hl.on("hyprland.start", function() hl.exec_cmd("~/.local/bin/forge-session") end)

local colors = io.open(directory .. "forge/colors.lua", "r")
if colors then colors:close(); dofile(directory .. "forge/colors.lua") end
local preferences = io.open(directory .. "forge/preferences.lua", "r")
if preferences then preferences:close(); dofile(directory .. "forge/preferences.lua") end
local override = directory .. "user.lua"
local file = io.open(override, "r")
if file then file:close(); dofile(override) end
