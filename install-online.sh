#!/usr/bin/env bash
set -euo pipefail

repo="hrushikbarani-hub/hyprland-forge"
api="https://api.github.com/repos/$repo/releases?per_page=1"

if [[ ! -r /etc/os-release ]] || ! . /etc/os-release || [[ "${ID:-}" != arch ]]; then
    printf '%s\n' 'Hyprland Forge supports Arch Linux only.' >&2
    exit 1
fi
if [[ "$(uname -m)" != x86_64 ]]; then
    printf '%s\n' 'Hyprland Forge supports x86_64 systems only.' >&2
    exit 1
fi
for tool in curl python3 tar sha256sum; do
    command -v "$tool" >/dev/null || { printf 'Missing required command: %s\n' "$tool" >&2; exit 1; }
done

release_json="$(curl -fsSL --retry 2 --retry-delay 1 -H 'Accept: application/vnd.github+json' "$api")"
mapfile -t release_info < <(python3 -c 'import json,re,sys; d=json.load(sys.stdin); tag=d[0]["tag_name"]; assets={a["name"]:a for a in d[0]["assets"]}; name="hyprland-forge-"+tag.removeprefix("v")+".tar.gz"; digest=assets[name].get("digest",""); assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+",tag) and re.fullmatch(r"sha256:[0-9a-f]{64}",digest); print(tag); print(digest[7:])' <<< "$release_json")
if [[ "${#release_info[@]}" -ne 2 ]]; then
    printf '%s\n' 'Could not identify a valid Hyprland Forge release.' >&2
    exit 1
fi

tag="${release_info[0]}"
digest="${release_info[1]}"
archive="hyprland-forge-${tag#v}.tar.gz"
download="https://github.com/$repo/releases/download/$tag/$archive"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT

printf 'Downloading Hyprland Forge %s\n' "$tag"
curl -fL --retry 2 --retry-delay 1 "$download" -o "$work/$archive"
printf '%s  %s\n' "$digest" "$work/$archive" | sha256sum --check --status || {
    printf '%s\n' 'Release checksum verification failed.' >&2
    exit 1
}
mkdir "$work/unpacked"
tar -xzf "$work/$archive" -C "$work/unpacked"
if [[ ! -f "$work/unpacked/hyprland-forge/install.sh" ]]; then
    printf '%s\n' 'The release archive does not contain its installer.' >&2
    exit 1
fi

args=("$@")
has_mode=false
needs_tty=false
for arg in "${args[@]}"; do
    case "$arg" in
        --plan|--apply|--rollback|--doctor) has_mode=true ;;
    esac
    case "$arg" in
        --apply|--rollback) needs_tty=true ;;
    esac
done
if [[ "$has_mode" == false ]]; then
    args=(--apply "${args[@]}")
fi

if [[ "$needs_tty" == true ]]; then
    if [[ ! -r /dev/tty ]]; then
        printf '%s\n' 'Apply and rollback need an interactive terminal. Re-run the command from a terminal.' >&2
        exit 1
    fi
    bash "$work/unpacked/hyprland-forge/install.sh" "${args[@]}" </dev/tty
else
    bash "$work/unpacked/hyprland-forge/install.sh" "${args[@]}"
fi
