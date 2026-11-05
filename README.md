# Hyprland Forge

Hyprland Forge is a set of Arch Linux and Hyprland desktop configs, tools, and a Quickshell desktop panel. It is designed for an AMD/NVIDIA laptop with an external monitor.

The project includes a launcher, clipboard and screenshot tools, wallpaper controls, display settings, and theme controls. Its files are installed from the `configs/` folder, and the setup plan is listed in `project.json`.

## Status

The project has passed automated configuration and runtime checks in test environments. It has not yet been validated on the target physical computer, and it is not marked ready for daily use.

## Before you start

- You need an Arch Linux system with Hyprland.
- The setup installs packages and changes files in your home folder.
- Review the plan before applying it.
- Keep a backup of your existing configs.

## Install

Clone the repository, then run the installer in plan mode:

```sh
bash install.sh --plan
```

Review the planned packages and file changes. To apply the setup:

```sh
bash install.sh --apply
```

The live installer script is for the official Arch Linux USB only. Read it before use; Arch installation can change disks based on the choices made in `archinstall`.

## Main folders and files

- `configs/` — Hyprland, Quickshell, and desktop settings
- `forge/` — setup and desktop helper tools
- `tests/` — automated checks
- `project.json` — target system and setup plan
- `install.sh` — installer entry point
- `live.sh` — Arch live USB helper

Hardware support and daily-use readiness still need testing on the target computer.


## Build note: A coherent desktop is more than a color preset.

Forge brings a personal Arch/Hyprland desktop together: a Quickshell panel, launcher, display controls, clipboard and setup tools for an AMD/NVIDIA laptop.

Generate shared theme values for the shell, terminal and launcher from one palette, with bounded interface options and restore paths.

The portable theme suite ran on Windows / Python 3.12.14 on November 5, 2026: 19 passed, 2 skipped. This review did not start Hyprland or run the installer.

Next: Run the desktop on the target AMD/NVIDIA laptop and record display, suspend, scaling and restore behavior with an actual session screenshot.

[Read the tradeoff, evidence, and reproduction steps](docs/build-note.md).
