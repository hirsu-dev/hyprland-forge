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
trap 'kill "$forge_pid" 2>/dev/null || true' EXIT
sleep 4
kill -0 "$forge_pid"
quickshell -p "$forge_config" ipc call forge launcher
sleep 1
quickshell -p "$forge_config" ipc call forge controls
sleep 1
quickshell -p "$forge_config" ipc call forge close
python -c 'import pathlib,re; s=pathlib.Path("test-results/quickshell.log").read_text(); print(s); assert "Configuration Loaded" in s; assert not re.search(r"(Failed to load configuration|is not installed|Cannot assign|ReferenceError|TypeError|SyntaxError)",s)'
