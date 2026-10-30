#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -s) == Linux && $EUID == 0 && -f /etc/arch-release ]] || { printf '%s\n' 'Build the ISO as root inside an Arch Linux build environment.' >&2; exit 1; }
[[ $# == 3 ]] || { printf '%s\n' 'Usage: bash iso/build.sh CALAMARES_PACKAGE NEW_WORK_DIRECTORY OUTPUT_DIRECTORY' >&2; exit 1; }
forge_source=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python -c 'import json,sys; state=json.load(open(sys.argv[1])); sys.exit(0 if state.get("build_enabled") is True else "The experimental ISO is incomplete. Building is disabled until its installer and live session are verified.")' "$forge_source/iso/state.json"
[[ -z $(git -c safe.directory="$forge_source" -C "$forge_source" status --porcelain) ]] || { printf '%s\n' 'Commit the ISO source before building.' >&2; exit 1; }
forge_package=$(realpath -- "$1")
forge_work=$(realpath -m -- "$2")
forge_output=$(realpath -m -- "$3")
[[ -f "$forge_package" && ! -e "$forge_work" && "$forge_work" != / && "$forge_output" != "$forge_work" && "$forge_output" != "$forge_work/"* ]] || exit 1
mkdir -p -- "$forge_work" "$forge_output"
cp -a /usr/share/archiso/configs/releng "$forge_work/profile"
mkdir -p "$forge_work/repository"
cp -- "$forge_package" "$forge_work/repository/"
repo-add "$forge_work/repository/forge.db.tar.gz" "$forge_work/repository/"*.pkg.tar.zst
python "$forge_source/iso/prepare.py" "$forge_source" "$forge_work/profile" "$forge_work/repository"
mkarchiso -v -w "$forge_work/mkarchiso" -o "$forge_output" "$forge_work/profile"
cd -- "$forge_output"
sha256sum -- ./*.iso > SHA256SUMS
pacman -Q > build-packages.txt
