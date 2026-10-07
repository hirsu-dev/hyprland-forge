#!/usr/bin/env bash
set -euo pipefail
forge_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { printf '%s\n' 'Python is required: sudo pacman -S python'; exit 1; }
cd -- "$forge_root"
if [[ -f SHA256SUMS ]]; then
    command -v sha256sum >/dev/null || { printf '%s\n' 'sha256sum is required to verify this bundle.'; exit 1; }
    sha256sum --check --quiet SHA256SUMS || { printf '%s\n' 'Bundle integrity verification failed.'; exit 1; }
fi
exec python3 -m forge "$@"
