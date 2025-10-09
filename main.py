import time
import ctypes
import logging
from ctypes import wintypes
from typing import List, Optional, Callable
from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox 
from PIL import ImageTk, ImageGrab
import json
from pathlib import Path
import argparse
import os

try:
    import psutil
except ImportError:
    raise SystemExit("Missing dependency: install with 'pip install psutil'")

try:
    import cv2
    import numpy as np
except ImportError:
    raise SystemExit("Missing dependency: install with 'pip install opencv-python numpy'")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tlopo_bot.log'),
        logging.StreamHandler()
    ]
)

LOG_FILE = 'tlopo_bot.log'
MAX_LINES = 10000

def clear_log_file():
    """Clear the log file at the start of each run."""
    with open(LOG_FILE, 'w') as f:
        f.write('')  # Clear the file

def manage_log_file():
    """Manage the log file to ensure it does not exceed MAX_LINES."""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        
        if len(lines) >= MAX_LINES:
            with open(LOG_FILE, 'w') as f:
                f.writelines(lines[-MAX_LINES:])  # Keep the last MAX_LINES

def log_message(message):
    """Log a message to the log file."""
    with open(LOG_FILE, 'a') as f:
        f.write(message + '\n')

@dataclass
class WindowsConstants:
    """Windows API constants"""
    WM_KEYDOWN: int = 0x0100
    WM_KEYUP: int = 0x0101
    VK_CONTROL: int = 0x11
    VK_SHIFT: int = 0x10
    VK_ESCAPE: int = 0x1B

class WindowsAPI:
    """Windows API function wrapper"""
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self._setup_api_functions()

    def _setup_api_functions(self):
        # Setup EnumWindows
        self.EnumWindows = self.user32.EnumWindows
        self.EnumWindows.argtypes = [
            ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM),
            wintypes.LPARAM
        ]
        self.EnumWindows.restype = wintypes.BOOL

        # Setup GetWindowThreadProcessId
        self.GetWindowThreadProcessId = self.user32.GetWindowThreadProcessId
        self.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.GetWindowThreadProcessId.restype = wintypes.DWORD

        # Setup other functions
        self.IsWindowVisible = self.user32.IsWindowVisible
        self.PostMessageW = self.user32.PostMessageW
        self.MapVirtualKeyW = self.user32.MapVirtualKeyW

class TLOPOWindow:
    """TLOPO Window handler"""
    def __init__(self):
        self.win_api = WindowsAPI()
        self.constants = WindowsConstants()
        
    def iter_process_windows(self, target_pid: int) -> List[int]:
        """Find all visible windows for a given process ID"""
        targets: List[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd: int, lparam: int) -> bool:
            if not self.win_api.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD(0)
            self.win_api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                targets.append(hwnd)
            return True

        self.win_api.EnumWindows(callback, 0)
        return targets

    def find_game_window(self) -> Optional[int]:
        """Find the TLOPO game window"""
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name == "tlopo.exe":
                    hwnds = self.iter_process_windows(proc.info["pid"])
                    if hwnds:
                        return hwnds[0]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def make_lparam(self, vk: int, key_up: bool) -> int:
        """Create LPARAM for key messages"""
        scan_code = self.win_api.MapVirtualKeyW(vk, 0)
        lparam = 1 | (scan_code << 16)
        if key_up:
            lparam |= (1 << 30) | (1 << 31)
        return lparam

    def post_key(self, hwnd: int, vk: int, down: bool) -> None:
        """Post a key message to the window"""
        msg = self.constants.WM_KEYDOWN if down else self.constants.WM_KEYUP
        self.win_api.PostMessageW(hwnd, msg, vk, self.make_lparam(vk, not down))

    def press_and_hold(self, hwnd: int, vk: int, seconds: float) -> None:
        """Press and hold a key for specified duration"""
        self.post_key(hwnd, vk, True)
        time.sleep(seconds)
        self.post_key(hwnd, vk, False)

