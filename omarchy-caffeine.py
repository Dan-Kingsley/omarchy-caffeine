#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib
import os
import subprocess
import json
import time
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
        self.timer_id = None
        self.timer_end_time = None
        
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
        
        # If marker missing (fresh boot) AND prev state file exists
        # This indicates we rebooted while Caffeine was active.
        # We don't just check for STATE_FILE because that might be a manual toggle.
        if not os.path.exists(boot_marker) and os.path.exists(PREV_STATE_FILE):
            print("Detected stale caffeine state after reboot. Reverting...")
            self.stop_caffeine(None)
            
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
            menu.append(item)

            if self.timer_end_time:
                remaining = int(self.timer_end_time - time.time())
                if remaining > 0:
                    if remaining >= 3600:
                        h = remaining // 3600
                        m = (remaining % 3600) // 60
                        s = remaining % 60
                        time_str = f"{h:02d}:{m:02d}:{s:02d}"
                    else:
                        m = remaining // 60
                        s = remaining % 60
                        time_str = f"{m:02d}:{s:02d}"
                    
                    time_item = Gtk.MenuItem(label=f"Time left: {time_str}")
                    time_item.set_sensitive(False)
                    menu.append(time_item)
        else:
            item = Gtk.MenuItem(label="Start")
            item.connect('activate', self.start_caffeine)
            menu.append(item)

            # Add Timer submenu
            timer_item = Gtk.MenuItem(label="Timer")
            timer_menu = Gtk.Menu()
            
            durations = [
                ("15m", 15 * 60),
                ("30m", 30 * 60),
                ("1h", 60 * 60),
                ("2h", 120 * 60),
                ("6h", 360 * 60),
            ]
            
            for label, seconds in durations:
                mi = Gtk.MenuItem(label=label)
                mi.connect('activate', lambda _, s=seconds, l=label: self.start_timer(s, l))
                timer_menu.append(mi)
            
            timer_item.set_submenu(timer_menu)
            menu.append(timer_item)
            
        item_close = Gtk.MenuItem(label="Close")
        item_close.connect('activate', self.quit)
        menu.append(item_close)
        
        menu.show_all()
        return menu

    def start_timer(self, seconds, label):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        
        self.start_caffeine(None, duration=label)
        self.timer_end_time = time.time() + seconds
        self.timer_id = GLib.timeout_add_seconds(seconds, self.stop_caffeine, None)

    def start_caffeine(self, _, duration=None):
        # 1. Save current state
        hypridle_running = subprocess.run(["pgrep", "-x", "hypridle"], 
                                        capture_output=True).returncode == 0
        state_file_existed = os.path.exists(STATE_FILE)
        
        os.makedirs(os.path.dirname(PREV_STATE_FILE), exist_ok=True)
        with open(PREV_STATE_FILE, 'w') as f:
            json.dump({
                "hypridle_running": hypridle_running,
                "state_file_existed": state_file_existed
            }, f)

        # 2. Disable screensaver via state file
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if not os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'w') as f:
                pass
            
        # 3. Stop hypridle (automated locking)
        subprocess.run(["pkill", "-x", "hypridle"], stderr=subprocess.DEVNULL)
        
        # 4. Ensure screen is on
        subprocess.run(["hyprctl", "dispatch", "dpms", "on"], stderr=subprocess.DEVNULL)
        
        self.update_state()
        
        msg = f"System will stay awake for {duration}" if duration else "System will stay awake"
        subprocess.run(["notify-send", "󰛟   Caffeine Enabled", msg])

    def stop_caffeine(self, _):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
            self.timer_id = None
        
        self.timer_end_time = None

        # 1. Default restore values (safety)
        should_restart_hypridle = True 
        should_exist_state_file = False
        
        # 2. Check previous state
        if os.path.exists(PREV_STATE_FILE):
            try:
                with open(PREV_STATE_FILE, 'r') as f:
                    prev = json.load(f)
                    should_restart_hypridle = prev.get("hypridle_running", True)
                    should_exist_state_file = prev.get("state_file_existed", False)
                os.remove(PREV_STATE_FILE)
            except Exception as e:
                print(f"Error reading previous state: {e}")

        # 3. Restore screensaver state file
        if should_exist_state_file:
            if not os.path.exists(STATE_FILE):
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                with open(STATE_FILE, 'w') as f: pass
        else:
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            
        # 4. Restore hypridle
        if should_restart_hypridle:
            # Only start if not already running
            hypridle_running = subprocess.run(["pgrep", "-x", "hypridle"], 
                                            capture_output=True).returncode == 0
            if not hypridle_running:
                subprocess.Popen(["uwsm-app", "--", "hypridle"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        self.update_state()
        subprocess.run(["notify-send", "   Caffeine Disabled", "System will lock normally" if not should_exist_state_file else "Screensaver remains disabled"])

    def quit(self, _):
        Gtk.main_quit()

    def run(self):
        Gtk.main()

if __name__ == "__main__":
    app = OmarchyCaffeine()
    app.run()
