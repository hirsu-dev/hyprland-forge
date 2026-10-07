#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && -d /run/archiso ]] || { printf '%s\n' 'Run this from the official Arch Linux installation USB.'; exit 1; }
[[ "$EUID" -eq 0 ]] || { printf '%s\n' 'Run as root in the Arch live environment.'; exit 1; }
command -v archinstall >/dev/null || { printf '%s\n' 'archinstall is missing. Use a current official Arch ISO.'; exit 1; }
printf '%s\n' 'Hyprland Forge: Arch base installation' 'Choose your disks, encryption, bootloader and account in archinstall.' 'Select a minimal profile, a sudo-enabled user, and NetworkManager.' 'Add git and python to Additional packages.' 'Disk changes are performed only by archinstall after your selections.'
read -r -p 'Type ARCHINSTALL to open the installer: ' forge_answer
[[ "$forge_answer" == ARCHINSTALL ]] || exit 1
archinstall
printf '%s\n' 'After a successful Arch installation, reboot and sign in as your normal user.' 'Authenticate to your private GitHub repository, clone hyprland-forge, then run:' 'bash install.sh --plan' 'bash install.sh --apply'
