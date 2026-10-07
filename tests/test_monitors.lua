package.path = "configs/hypr/?.lua;" .. package.path
local monitors = {
    { name = "eDP-1", width = 1920, height = 1080 },
    { name = "HDMI-A-1", available_modes = {{ width = 1920, height = 1080, refresh_rate = 120 }} },
}
local events, timers, applied, workspaces, dispatched = {}, {}, {}, {}, {}
local disabled = 0
local active_session = true
local original_getenv = os.getenv
os.getenv = function(name)
    if name == "HYPRLAND_INSTANCE_SIGNATURE" then return active_session and "test" or nil end
    return original_getenv(name)
end
hl = {
    monitor = function(rule) table.insert(applied, rule) end,
    get_monitors = function() return monitors end,
    workspace_rule = function(rule)
        table.insert(workspaces, rule)
        return { set_enabled = function(_, enabled) assert(not enabled); disabled = disabled + 1 end }
    end,
    get_workspace = function() return true end,
    dispatch = function(action) table.insert(dispatched, action) end,
    timer = function(callback, options) assert(options.type == "oneshot"); table.insert(timers, callback) end,
    on = function(event, callback) events[event] = callback end,
    dsp = { focus = function(value) return value end, workspace = { move = function(value) return value end } },
}
local function flush()
    local queued = timers
    timers = {}
    for _, callback in ipairs(queued) do callback() end
end
require("forge.monitors")
assert(#applied == 1)
events["hyprland.start"]()
flush()
assert(#workspaces == 10)
assert(applied[2].output == "HDMI-A-1")
assert(dispatched[#dispatched].monitor == "HDMI-A-1")
events["monitor.added"]()
flush()
assert(#workspaces == 10)
monitors = { monitors[1] }
events["monitor.removed"]()
flush()
assert(disabled == 10)
assert(#workspaces == 20)
assert(workspaces[20].monitor == "eDP-1")
events["config.reloaded"]()
flush()
assert(disabled == 20)
assert(dispatched[#dispatched].monitor == "eDP-1")
active_session = false
events["config.reloaded"]()
assert(#timers == 0)
os.getenv = original_getenv
print("Compositor event lifecycle scenarios passed")
