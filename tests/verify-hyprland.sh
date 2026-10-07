#!/usr/bin/env bash
set -euo pipefail
forge_home="$(mktemp -d)"
mkdir -p "$forge_home/.config/hypr" "$forge_home/runtime" test-results
chmod 700 "$forge_home/runtime"
cp -r configs/hypr/. "$forge_home/.config/hypr/"
chown -R nobody:nobody "$forge_home"
timeout 30s runuser -u nobody -- env -u HYPRLAND_INSTANCE_SIGNATURE HOME="$forge_home" XDG_RUNTIME_DIR="$forge_home/runtime" XDG_CONFIG_HOME="$forge_home/.config" gdb -batch -ex 'set pagination off' -ex run -ex 'thread apply all bt' --args Hyprland --verify-config -c "$forge_home/.config/hypr/hyprland.lua" >test-results/hyprland-verify.log 2>&1
cat test-results/hyprland-verify.log
python -c 'from pathlib import Path; s=Path("test-results/hyprland-verify.log").read_text(); assert "config ok" in s and "exited normally" in s and "received signal" not in s'
