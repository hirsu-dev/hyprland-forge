#!/usr/bin/env bash
set -euo pipefail
[[ "$(systemd-detect-virt --vm)" == oracle && $EUID -eq 0 ]]
forge_instance="$(find /run/user/1000/hypr -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | head -n1)"
[[ -n "$forge_instance" ]]
forge_env=(runuser -u forge -- env HOME=/home/forge XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1 "HYPRLAND_INSTANCE_SIGNATURE=$forge_instance" DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus)
case "${1:-status}" in
deploy)
    "${forge_env[@]}" python /home/forge/system-deck-test/tests/deploy-system-deck.py --disposable-vm
    pkill -u forge -f '^bash /home/forge/.local/bin/forge-session$' || true
    pkill -u forge -x quickshell || true
    pkill -u forge -x mako || true
    sleep 2
    "${forge_env[@]}" systemd-run --user --unit=forge-system-deck --collect /home/forge/.local/bin/forge-session
    ;;
test)
    "${forge_env[@]}" python /home/forge/system-deck-test/tests/validate-system-deck.py --disposable-vm
    ;;
ipc)
    shift
    "${forge_env[@]}" quickshell -c forge ipc call "$@"
    ;;
run)
    shift
    "${forge_env[@]}" "$@"
    ;;
capture)
    "${forge_env[@]}" hyprctl dispatch 'hl.dsp.dpms({action="on"})'
    "${forge_env[@]}" grim "/tmp/forge-system-deck-${2:-desktop}.png"
    ;;
status)
    "${forge_env[@]}" hyprctl configerrors
    "${forge_env[@]}" journalctl --user -u forge-system-deck --no-pager -n 80
    ;;
esac
