local window = { address = "test", mapped = true, hidden = false, floating = true, at = { x = 100, y = 100 }, size = { x = 600, y = 400 }, monitor = { x = -1920, y = 0, width = 1920, height = 1080, scale = 1, reserved = { top = 56 } } }
local calls, events = {}, {}
local function action(kind)
    return function(value) value.kind = kind; return value end
end
hl = {
    config = function() end,
    window_rule = function() end,
    get_windows = function() return { window } end,
    get_active_window = function() return window end,
    on = function(event, callback) events[event] = callback end,
    dispatch = function(value) table.insert(calls, value) end,
    dsp = { focus = action("focus"), window = { float = action("float"), fullscreen = action("fullscreen"), resize = action("resize"), move = action("move") } },
}
local tiling = dofile("configs/hypr/forge/tiling.lua")
tiling.mode = "caelestia"
tiling.arrow("left")
assert(calls[#calls].direction == "left" and calls[#calls].kind == "focus")
tiling.mode = "windows"
tiling.arrow("left")
assert(calls[#calls].x == -1908 and calls[#calls].y == 68)
assert(calls[#calls - 1].x == 936 and calls[#calls - 1].y == 1000)
tiling.snap("bottom_right")
assert(calls[#calls].x == -948 and calls[#calls].y == 580)
tiling.arrow("up")
assert(calls[#calls - 1].x == 1896 and calls[#calls - 1].y == 1000)
tiling.arrow("down")
assert(calls[#calls].x == 100 and calls[#calls].y == 100)
assert(calls[#calls - 1].x == 600 and calls[#calls - 1].y == 400)
local count = #calls
tiling.snap("restore")
tiling.snap("unknown")
assert(#calls == count)
tiling.apply()
assert(calls[#calls].action == "enable")
tiling.mode = "caelestia"
tiling.apply()
assert(calls[#calls].action == "disable")
window.hidden = true
count = #calls
tiling.apply()
assert(#calls == count)
tiling.snap("left")
events["window.close"](window)
count = #calls
tiling.snap("restore")
assert(#calls == count)
print("Tiling and snap scenarios passed")
window.monitor.scale = 2
window.monitor.transform = 1
tiling.snap("bottom_right")
assert(calls[#calls].x == -1638 and calls[#calls].y == 520)
assert(calls[#calls - 1].x == 246 and calls[#calls - 1].y == 428)
