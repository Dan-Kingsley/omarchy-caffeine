# Omarchy Caffeine

A system tray application for Omarchy (Wayland/Hyprland) that keeps your system awake and prevents automated locking.

![Caffeine Active](https://img.shields.io/badge/Status-Active-brightgreen)
![Caffeine Inactive](https://img.shields.io/badge/Status-Inactive-grey)

## Features

- **Tray Integration**: Adds a coffee cup icon to your Waybar tray.
- **Dynamic Icons**: Automatically generates icons using your current Omarchy theme's foreground color.
  - **Full Cup (Active)**: Caffeine is enabled. Screensaver and idle locking are disabled.
  - **Faded Cup (Inactive)**: Normal system behavior.
- **Automated Control**:
  - Disables `hypridle` to prevent automated screen locking and DPMS (screen off).
  - Manages Omarchy's internal screensaver toggle state.
  - Ensures the display stays on when activated.
- **Smart Theming**: Reads `@foreground` from `~/.config/omarchy/current/theme/waybar.css` to ensure icons match your desktop style perfectly.

## Requirements

- **Python 3** with `Pillow` (for icon generation) and `PyGObject` (`gi`).
- **Nerd Fonts**: Specifically `CaskaydiaMono Nerd Font`.
- **Hyprland** & **Hypridle**.
- **libappindicator-gtk3**: For the system tray menu.

## Installation

Run the provided installation script to set up the binary and the systemd user service:

```bash
chmod +x install.sh
./install.sh
```

This will:
1. Copy the script to `~/.local/share/omarchy/bin/omarchy-caffeine.py`.
2. Create and enable a systemd user service `omarchy-caffeine.service`.
3. Generate the initial set of themed icons in `~/.cache/omarchy-caffeine/icons`.

## Usage

- **Click** the coffee cup in the tray to open the menu.
- Select **Start** to enable Caffeine mode.
- Select **Stop** to return to normal idle behavior.
- Select **Close** to quit the application (the systemd service will restart it unless disabled).

## Technical Details

- **State File**: Uses `~/.local/state/omarchy/toggles/screensaver-off` to sync with Omarchy's screensaver logic.
- **Process Management**: Uses `uwsm-app` to restart `hypridle` cleanly when stopping caffeine.
- **Service**: Managed via `systemctl --user`.
