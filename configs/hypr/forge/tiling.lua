local M = { mode = "caelestia" }
local saved = {}
local function unfullscreen(window)
    if (window.fullscreen or 0) > 0 then
        hl.dispatch(hl.dsp.window.fullscreen({ mode = window.fullscreen == 1 and "maximized" or "fullscreen", window = window }))
    end
end
local path = (os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hypr/tiling.local.lua"
local file = io.open(path, "r")
if file then
    file:close()
    local ok, value = pcall(dofile, path)
    if ok and value == "windows" then M.mode = value end
end

hl.config({ general = { layout = "dwindle" }, dwindle = { preserve_split = true, smart_split = false, smart_resizing = true } })
if M.mode == "windows" then hl.window_rule({ name = "forge-windows", match = { class = ".*" }, float = true }) end

function M.apply()
    for _, window in ipairs(hl.get_windows()) do
        if window.mapped and not window.hidden then
            unfullscreen(window)
            hl.dispatch(hl.dsp.window.float({ action = M.mode == "windows" and "enable" or "disable", window = window }))
        end
    end
end

function M.snap(zone)
    local window = hl.get_active_window()
    if not window or not window.monitor then return end
    if zone == "restore" then
        local old = saved[window.address]
        if not old then return end
        unfullscreen(window)
        hl.dispatch(hl.dsp.window.float({ action = "enable", window = window }))
        hl.dispatch(hl.dsp.window.resize({ x = old.width, y = old.height, window = window }))
        hl.dispatch(hl.dsp.window.move({ x = old.x, y = old.y, window = window }))
        if not old.floating and M.mode ~= "windows" then hl.dispatch(hl.dsp.window.float({ action = "disable", window = window })) end
        saved[window.address] = nil
        return
    end
    local zones = {
        left = { 0, 0, 0.5, 1 }, right = { 0.5, 0, 0.5, 1 },
        top_left = { 0, 0, 0.5, 0.5 }, top_right = { 0.5, 0, 0.5, 0.5 },
        bottom_left = { 0, 0.5, 0.5, 0.5 }, bottom_right = { 0.5, 0.5, 0.5, 0.5 },
        maximize = { 0, 0, 1, 1 },
    }
    local area = zones[zone]
    if not area then return end
    saved[window.address] = saved[window.address] or { x = window.at.x, y = window.at.y, width = window.size.x, height = window.size.y, floating = window.floating }
    local monitor, gap = window.monitor, 12
    local reserved = monitor.reserved or {}
    local left, top = reserved.left or 0, reserved.top or 0
    local logical_width, logical_height = monitor.width / monitor.scale, monitor.height / monitor.scale
    if (monitor.transform or 0) % 2 == 1 then logical_width, logical_height = logical_height, logical_width end
    local width = logical_width - left - (reserved.right or 0)
    local height = logical_height - top - (reserved.bottom or 0)
    unfullscreen(window)
    hl.dispatch(hl.dsp.window.float({ action = "enable", window = window }))
    hl.dispatch(hl.dsp.window.resize({ x = math.max(100, math.floor(width * area[3] - gap * 2)), y = math.max(80, math.floor(height * area[4] - gap * 2)), window = window }))
    hl.dispatch(hl.dsp.window.move({ x = math.floor(monitor.x + left + width * area[1] + gap), y = math.floor(monitor.y + top + height * area[2] + gap), window = window }))
end

function M.arrow(direction)
    if M.mode == "windows" then
        M.snap(({ left = "left", right = "right", up = "maximize", down = "restore" })[direction])
    else
        hl.dispatch(hl.dsp.focus({ direction = direction }))
    end
end

hl.on("window.close", function(window) saved[window.address] = nil end)
return M
