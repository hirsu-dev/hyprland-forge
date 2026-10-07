#!/usr/bin/env bash
set -euo pipefail
forge_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { printf '%s\n' 'Python is required: sudo pacman -S python'; exit 1; }
cd -- "$forge_root"
exec python3 -m forge "$@"
