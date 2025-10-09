import time
import ctypes
import logging
from ctypes import wintypes
from typing import List, Optional, Callable
from dataclasses import dataclass

try:
    import psutil
except ImportError:
    raise SystemExit("Missing dependency: install with 'pip install psutil'")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tlopo_bot.log'),
        logging.StreamHandler()
    ]
)

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
        self.window = TLOPOWindow()
        self.constants = WindowsConstants()

    def run(self):
        """Main bot loop"""
        logging.info("Starting TLOPO Bot - Press Ctrl+C to stop")
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
        # Press and release CTRL every 1 second (do this 3 times)
        for i in range(5):
            logging.info(f"CTRL press/release #{i+1}")
            self.window.post_key(hwnd, self.constants.VK_CONTROL, True)
            time.sleep(0.1)  # Brief hold
            self.window.post_key(hwnd, self.constants.VK_CONTROL, False)
            time.sleep(1)  # Wait 1 second before next press

        # Hold SHIFT for 4 seconds
        logging.info("Holding SHIFT for 4.0s")
        self.window.press_and_hold(hwnd, self.constants.VK_SHIFT, 4.0)

        # Press and release ESC
        logging.info("Pressing ESC")
        self.window.post_key(hwnd, self.constants.VK_ESCAPE, True)
        self.window.post_key(hwnd, self.constants.VK_ESCAPE, False)

        # Optional delay before next iteration
        logging.info("Sequence complete, waiting 1.0s")
        time.sleep(1.0)

def main():
    bot = TLOPOBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")

if __name__ == "__main__":
    main()


