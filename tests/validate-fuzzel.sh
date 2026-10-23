#!/usr/bin/env bash
set -euo pipefail
forge_home="$(mktemp -d)"
export HOME="$forge_home"
mkdir -p "$forge_home/.config/fuzzel"
cp configs/fuzzel/*.ini "$forge_home/.config/fuzzel/"
fuzzel --check-config --config "$forge_home/.config/fuzzel/fuzzel.ini"
for preset in overdrive redline icewire monolith sage ocean plum ember; do
    python -c 'import sys; from pathlib import Path; from forge.theme import PRESETS,render; Path.home().joinpath(".config/fuzzel/forge-colors.ini").write_text(render(PRESETS[sys.argv[1]])[".config/fuzzel/forge-colors.ini"])' "$preset"
    fuzzel --check-config --config "$forge_home/.config/fuzzel/fuzzel.ini"
done
