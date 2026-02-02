#!/bin/bash

# Create directories if they don't exist
mkdir -p ~/.local/share/omarchy/bin/
mkdir -p ~/.config/systemd/user/

# Copy the script
cp omarchy-caffeine.py ~/.local/share/omarchy/bin/
chmod +x ~/.local/share/omarchy/bin/omarchy-caffeine.py

# Copy the service
cp omarchy-caffeine.service ~/.config/systemd/user/

# Reload systemd and start the service
systemctl --user daemon-reload
systemctl --user enable --now omarchy-caffeine.service

echo "Omarchy Caffeine service has been installed and started."
echo "You should see a coffee cup in your Waybar tray."
