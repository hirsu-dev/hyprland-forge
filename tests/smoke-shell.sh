#!/usr/bin/env bash
set -euo pipefail
forge_config="$(pwd)/configs/quickshell/forge/shell.qml"
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$(mktemp -d)}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export QT_QUICK_BACKEND=software
export XDG_CONFIG_HOME
XDG_CONFIG_HOME="$(mktemp -d)"
mkdir -p "$XDG_CONFIG_HOME/forge"
mkdir -p "$XDG_CONFIG_HOME/qt6ct"
cp configs/forge/theme.json "$XDG_CONFIG_HOME/forge/theme.json"
cp configs/forge/interface.json "$XDG_CONFIG_HOME/forge/interface.json"
cp configs/forge/taskbar.json "$XDG_CONFIG_HOME/forge/taskbar.json"
cp configs/qt6ct/qt6ct.conf "$XDG_CONFIG_HOME/qt6ct/qt6ct.conf"
export QT_QPA_PLATFORMTHEME=qt6ct
mkdir -p test-results
forge_fixture="$(mktemp -d)"
cp tests/brightness-fixture "$forge_fixture/brightnessctl"
chmod +x "$forge_fixture/brightnessctl"
export PATH="$forge_fixture:$PATH"
export FORGE_BRIGHTNESS_STATE="$forge_fixture/brightness.json"
forge_audio_children=()
forge_audio_stop() {
    for forge_audio_pid in "${forge_audio_children[@]}"; do kill "$forge_audio_pid" 2>/dev/null || true; done
    for forge_audio_pid in "${forge_audio_children[@]}"; do wait "$forge_audio_pid" 2>/dev/null || true; done
}
trap forge_audio_stop EXIT
pipewire >test-results/pipewire.log 2>&1 &
forge_audio_children+=("$!")
for ((attempt = 0; attempt < 50; attempt++)); do
    if pw-cli info 0 >/dev/null 2>&1; then break; fi
    sleep 0.2
done
pw-cli info 0 >/dev/null
wireplumber >test-results/wireplumber.log 2>&1 &
forge_audio_children+=("$!")
pw-cli create-node adapter '{ factory.name=support.null-audio-sink node.name=ForgeTestSink node.description="Forge test sink" media.class=Audio/Sink object.linger=true audio.position=[ FL FR ] }'
forge_sink="$(pw-dump | python -c 'import json,sys; print(next(n["id"] for n in json.load(sys.stdin) if n.get("info",{}).get("props",{}).get("node.name") == "ForgeTestSink"))')"
for ((attempt = 0; attempt < 50; attempt++)); do
    if wpctl set-default "$forge_sink"; then break; fi
    sleep 0.2
done
wpctl set-default "$forge_sink"
quickshell -p "$forge_config" >test-results/quickshell.log 2>&1 &
forge_pid=$!
forge_tray=""
forge_stop() {
    if [[ -n "$forge_tray" ]]; then kill "$forge_tray" 2>/dev/null || true; wait "$forge_tray" 2>/dev/null || true; fi
    kill "$forge_pid" 2>/dev/null || true
    wait "$forge_pid" 2>/dev/null || true
    forge_audio_stop
    cat test-results/quickshell.log
}
trap forge_stop EXIT
for ((attempt = 0; attempt < 50; attempt++)); do
    kill -0 "$forge_pid"
    if quickshell -p "$forge_config" ipc call forge close 2>/dev/null; then break; fi
    sleep 0.2
done
kill -0 "$forge_pid"
forge_status() {
    quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["screens"] > 0 and d["screen"]; assert d["launcher"] == (sys.argv[1] == "true"); assert d["controls"] == (sys.argv[2] == "true")' "$1" "$2"
}
forge_status false false
quickshell -p "$forge_config" ipc call forgeTasks status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["enabled"] and d["showTitles"]; assert d["pins"] == ["kitty","thunar","firefox"]'
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_audio="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["audio"])')"
    if [[ "$forge_audio" == True ]]; then break; fi
    sleep 0.2
done
[[ "$forge_audio" == True ]]
quickshell -p "$forge_config" ipc call forge volume 0.4
quickshell -p "$forge_config" ipc call forge mute
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["volume"] == 40 and d["muted"]'
quickshell -p "$forge_config" ipc call forge mute
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; assert not json.load(sys.stdin)["muted"]'
python tests/tray-fixture.py >test-results/tray.log 2>&1 &
forge_tray=$!
for ((attempt = 0; attempt < 50; attempt++)); do
    kill -0 "$forge_tray" || { cat test-results/tray.log; exit 1; }
    forge_count="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["trayItems"])')"
    if [[ "$forge_count" == 1 ]]; then break; fi
    sleep 0.2
done
[[ "$forge_count" == 1 ]]
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_track="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["track"])')"
    if [[ "$forge_track" == Orbit ]]; then break; fi
    sleep 0.2
done
[[ "$forge_track" == Orbit ]]
quickshell -p "$forge_config" ipc call forge media next
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["track"] == "Dawn" and d["playing"]'
quickshell -p "$forge_config" ipc call forge media toggle
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; assert not json.load(sys.stdin)["playing"]'
quickshell -p "$forge_config" ipc call forge media previous
quickshell -p "$forge_config" ipc call forge media toggle
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["track"] == "Orbit" and d["playing"]'
forge_accent="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["accent"])')"
python -c 'import os; from pathlib import Path; from forge.theme import PRESETS,render; from forge.storage import atomic_write; atomic_write(Path(os.environ["XDG_CONFIG_HOME"])/"forge/theme.json",render(PRESETS["ocean"])[".config/forge/theme.json"].encode())'
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_next="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["accent"])')"
    if [[ "$forge_next" != "$forge_accent" ]]; then break; fi
    sleep 0.2
