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
cp configs/forge/theme.json "$XDG_CONFIG_HOME/forge/theme.json"
mkdir -p test-results
quickshell -p "$forge_config" >test-results/quickshell.log 2>&1 &
forge_pid=$!
forge_tray=""
forge_stop() {
    if [[ -n "$forge_tray" ]]; then kill "$forge_tray" 2>/dev/null || true; wait "$forge_tray" 2>/dev/null || true; fi
    kill "$forge_pid" 2>/dev/null || true
    wait "$forge_pid" 2>/dev/null || true
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
python tests/tray-fixture.py >test-results/tray.log 2>&1 &
forge_tray=$!
for ((attempt = 0; attempt < 50; attempt++)); do
    kill -0 "$forge_tray" || { cat test-results/tray.log; exit 1; }
    forge_count="$(quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; print(json.load(sys.stdin)["trayItems"])')"
    if [[ "$forge_count" == 1 ]]; then break; fi
    sleep 0.2
done
[[ "$forge_count" == 1 ]]
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
kill -0 "$forge_pid"
kill "$forge_tray"
wait "$forge_tray"
forge_tray=""
sleep 0.5
quickshell -p "$forge_config" ipc call forge status | python -c 'import json,sys; assert json.load(sys.stdin)["trayItems"] == 0'
python -c 'import pathlib,re; s=pathlib.Path("test-results/quickshell.log").read_text(); assert "Configuration Loaded" in s; assert not re.search(r"(Failed to load configuration|is not installed|Cannot assign|Unable to assign|ReferenceError|TypeError|SyntaxError|Binding loop)",s)'
