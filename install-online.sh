#!/usr/bin/env bash
set -euo pipefail

forge_admin() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    elif [[ "${use_su:-false}" != true ]] && command -v sudo >/dev/null; then
        sudo -- "$@"
    else
        local command_line
        printf -v command_line '%q ' "$@"
        su -s /bin/bash -c "$command_line" root
    fi
}

forge_online() {
    local repo='hirsu-dev/hyprland-forge' mode=setup arg answer release_json release_info tag digest archive work status use_su=false
    command -v sudo >/dev/null || use_su=true
    for arg in "$@"; do
        case "$arg" in
            --plan|--json|--doctor|--help|-h) mode=inspect ;;
            --setup|--apply|--rollback|--rollback=*) mode=install ;;
        esac
    done
    if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 || ! -f /etc/arch-release || ! -r /etc/os-release ]] || ! grep -Eq '^ID=(arch|"arch")$' /etc/os-release; then
        printf '%s\n' 'Forge needs x86_64 Arch Linux or the official Arch USB.' >&2
        return 1
    fi
    if [[ "$mode" != inspect && ! -t 0 ]]; then
        printf '%s\n' 'Open a terminal to run the interactive Forge installer.' >&2
        return 1
    fi
    if [[ "$mode" != inspect ]] && systemd-detect-virt --chroot >/dev/null 2>&1; then
        printf '%s\n' 'Run Forge from the Arch USB shell or boot installed Arch first; leave the target chroot.' >&2
        return 1
    fi
    if [[ "$mode" != inspect && -f /var/lib/pacman/db.lck ]]; then
        printf '%s\n' 'Another package operation is running. Retry when it finishes.' >&2
        return 1
    fi
    if ! command -v python3 >/dev/null || ! command -v curl >/dev/null || { [[ "$mode" != inspect && ! -d /run/archiso ]] && ! command -v sudo >/dev/null; }; then
        if [[ "$mode" == inspect ]]; then
            printf '%s\n' 'Python and curl are needed to inspect the release. Run without --plan to prepare them automatically.' >&2
            return 1
        fi
        printf '%s\n' 'Forge will update Arch and install its setup requirements.'
        read -r -p 'Continue? [Y/n] ' answer
        case "${answer,,}" in ''|y|yes) ;; *) return 0 ;; esac
        forge_admin pacman -Syu --needed --noconfirm -- python sudo curl
    fi
    for arg in curl python3 tar sha256sum; do
        command -v "$arg" >/dev/null || { printf 'Required command is missing: %s\n' "$arg" >&2; return 1; }
    done
    release_json="$(curl -fsSL --retry 2 -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$repo/releases?per_page=1")"
    release_info="$(python3 -c '
import json,re,sys
try:
    release=json.load(sys.stdin)[0]
    tag=release["tag_name"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+",tag):
        raise ValueError("invalid release version")
    name="hyprland-forge-"+tag[1:]+".tar.gz"
    asset=next(a for a in release["assets"] if a["name"]==name)
    digest=asset.get("digest","")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}",digest):
        raise ValueError("missing release checksum")
    print(tag, digest[7:])
except (ValueError,KeyError,IndexError,StopIteration,TypeError):
    sys.exit("Forge: no verified release is available. Retry later.")
' <<< "$release_json")"
    read -r tag digest <<< "$release_info"
    archive="hyprland-forge-${tag#v}.tar.gz"
    work="$(mktemp -d -t forge-download-XXXXXXXX)"
    printf 'Downloading Forge %s\n' "$tag"
    if ! curl -fsSL --retry 2 "https://github.com/$repo/releases/download/$tag/$archive" -o "$work/$archive"; then
        rm -r -- "$work"
        return 1
    fi
    if ! printf '%s  %s\n' "$digest" "$work/$archive" | sha256sum --check --status; then
        printf '%s\n' 'Release checksum verification failed.' >&2
        rm -r -- "$work"
        return 1
    fi
    mkdir "$work/unpacked"
    if ! tar -xzf "$work/$archive" -C "$work/unpacked"; then
        rm -r -- "$work"
        return 1
    fi
    if [[ ! -f "$work/unpacked/hyprland-forge/install.sh" ]]; then
        printf '%s\n' 'The release does not contain an installer.' >&2
        rm -r -- "$work"
        return 1
    fi
    chmod 755 "$work" "$work/unpacked"
    chmod -R a+rX "$work/unpacked/hyprland-forge"
    status=0
    if [[ "$mode" == setup ]]; then
        set -- --setup "$@"
    fi
    if [[ -d /run/archiso && "$mode" != inspect ]]; then
        bash "$work/unpacked/hyprland-forge/live.sh" || status=$?
    elif [[ "$use_su" == true && $EUID -ne 0 && "$mode" != inspect ]]; then
        ( cd "$work/unpacked/hyprland-forge"; forge_admin python3 -m forge.bootstrap "$@" ) || status=$?
    else
        bash "$work/unpacked/hyprland-forge/install.sh" "$@" || status=$?
    fi
    rm -r -- "$work"
    return "$status"
}

if [[ -t 0 ]]; then
    forge_online "$@"
elif ( : </dev/tty ) 2>/dev/null; then
    forge_online "$@" </dev/tty
else
    forge_online "$@"
fi
