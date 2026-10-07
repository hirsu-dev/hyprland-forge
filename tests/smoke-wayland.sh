#!/usr/bin/env bash
set -euo pipefail
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_HEADLESS_OUTPUTS=2
export QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software
mkdir -p test-results
sway -c "$(pwd)/tests/sway.conf" -d >test-results/sway.log 2>&1 &
forge_sway=$!
forge_wallpaper=""
forge_stop() {
    if [[ -n "$forge_wallpaper" ]]; then kill "$forge_wallpaper" 2>/dev/null || true; fi
    kill "$forge_sway" 2>/dev/null || true
    wait "$forge_sway" 2>/dev/null || true
}
trap forge_stop EXIT
for ((attempt = 0; attempt < 50; attempt++)); do
    kill -0 "$forge_sway" || { cat test-results/sway.log; exit 1; }
    for forge_socket in "$XDG_RUNTIME_DIR"/wayland-*; do
        if [[ -S "$forge_socket" ]]; then export WAYLAND_DISPLAY="${forge_socket##*/}"; break; fi
    done
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then break; fi
    sleep 0.2
done
: "${WAYLAND_DISPLAY:?Wayland did not start}"
for forge_socket in "$XDG_RUNTIME_DIR"/sway-ipc.*.sock; do
    if [[ -S "$forge_socket" ]]; then export SWAYSOCK="$forge_socket"; break; fi
done
swaymsg -t get_outputs
python tests/validate-clipboard.py
bash configs/bin/forge-wallpaper "$(pwd)/configs/backgrounds/forge.svg" >test-results/wallpaper.log 2>&1 &
forge_wallpaper=$!
bash tests/smoke-shell.sh
kill -0 "$forge_wallpaper"
