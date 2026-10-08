local M = {}

local function internal(name)
    return name:match("^eDP") or name:match("^LVDS") or name:match("^DSI")
end

local function external_mode(monitor)
    local selected, distance = nil, math.huge
    local preferred_width = monitor.width or 1920
    local preferred_height = monitor.height or 1080
    for _, mode in ipairs(monitor.available_modes or {}) do
        if mode.preferred then preferred_width, preferred_height = mode.width, mode.height end
        local delta = math.abs(mode.refresh_rate - 120)
        if mode.width == 1920 and mode.height == 1080 and delta <= 1 and delta < distance then
            selected, distance = mode, delta
        end
    end
    if selected then
        return string.format("1920x1080@%.3f", selected.refresh_rate), 1920, 1080
    end
    return "preferred", preferred_width, preferred_height
end

function M.plan(monitors, options)
    options = options or {}
    if options.outputs then
        local result = { monitors = {}, workspaces = {} }
        local enabled = {}
        for _, monitor in ipairs(monitors) do
            local choice = options.outputs[monitor.name]
            local rule = { output = monitor.name, mode = "preferred", position = "auto", scale = "auto", disabled = false }
            if choice then for key, value in pairs(choice) do rule[key] = value end end
            rule.output = monitor.name
            table.insert(result.monitors, rule)
            if not rule.disabled then table.insert(enabled, monitor.name) end
        end
        if #enabled == 0 and #monitors > 0 then
            result.monitors[1] = { output = monitors[1].name, mode = "preferred", position = "0x0", scale = "auto", disabled = false }
            enabled[1] = monitors[1].name
        end
        for _, name in ipairs(enabled) do if name == options.primary then result.primary = name end end
        result.primary = result.primary or enabled[1]
        local secondary
        for _, name in ipairs(enabled) do if name ~= result.primary then secondary = secondary or name end end
        for i = 1, 10 do
            if result.primary then result.workspaces[i] = { workspace = tostring(i), monitor = i > 5 and secondary or result.primary, persistent = true, default = i == 1 or (i == 6 and secondary ~= nil) } end
        end
        return result
    end
    local panel, external, other = nil, nil, {}
    for _, monitor in ipairs(monitors) do
        if internal(monitor.name) then
            panel = panel or monitor
        else
            table.insert(other, monitor)
        end
    end
    table.sort(other, function(a, b)
        local a_priority = a.name == options.external and 0 or a.name:match("^HDMI") and 1 or 2
        local b_priority = b.name == options.external and 0 or b.name:match("^HDMI") and 1 or 2
        if a_priority ~= b_priority then return a_priority < b_priority end
        return a.name < b.name
    end)
    external = other[1]
    local primary = external or panel
    if not primary then return { monitors = {}, workspaces = {} } end
    local result = { monitors = {}, workspaces = {}, primary = primary.name }
    local width, height = 0, external and 1080 or 0
    if external then
        local mode
        mode, width, height = external_mode(external)
        table.insert(result.monitors, { output = external.name, mode = mode, position = "0x0", scale = 1 })
    end
    if panel then
        local scale = tonumber(options.internal_scale) or panel.scale or 1
        local panel_width, panel_height = panel.width or 1920, panel.height or 1080
        for _, mode in ipairs(panel.available_modes or {}) do
            if mode.preferred then panel_width, panel_height = mode.width, mode.height end
        end
        local x, y = width, 0
        if options.internal_position == "left" then x = -math.ceil(panel_width / scale)
        elseif options.internal_position == "above" then x, y = 0, -math.ceil(panel_height / scale)
        elseif options.internal_position == "below" then x, y = 0, height end
        table.insert(result.monitors, {
            output = panel.name,
            mode = "preferred",
            position = external and (tostring(x) .. "x" .. tostring(y)) or "0x0",
            scale = options.internal_scale or "auto",
            disabled = false,
        })
    end
    for _, monitor in ipairs(other) do
        if monitor ~= external then
            table.insert(result.monitors, { output = monitor.name, mode = "preferred", position = "auto", scale = "auto" })
        end
    end
    for i = 1, 10 do
        local target = i > 5 and panel or primary
        result.workspaces[i] = { workspace = tostring(i), monitor = target.name, persistent = true, default = i == 1 or (i == 6 and panel ~= nil and external ~= nil) }
    end
    return result
end

return M
