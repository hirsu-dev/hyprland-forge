local layout = require("forge.layout")
local rules, signature = {}, ""
local options = { internal_scale = "auto" }
local override = (os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hypr/monitors.local.lua"
local file = io.open(override, "r")
if file then
    file:close()
    local value = dofile(override)
    if type(value) == "table" then options = value end
end

local function configure(focus)
    local monitors = hl.get_monitors({ all = true })
    local names = {}
    for _, monitor in ipairs(monitors) do table.insert(names, monitor.name) end
    table.sort(names)
    local next_signature = table.concat(names, ",")
    if not focus and next_signature == signature then return end
    signature = next_signature
    local plan = layout.plan(monitors, options)
    for _, rule in ipairs(rules) do rule:set_enabled(false) end
    rules = {}
    for _, monitor in ipairs(plan.monitors) do hl.monitor(monitor) end
    for _, workspace in ipairs(plan.workspaces) do
        table.insert(rules, hl.workspace_rule(workspace))
        if hl.get_workspace(workspace.workspace) then
            hl.dispatch(hl.dsp.workspace.move({ workspace = workspace.workspace, monitor = workspace.monitor }))
        end
    end
    if focus and plan.primary then hl.dispatch(hl.dsp.focus({ monitor = plan.primary })) end
end

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
local function schedule(focus)
    if not os.getenv("HYPRLAND_INSTANCE_SIGNATURE") then return end
    hl.timer(function() configure(focus) end, { timeout = 150, type = "oneshot" })
end
hl.on("hyprland.start", function() schedule(true) end)
hl.on("config.reloaded", function() schedule(true) end)
hl.on("monitor.added", function() schedule(false) end)
hl.on("monitor.removed", function() schedule(false) end)