done
[[ "$forge_next" != "$forge_accent" ]]
cp configs/forge/theme.json "$XDG_CONFIG_HOME/forge/theme.json"
sleep 0.5
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then quickshell -p "$forge_config" ipc call forge screen HEADLESS-1; fi
quickshell -p "$forge_config" ipc call forge launcher
forge_status true false
sleep 1
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then grim -o HEADLESS-1 test-results/launcher.png; fi
quickshell -p "$forge_config" ipc call forge controls
forge_status false true
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_backlight="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["backlight"])')"
    if [[ "$forge_backlight" == True ]]; then break; fi
    sleep 0.2
done
[[ "$forge_backlight" == True ]]
quickshell -p "$forge_config" ipc call forge brightness 35
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_light="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["brightness"])')"
    if [[ "$forge_light" == 35 ]]; then break; fi
    sleep 0.2
done
[[ "$forge_light" == 35 ]]
python -c 'import os,json; from pathlib import Path; state=json.loads(Path(os.environ["FORGE_BRIGHTNESS_STATE"]).read_text()); assert state["updates"] == [35]'
sleep 1
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then grim -o HEADLESS-1 test-results/controls.png; fi
quickshell -p "$forge_config" ipc call forge close
forge_status false false
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then
    python -c 'from pathlib import Path; assert Path("test-results/launcher.png").read_bytes() != Path("test-results/controls.png").read_bytes()'
    quickshell -p "$forge_config" ipc call forge screen HEADLESS-2
    quickshell -p "$forge_config" ipc call forge controls
    quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["screen"] == "HEADLESS-2" and d["screens"] == 2'
    swaymsg output HEADLESS-2 disable
    sleep 1
    quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["screen"] == "HEADLESS-1" and d["screens"] == 1'
    quickshell -p "$forge_config" ipc call forge close
fi
quickshell -p "$forge_config" ipc call forgeTasks status | python -c 'import json,sys; d=json.load(sys.stdin); assert len(d["bars"]) > 0 and all(b["visible"] for b in d["bars"])'
python -c 'import json,os; from pathlib import Path; from forge.storage import atomic_write; from forge.taskbar import DEFAULTS; atomic_write(Path(os.environ["XDG_CONFIG_HOME"])/"forge/taskbar.json",json.dumps({**DEFAULTS,"enabled":False,"showTitles":False}).encode())'
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_taskbar="$(quickshell -p "$forge_config" ipc call forgeTasks status | python -c 'import json,sys; d=json.load(sys.stdin); print(d["enabled"] or d["showTitles"] or any(b["visible"] for b in d["bars"]))')"
    if [[ "$forge_taskbar" == False ]]; then break; fi
    sleep 0.2
done
[[ "$forge_taskbar" == False ]]
cp configs/forge/taskbar.json "$XDG_CONFIG_HOME/forge/taskbar.json"
quickshell -p "$forge_config" ipc call forge taskbar
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["settings"] and d["settingsPage"] == 2'
sleep 0.5
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then grim -o HEADLESS-1 test-results/taskbar.png; fi
quickshell -p "$forge_config" ipc call forge close
quickshell -p "$forge_config" ipc call forge settings
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["settings"] and not d["controls"] and not d["launcher"]'
quickshell -p "$forge_config" ipc call forge appearance
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; assert json.load(sys.stdin)["settingsPage"] == 1'
sleep 0.5
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then grim -o HEADLESS-1 test-results/interface.png; fi
python -c 'import json,os; from pathlib import Path; from forge.storage import atomic_write; atomic_write(Path(os.environ["XDG_CONFIG_HOME"])/"forge/interface.json",json.dumps({"motion":False,"effects":False}).encode())'
for ((attempt = 0; attempt < 50; attempt++)); do
    forge_motion="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); print(d["motion"] or d["effects"])')"
    if [[ "$forge_motion" == False ]]; then break; fi
    sleep 0.2
done
[[ "$forge_motion" == False ]]
quickshell -p "$forge_config" ipc call forge close
quickshell -p "$forge_config" ipc call forge launcher
forge_status true false
quickshell -p "$forge_config" ipc call forge close
cp configs/forge/interface.json "$XDG_CONFIG_HOME/forge/interface.json"
quickshell -p "$forge_config" ipc call forge power
quickshell -p "$forge_config" ipc call forge powerChoice reboot
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert d["power"] and d["powerAction"] == "reboot" and not d["launcher"] and not d["controls"]'
sleep 0.5
if [[ "$QT_QPA_PLATFORM" == wayland ]]; then grim -o HEADLESS-1 test-results/power.png; fi
quickshell -p "$forge_config" ipc call forge close
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; d=json.load(sys.stdin); assert not d["power"] and not d["powerAction"]'
kill -0 "$forge_pid"
kill "$forge_tray"
wait "$forge_tray"
forge_tray=""
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; assert json.load(sys.stdin)["trayItems"] == 0'
python -c 'import pathlib,re; s=pathlib.Path("test-results/quickshell.log").read_text(); assert "Configuration Loaded" in s; assert not re.search(r"(Failed to load configuration|is not installed|Cannot assign|Unable to assign|ReferenceError|TypeError|SyntaxError|Binding loop)",s)'
