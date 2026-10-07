#!/usr/bin/env bash
set -euo pipefail
forge_config="$(pwd)/configs/quickshell/forge/shell.qml"
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR="$(mktemp -d)"
export QT_QPA_PLATFORM=xcb
export QT_QUICK_BACKEND=software
mkdir -p test-results
quickshell -p "$forge_config" >test-results/quickshell.log 2>&1 &
forge_pid=$!
forge_stop() {
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
quickshell -p "$forge_config" ipc call forge launcher
forge_status true false
sleep 1
quickshell -p "$forge_config" ipc call forge controls
forge_status false true
sleep 1
quickshell -p "$forge_config" ipc call forge close
forge_status false false
kill -0 "$forge_pid"
python -c 'import pathlib,re; s=pathlib.Path("test-results/quickshell.log").read_text(); assert "Configuration Loaded" in s; assert not re.search(r"(Failed to load configuration|is not installed|Cannot assign|ReferenceError|TypeError|SyntaxError|Binding loop)",s)'
