import time
import ctypes
from ctypes import wintypes

try:
    import psutil
except ImportError:
    raise SystemExit("Missing dependency: install with 'pip install psutil'")


# Win32 constants
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_ESCAPE = 0x1B


# Win32 bindings
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
EnumWindows.restype = wintypes.BOOL

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
PostMessageW.restype = wintypes.BOOL

MapVirtualKeyW = user32.MapVirtualKeyW
MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
MapVirtualKeyW.restype = wintypes.UINT


def iter_process_windows(target_pid: int):
    targets: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, lparam: int) -> bool:
        if not IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == target_pid:
            targets.append(hwnd)
        return True

    EnumWindows(callback, 0)
    return targets


def find_tlopo_hwnd() -> int | None:
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name == "tlopo.exe":
                hwnds = iter_process_windows(proc.info["pid"])  # visible top-level windows
                if hwnds:
                    return hwnds[0]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def make_lparam(vk: int, key_up: bool) -> int:
    scan_code = MapVirtualKeyW(vk, 0)
    lparam = 1 | (scan_code << 16)
    if key_up:
        lparam |= (1 << 30) | (1 << 31)  # previous down + transition state
    return lparam


def post_key(hwnd: int, vk: int, down: bool) -> None:
    msg = WM_KEYDOWN if down else WM_KEYUP
    PostMessageW(hwnd, msg, vk, make_lparam(vk, key_up=not down))


def press_and_hold_hwnd(hwnd: int, vk: int, seconds: float) -> None:
    post_key(hwnd, vk, True)
    time.sleep(seconds)
    post_key(hwnd, vk, False)


def main() -> None:
    def now_ts() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    print("Background loop targeting tlopo.exe window: Ctrl 2s -> Shift 3s -> Esc -> wait 5s (Ctrl+C to stop)")
    iteration = 0
    while True:
        hwnd = find_tlopo_hwnd()
        if not hwnd:
            print(f"[{now_ts()}] tlopo.exe window not found; retrying in 1.0s")
            time.sleep(1.0)
            continue

        iteration += 1
        print(f"[{now_ts()}] Loop #{iteration} start")

        print(f"[{now_ts()}] Holding CTRL for 2.0s")
        press_and_hold_hwnd(hwnd, VK_CONTROL, 2.0)

        print(f"[{now_ts()}] Holding SHIFT for 3.0s")
        press_and_hold_hwnd(hwnd, VK_SHIFT, 3.0)

        print(f"[{now_ts()}] Pressing ESC")
        post_key(hwnd, VK_ESCAPE, True)
        post_key(hwnd, VK_ESCAPE, False)

        print(f"[{now_ts()}] Sleeping 5.0s")
        time.sleep(5.0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")