class TLOPOBot:
    """Main bot logic"""
    def __init__(self):
        clear_log_file()  # Clear log at the start
        manage_log_file()  # Manage log file size
        self.window = TLOPOWindow()
        self.constants = WindowsConstants()
        self.loot_detector = LootDetector()
        
    def run(self, force_calibrate: bool = False):
        """Main bot loop"""
        logging.info("Starting TLOPO Bot - Press Ctrl+C to stop")
        
        try:
            self.loot_detector.calibrate(force=force_calibrate)
        except ValueError as e:
            logging.error(f"Calibration failed: {e}")
            return
            
        iteration = 0

        while True:
            try:
                hwnd = self.window.find_game_window()
                if not hwnd:
                    logging.warning("TLOPO window not found, retrying in 1.0s")
                    time.sleep(1.0)
                    continue

                iteration += 1
                logging.info(f"Starting iteration #{iteration}")

                # Execute key sequence
                self.execute_key_sequence(hwnd)

            except Exception as e:
                logging.error(f"Error in bot loop: {e}")
                time.sleep(1.0)

    def execute_key_sequence(self, hwnd: int):
        """Execute the predefined key sequence"""
        # Press and release CTRL every 1 second (do this 5 times)
        for i in range(5):
            logging.info(f"CTRL press/release #{i+1}")
            self.window.post_key(hwnd, self.constants.VK_CONTROL, True)
            time.sleep(0.1)  # Brief hold
            self.window.post_key(hwnd, self.constants.VK_CONTROL, False)
            time.sleep(1.0)  # Wait 1 second before next press

        # Press SHIFT more naturally (brief press)
        logging.info("Pressing SHIFT")
        self.window.post_key(hwnd, self.constants.VK_SHIFT, True)
        time.sleep(1)  # Brief hold
        self.window.post_key(hwnd, self.constants.VK_SHIFT, False)

        # Check if loot window is open
        if self.loot_detector.is_loot_window_open():
            logging.info("Loot window detected! Waiting 5 seconds before pressing ESC")
            time.sleep(5.0)  # Wait 5 seconds if the loot window is open
            logging.info("Pressing ESC to close the loot window")
            # Press ESC to close the loot window
            self.window.post_key(hwnd, self.constants.VK_ESCAPE, True)
            time.sleep(0.1)
            self.window.post_key(hwnd, self.constants.VK_ESCAPE, False)
            return True
        else:
            logging.info("No loot window detected, continuing cycle")
            return False

        # Optional delay before next iteration
        time.sleep(1.0)
        return False

