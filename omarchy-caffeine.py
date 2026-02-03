#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

# Path configuration
STATE_FILE = os.path.expanduser("~/.local/state/omarchy/toggles/screensaver-off")
PREV_STATE_FILE = os.path.expanduser("~/.local/state/omarchy/toggles/screensaver-prev-state")
ICON_DIR = os.path.expanduser("~/.cache/omarchy-caffeine/icons")
FONT_PATH = "/usr/share/fonts/TTF/CaskaydiaMonoNerdFont-Regular.ttf"
THEME_FILE = os.path.expanduser("~/.config/omarchy/current/theme/waybar.css")

# Icons from Nerd Font
# Using the same coffee cup icon for both to ensure consistency
COFFEE_CUP_CHAR = "\uf0f4"

class OmarchyCaffeine:
    def __init__(self):
        os.makedirs(ICON_DIR, exist_ok=True)
        self.icon_empty = os.path.join(ICON_DIR, "coffee-empty.png")
        self.icon_full = os.path.join(ICON_DIR, "coffee-full.png")
        
        self.color = self.get_theme_color()
        self.ensure_icons()
        
        # Check for stale state on reboot
        self.check_boot_state()
        
        # Initial indicator setup
        self.indicator = AppIndicator3.Indicator.new(
            "omarchy-caffeine",
            self.icon_empty,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        
        # Initial state update
        self.update_state()
        
        # Periodic check to sync with external changes
        GLib.timeout_add_seconds(2, self.update_state)

    def check_boot_state(self):
        """Check if we rebooted with caffeine on and restore state"""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        boot_marker = os.path.join(runtime_dir, "omarchy-caffeine.lock")
        
        # If marker missing (fresh boot) but state file exists (stale)
        if not os.path.exists(boot_marker) and os.path.exists(STATE_FILE):
            print("Detected stale caffeine state after reboot. Reverting...")
            
            # Restore hypridle if it was supposed to be running
            should_restore = True # Default to True for safety (consistent with stop_caffeine)
            if os.path.exists(PREV_STATE_FILE):
                try:
                    with open(PREV_STATE_FILE, 'r') as f:
                        should_restore = (f.read().strip() == "true")
                    os.remove(PREV_STATE_FILE)
                except Exception as e:
                    print(f"Error reading prev state: {e}")
            
            # Only start if not already running
            hypridle_running = subprocess.run(["pgrep", "-x", "hypridle"], 
                                            capture_output=True).returncode == 0
            
            if should_restore and not hypridle_running:
                print("Restoring hypridle...")
                subprocess.Popen(["uwsm-app", "--", "hypridle"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Remove the stale lock file
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            
            # Also clean up prev state file if it still exists (e.g. if reading failed)
            if os.path.exists(PREV_STATE_FILE):
                os.remove(PREV_STATE_FILE)
            
        # Create marker for this boot session
        try:
            with open(boot_marker, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            print(f"Could not create boot marker: {e}")

    def get_theme_color(self):
        """Try to extract @foreground color from omarchy theme"""
        default_color = (87, 82, 121, 255) # #575279
        color = default_color
        if not os.path.exists(THEME_FILE):
            print(f"Theme file not found at {THEME_FILE}, using default color")
            return default_color
            
        try:
            with open(THEME_FILE, 'r') as f:
                content = f.read()
                # Look for @define-color foreground #XXXXXX;
                import re
                match = re.search(r'@define-color\s+foreground\s+#([0-9a-fA-F]{6});', content)
                if match:
                    hex_color = match.group(1)
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    color = (r, g, b, 255)
                    print(f"Found theme color: #{hex_color} -> {color}")
                else:
                    print("Could not find foreground color in theme file, using default")
        except Exception as e:
            print(f"Error reading theme color: {e}")
            
        return color

    def ensure_icons(self):
        # Full cup: Normal theme color
        self.generate_icon(COFFEE_CUP_CHAR, self.icon_full, self.color)
        
        # Empty cup: Same icon, but 30% opacity (faint)
        empty_color = (self.color[0], self.color[1], self.color[2], 75)
        self.generate_icon(COFFEE_CUP_CHAR, self.icon_empty, empty_color)

    def generate_icon(self, char, path, fill_color):
        size = 64
        image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        
        try:
            font = ImageFont.truetype(FONT_PATH, 52)
        except Exception:
            font = ImageFont.load_default()
            
        # Center the icon
        bbox = draw.textbbox((0, 0), char, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), 
                  char, font=font, fill=fill_color)
        
        image.save(path)

    def is_active(self):
        # Active if screensaver-off file exists AND hypridle is NOT running
        screensaver_off = os.path.exists(STATE_FILE)
        hypridle_running = subprocess.run(["pgrep", "-x", "hypridle"], 
                                         capture_output=True).returncode == 0
        return screensaver_off and not hypridle_running

    def update_state(self):
        active = self.is_active()
        if active:
            self.indicator.set_icon_full(self.icon_full, "Caffeine Active")
        else:
            self.indicator.set_icon_full(self.icon_empty, "Caffeine Inactive")
        
        self.indicator.set_menu(self.build_menu(active))
        return True

    def build_menu(self, active):
        menu = Gtk.Menu()
        
        if active:
            item = Gtk.MenuItem(label="Stop")
            item.connect('activate', self.stop_caffeine)
        else:
            item = Gtk.MenuItem(label="Start")
            item.connect('activate', self.start_caffeine)
            
        menu.append(item)
        
        item_close = Gtk.MenuItem(label="Close")
        item_close.connect('activate', self.quit)
        menu.append(item_close)
        
        menu.show_all()
        return menu

    def start_caffeine(self, _):
        # 1. Save current hypridle state
        hypridle_running = subprocess.run(["pgrep", "-x", "hypridle"], 
                                        capture_output=True).returncode == 0
        
        os.makedirs(os.path.dirname(PREV_STATE_FILE), exist_ok=True)
        with open(PREV_STATE_FILE, 'w') as f:
            f.write("true" if hypridle_running else "false")

        # 2. Disable screensaver via state file
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            pass
            
        # 3. Stop hypridle (automated locking)
        subprocess.run(["pkill", "-x", "hypridle"], stderr=subprocess.DEVNULL)
        
        # 4. Ensure screen is on
        subprocess.run(["hyprctl", "dispatch", "dpms", "on"], stderr=subprocess.DEVNULL)
        
        self.update_state()
        subprocess.run(["notify-send", "󰛟   Caffeine Enabled", "System will stay awake"])

    def stop_caffeine(self, _):
        # 1. Enable screensaver
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            
        # 2. Check previous state and restart hypridle if needed
        should_restart = True # Default to restarting if no state file found (safety)
        
        if os.path.exists(PREV_STATE_FILE):
            try:
                with open(PREV_STATE_FILE, 'r') as f:
                    state = f.read().strip()
                    should_restart = (state == "true")
                os.remove(PREV_STATE_FILE)
            except Exception as e:
                print(f"Error reading previous state: {e}")
        
        if should_restart:
            # Restart hypridle
            subprocess.Popen(["uwsm-app", "--", "hypridle"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        self.update_state()
        subprocess.run(["notify-send", "   Caffeine Disabled", "System will lock normally"])

    def quit(self, _):
        Gtk.main_quit()

    def run(self):
        Gtk.main()

if __name__ == "__main__":
    app = OmarchyCaffeine()
    app.run()
