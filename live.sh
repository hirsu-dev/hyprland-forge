#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && -d /run/archiso ]] || { printf '%s\n' 'Run this from the official Arch Linux installation USB.'; exit 1; }
[[ "$EUID" -eq 0 ]] || { printf '%s\n' 'Run as root in the Arch live environment.'; exit 1; }
forge_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$forge_root"
if [[ -f SHA256SUMS ]]; then
    sha256sum --check --quiet SHA256SUMS || { printf '%s\n' 'Bundle integrity verification failed.'; exit 1; }
fi
exec python3 -m forge.live "$@"