class RegionSelector:
    """GUI tool for selecting screen regions"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        self.selection_made = False
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.selected_region = None

    def get_region(self, message="Select the region to monitor"):
        logging.info("Starting region selection...")
        
        messagebox.showinfo(
            "Region Selection", 
            message + "\n\n"
            "1. Click and drag to select the region\n"
            "2. Release mouse button to confirm\n"
            "3. Window will close automatically"
        )
        
        window = tk.Toplevel(self.root)
        window.attributes('-fullscreen', True, '-alpha', 0.3)
        window.configure(bg='grey')

        screenshot = ImageGrab.grab()
        photo = ImageTk.PhotoImage(screenshot)

        canvas = tk.Canvas(window, width=screenshot.width, height=screenshot.height)
        canvas.pack(fill='both', expand=True)
        canvas.create_image(0, 0, image=photo, anchor='nw')

        selection_rect = None

        def on_mouse_down(event):
            self.start_x = event.x
            self.start_y = event.y
            logging.debug(f"Mouse down at ({event.x}, {event.y})")

        def on_mouse_drag(event):
            nonlocal selection_rect
            if selection_rect:
                canvas.delete(selection_rect)
            selection_rect = canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline='red', width=2
            )

        def on_mouse_up(event):
            self.end_x = event.x
            self.end_y = event.y
            self.selected_region = (
                min(self.start_x, self.end_x),
                min(self.start_y, self.end_y),
                max(self.start_x, self.end_x),
                max(self.start_y, self.end_y)
            )
            self.selection_made = True
            logging.info(f"Region selected: {self.selected_region}")
            window.destroy()
            self.root.quit()

        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)

        window.mainloop()
        
        if self.selected_region:
            logging.info(f"Returning selected region: {self.selected_region}")
            return self.selected_region
        else:
            logging.warning("No region was selected!")
            return None

class LootDetector:
    def __init__(self):
        logging.info("Initializing LootDetector")
        self.config = Config()
        self.region = self.config.data.get('region')
        self.brightness_threshold = self.config.data.get('brightness_threshold', 150)
        self.min_bright_pixels = self.config.data.get('min_bright_pixels', 0.4)
        logging.info(f"Loaded config: region={self.region}, "
                    f"brightness_threshold={self.brightness_threshold}, "
                    f"min_bright_pixels={self.min_bright_pixels}")

    def calibrate(self, force: bool = False):
        """Let user select the region to monitor"""
        if self.region and not force:
            logging.info("Using saved calibration settings")
            return

        logging.info("Starting calibration process")
        selector = RegionSelector()
        self.region = selector.get_region(
            "Select the area where the loot chest UI appears.\n"
            "Click and drag to select the region."
        )
        
        if self.region:
            logging.info(f"Calibrated region: {self.region}")
            self._calibrate_thresholds()
            self._save_config()
        else:
            logging.error("No region selected during calibration")
            raise ValueError("Calibration failed - no region selected")

    def _save_config(self):
        """Save current configuration"""
        config_data = {
            'region': self.region,
            'brightness_threshold': self.brightness_threshold,
            'min_bright_pixels': self.min_bright_pixels
        }
        logging.info(f"Saving config: {config_data}")
        self.config.save(config_data)

    def _calibrate_thresholds(self):
        """Calibrate brightness thresholds"""
        # First message before chest closed measurement
        messagebox.showinfo(
            "Calibration Step 1", 
            "Make sure the loot chest is CLOSED.\n"
            "After clicking OK:\n"
            "1. The screen will clear\n"
            "2. Wait 3 seconds\n"
            "3. The system will capture baseline values"
        )
        
        # Give time for chest to be closed and UI to clear
        time.sleep(3)
        closed_brightness, closed_ratio = self.analyze_region_brightness()
        logging.info(f"Closed chest values - brightness: {closed_brightness}, ratio: {closed_ratio}")

        # Message before chest open measurement
        messagebox.showinfo(
            "Calibration Step 2",
            "Now:\n"
            "1. Open the loot chest\n"
            "2. Click OK when ready\n"
            "3. Wait 3 seconds\n"
            "4. The system will capture active state values"
        )
        
        # Give time for chest to be opened and UI to settle
        time.sleep(3)
        open_brightness, open_ratio = self.analyze_region_brightness()
        logging.info(f"Open chest values - brightness: {open_brightness}, ratio: {open_ratio}")
        
        # Set thresholds based on samples
        self.brightness_threshold = (closed_brightness + open_brightness) / 2
        self.min_bright_pixels = (closed_ratio + open_ratio) / 2
        
        logging.info(f"Calibrated thresholds - Brightness: {self.brightness_threshold:.2f}, "
                    f"Bright pixel ratio: {self.min_bright_pixels:.2f}")

    def get_confidence_score(self, region: tuple = None) -> float:
        """
        Get the confidence score for template matching
        Returns: float between 0 and 1
        """
        # Capture screen or region
        if region:
            screenshot = ImageGrab.grab(bbox=region)
        else:
            screenshot = ImageGrab.grab()
        
        # Convert PIL image to CV2 format
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Perform template matching
        result = cv2.matchTemplate(
            screenshot, 
            self.template, 
            cv2.TM_CCOEFF_NORMED
        )
        
        # Get best match confidence
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        return max_val

    def is_loot_window_open(self) -> bool:
        """Check if loot window is open based on brightness analysis"""
        try:
            avg_brightness, bright_ratio = self.analyze_region_brightness()
            is_open = bright_ratio > self.min_bright_pixels
            
            logging.info(f"Loot check - brightness: {avg_brightness:.2f}, "
                        f"ratio: {bright_ratio:.2f}, threshold: {self.min_bright_pixels:.2f}, "
                        f"is_open: {is_open}")
            
            return is_open
            
        except Exception as e:
            logging.error(f"Error checking loot window: {e}")
            return False

    def analyze_region_brightness(self) -> tuple[float, float]:
        """
        Analyze brightness in the region
        Returns: (average_brightness, bright_pixel_ratio)
        """
        if not self.region:
            logging.error("No region set for brightness analysis")
            raise ValueError("Region not set")

        logging.debug(f"Analyzing brightness for region: {self.region}")
        screenshot = ImageGrab.grab(bbox=self.region)
        # Convert to grayscale using numpy for better performance
        gray_screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        gray_screen = cv2.cvtColor(gray_screen, cv2.COLOR_BGR2GRAY)
        
        # Calculate average brightness and ratio of bright pixels
        avg_brightness = np.mean(gray_screen)
        bright_pixels = np.sum(gray_screen > self.brightness_threshold)
        bright_ratio = bright_pixels / (gray_screen.shape[0] * gray_screen.shape[1])
        
        logging.debug(f"Brightness analysis - Avg: {avg_brightness:.2f}, Bright ratio: {bright_ratio:.2f}")
        return avg_brightness, bright_ratio

class Config:
    """Configuration manager for bot settings"""
    def __init__(self, filename: str = "bot_config.json"):
        self.filename = filename
        self.config_path = Path(filename)
        self.data = self._load_config()
        logging.info(f"Config initialized with path: {self.config_path.absolute()}")

    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    logging.info(f"Loading configuration from {self.filename}")
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"Error reading {self.filename}: {e}")
        return {}

    def save(self, data: dict):
        """Save configuration to JSON file"""
        try:
            # Convert tuples to lists for JSON serialization
            if 'region' in data and isinstance(data['region'], tuple):
                data['region'] = list(data['region'])
                
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)
            logging.info(f"Configuration saved to {self.filename}: {data}")
            self.data = data
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='TLOPO Bot')
    parser.add_argument('--recalibrate', action='store_true', 
                       help='Force recalibration of regions')
    args = parser.parse_args()

    bot = TLOPOBot()
    try:
        bot.run(force_calibrate=args.recalibrate)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")

if __name__ == "__main__":
    main()


