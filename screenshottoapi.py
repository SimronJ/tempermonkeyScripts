# filepath: e:\github_clone\Tlopo_Boss_AutoFarm\screenshottoapi.py
import os
import time
import json
import logging
import requests
import pyautogui
import keyboard
import psutil
import shutil  # NEW
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Win32 focus helpers
import win32gui
import win32process
import win32con

# -------------------- Config --------------------
load_dotenv()
API_URL = os.getenv("API_URL")

PROCESS_NAME = "tlopo.exe"

# Detection thresholds
ENEMY_CLASS = "enemy"
ENEMY_CONFIDENCE_THRESHOLD = 0.8
LEGENDARY_CLASS = "legendary"
LEGENDARY_MIN_CONF = 0.1
FAME_CLASS = "fame"
FAME_MIN_CONF = 0.2
SS_CLASS = "ss"
SS_MIN_CONF = 0.2

# Timings
API_POLL_INTERVAL = 5.0         # seconds between main polls
CTRL_PRESS_INTERVAL = 1.0       # seconds between ctrl presses while enemy present
LOOT_RECHECK_DELAY = 3.0        # wait after first loot click before re-check  # (kept but no longer used)
MAINT_INTERVAL = 120.0          # periodic Esc+Ctrl (every 2 minutes)
LOOT_KEEP_OPEN = 2.0            # keep chest open for 2s

# No-enemy fallback
ENEMY_ABSENCE_CTRL_THRESHOLD = 5  # press Ctrl if no enemy for N polls

# Files
SCREENSHOT_FILENAME = "screenshot.png"
LABELED_FILENAME = "labeled_screenshot.png"
STATE_FILE = "state.json"
CHEST_SHOT_DIR = "chestScreenShot"  # NEW

# Drawing
FONT_SIZE = 24
CLASS_COLORS = {
    ENEMY_CLASS: 'green',
    'LootTakeButton': 'blue',
    'LootExitIcon': 'orange',
    'TrashIcon': 'purple',
    LEGENDARY_CLASS: 'gold',
    FAME_CLASS: 'cyan',
    SS_CLASS: 'magenta',
}

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("tlopo-bot")

if not API_URL:
    logger.error("API_URL not found in .env")
    raise SystemExit(1)

# -------------------- Window focus helpers --------------------
def _enum_windows_for_pid(pid):
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
            if w_pid == pid:
                result.append(hwnd)
    win32gui.EnumWindows(callback, None)
    return result

def find_tlopo_hwnd():
    for p in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if p.info["name"] and p.info["name"].lower() == PROCESS_NAME.lower():
                hwnds = _enum_windows_for_pid(p.info["pid"])
                if hwnds:
                    logger.info(f"Found tlopo.exe window: hwnd={hwnds[0]}")
                    return hwnds[0]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    logger.warning("tlopo.exe window not found")
    return None

def focus_hwnd(hwnd):
    try:
        # Only restore if minimized to avoid window size changes
        if win32gui.IsIconic(hwnd):
            logger.info("Window is minimized; restoring")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Do not force ShowWindow for normal/maximized windows to prevent resize
        win32gui.SetForegroundWindow(hwnd)
        logger.info("Focused tlopo.exe window")
        return True
    except Exception as e:
        logger.debug(f"Focus failed: {e}")
        return False

# -------------------- Bot --------------------
class GameBot:
    def __init__(self):
        self.last_api_time = 0.0
        self.last_ctrl_time = 0.0
        self.last_maint_time = 0.0
        self.enemy_active = False
        self.hwnd = None
        self.state = self.load_state()
        # Ensure state file exists immediately
        self.save_state()
        logger.info(f"State loaded: bosses_defeated={self.state['bosses_defeated']} chests_opened={self.state['chests_opened']}")

        self.no_enemy_count = 0   # NEW: consecutive no-enemy polls counter

    # ---------- State ----------
    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return {
                    "bosses_defeated": int(d.get("bosses_defeated", 0)),
                    "chests_opened": int(d.get("chests_opened", 0)),
                    "last_updated": d.get("last_updated", "")
                }
            except Exception as e:
                logger.warning(f"Failed to read {STATE_FILE}: {e}")
        logger.info("State file not found; initializing new state")
        return {"bosses_defeated": 0, "chests_opened": 0, "last_updated": ""}

    def save_state(self):
        self.state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            logger.info(f"State saved: bosses_defeated={self.state['bosses_defeated']} chests_opened={self.state['chests_opened']}")
        except Exception as e:
            logger.error(f"Failed to write {STATE_FILE}: {e}")

    # ---------- Focused inputs ----------
    def ensure_focus(self):
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            self.hwnd = find_tlopo_hwnd()
        if self.hwnd:
            return focus_hwnd(self.hwnd)
        return False

    def press_key(self, key, reason=None):
        if self.ensure_focus():
            try:
                pyautogui.press(key)
                if reason:
                    logger.info(f"Pressed key '{key}' - reason: {reason}")
                else:
                    logger.info(f"Pressed key '{key}'")
                return True
            except Exception as e:
                logger.error(f"Key press failed ({key}): {e}")
        else:
            logger.warning(f"Skipped key '{key}' - tlopo window not focused/found")
        return False

    def click_center(self, cx, cy, label="click"):
        if self.ensure_focus():
            try:
                x, y = int(cx), int(cy)
                pyautogui.click(x, y)
                logger.info(f"Click '{label}' at ({x}, {y})")
                return True
            except Exception as e:
                logger.error(f"Click failed at ({cx},{cy}): {e}")
        else:
            logger.warning(f"Skipped click '{label}' - tlopo window not focused/found")
        return False

    # ---------- Vision ----------
    def take_screenshot(self):
        logger.info("Capturing screenshot")
        shot = pyautogui.screenshot()
        shot.save(SCREENSHOT_FILENAME)
        return shot

    def analyze(self):
        try:
            img = Image.open(SCREENSHOT_FILENAME)
            width, height = img.size
            logger.info(f"Sending screenshot to API (size={width}x{height})")
            t0 = time.perf_counter()
            with open(SCREENSHOT_FILENAME, "rb") as f:
                resp = requests.post(API_URL, files={"file": f}, timeout=10)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if resp.status_code != 200:
                logger.warning(f"API {resp.status_code} in {elapsed:.1f} ms: {resp.text[:200]}")
                img.close()
                return []
            data = resp.json()
            preds = data.get("predictions", [])
            logger.info(f"API ok in {elapsed:.1f} ms - detections={len(preds)}")
            # labeled image
            labeled = self.draw_detections(img.copy(), preds)
            labeled.save(LABELED_FILENAME)
            img.close()
            logger.info("Updated labeled_screenshot.png")
            return preds
        except Exception as e:
            logger.error(f"Analyze error: {e}")
            return []

    def draw_detections(self, image, predictions):
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", FONT_SIZE)
        except OSError:
            font = ImageFont.load_default()

        for p in predictions:
            cls = p.get('class', '')
            color = CLASS_COLORS.get(cls, 'yellow')
            cx = int(p.get('x', 0))
            cy = int(p.get('y', 0))
            w = int(p.get('width', 0))
            h = int(p.get('height', 0))
            x1, y1 = cx - w // 2, cy - h // 2
            x2, y2 = cx + w // 2, cy + h // 2

            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            conf = p.get('confidence', 0.0) * 100
            label = f"{cls} ({conf:.1f}%)"
            try:
                bbox = draw.textbbox((x1, max(0, y1 - 28)), label, font=font)
                draw.rectangle(bbox, fill="black")
            except Exception:
                pass
            draw.text((x1, max(0, y1 - 28)), label, fill="#FF0000", font=font)
        return image

    # ---------- Filters ----------
    def have_enemy(self, preds):
        enemies = [p for p in preds if p.get('class') == ENEMY_CLASS and p.get('confidence', 0.0) >= ENEMY_CONFIDENCE_THRESHOLD]
        if enemies:
            top_conf = max(p['confidence'] for p in enemies) * 100
            logger.info(f"Enemy present - count={len(enemies)} top_conf={top_conf:.1f}%")
        else:
            logger.info("No enemy present")
        return len(enemies) > 0

    def find_first(self, preds, cls_name):
        for p in preds:
            if p.get('class') == cls_name:
                return p
        return None

    def find_items(self, preds):
        has_legendary = any(p.get('class') == LEGENDARY_CLASS and p.get('confidence', 0.0) >= LEGENDARY_MIN_CONF for p in preds)
        has_fame = any(p.get('class') == FAME_CLASS and p.get('confidence', 0.0) >= FAME_MIN_CONF for p in preds)
        ss_obj = next((p for p in preds if p.get('class') == SS_CLASS and p.get('confidence', 0.0) >= SS_MIN_CONF), None)
        if has_legendary or has_fame or ss_obj:
            logger.info(f"Items detected - legendary>={LEGENDARY_MIN_CONF}, fame>={FAME_MIN_CONF}, ss>={SS_MIN_CONF}: "
                        f"legendary={has_legendary} fame={has_fame} ss={'yes' if ss_obj else 'no'}")
        else:
            logger.info("No target items detected")
        return has_legendary, has_fame, ss_obj

    # ---------- Main loop ----------
    def run(self):
        logger.info("Starting bot. Press 'q' to quit.")
        # Initial poll
        self.take_screenshot()
        preds = self.analyze()
        self.last_api_time = time.time()
        self.enemy_active = self.have_enemy(preds)

        last_loot_btn_center = None
        last_loot_btn_conf = None
        last_trash_conf = None

        while True:
            if keyboard.is_pressed('q'):
                logger.info("Quit requested.")
                break

            now = time.time()

            # Press Ctrl every second while enemy is active (based on last poll)
            if self.enemy_active and (now - self.last_ctrl_time) >= CTRL_PRESS_INTERVAL:
                self.press_key('ctrl', reason="enemy active - attack tick")
                self.last_ctrl_time = now

            # Periodic maintenance keys (Esc then Ctrl)
            if (now - self.last_maint_time) >= MAINT_INTERVAL:
                logger.info("Maintenance keys: Esc then Ctrl")
                self.press_key('esc', reason="maintenance")
                time.sleep(0.1)
                self.press_key('ctrl', reason="maintenance")
                self.last_maint_time = now

            # Poll API on interval
            if (now - self.last_api_time) >= API_POLL_INTERVAL:
                self.take_screenshot()
                preds = self.analyze()
                self.last_api_time = now

                enemy_now = self.have_enemy(preds)

                # Transition: enemy defeated
                if self.enemy_active and not enemy_now:
                    self.state["bosses_defeated"] += 1
                    self.save_state()
                    logger.info(f"Enemy defeated. Total bosses_defeated={self.state['bosses_defeated']}")
                    self.press_key('shift', reason="post-fight")

                self.enemy_active = enemy_now

                # Track no-enemy streak and press Ctrl if threshold reached
                if not self.enemy_active:
                    self.no_enemy_count += 1
                    logger.info(f"No-enemy streak: {self.no_enemy_count}/{ENEMY_ABSENCE_CTRL_THRESHOLD}")
                    if self.no_enemy_count >= ENEMY_ABSENCE_CTRL_THRESHOLD:
                        self.press_key('ctrl', reason=f"no enemy for {self.no_enemy_count} polls")
                        self.no_enemy_count = 0
                else:
                    if self.no_enemy_count:
                        logger.info("Enemy detected again, resetting no-enemy streak")
                    self.no_enemy_count = 0

                # If no enemy, handle loot (reuse preds)
                if not self.enemy_active:
                    loot_btn = self.find_first(preds, 'LootTakeButton')
                    trash_icon = self.find_first(preds, 'TrashIcon')

                    if loot_btn and trash_icon:
                        # Log confidences
                        last_loot_btn_conf = loot_btn.get('confidence', 0.0) * 100
                        last_trash_conf = trash_icon.get('confidence', 0.0) * 100
                        logger.info(f"Chest open detected: LootTakeButton conf={last_loot_btn_conf:.1f}%, "
                                    f"TrashIcon conf={last_trash_conf:.1f}%")

                        # Determine items (using current preds)
                        has_legendary, has_fame, ss_obj = self.find_items(preds)
                        is_special = has_legendary or has_fame

                        # Archive labeled screenshot
                        try:
                            os.makedirs(CHEST_SHOT_DIR, exist_ok=True)
                            ts = time.strftime("%Y%m%d_%H%M%S")
                            base = "special" if is_special else "noSpecial"
                            target_path = os.path.join(CHEST_SHOT_DIR, f"{base}_{ts}.png")
                            shutil.copyfile(LABELED_FILENAME, target_path)
                            logger.info(f"Archived chest screenshot: {target_path}")
                        except Exception as e:
                            logger.warning(f"Failed to archive chest screenshot: {e}")

                        # Click LootTakeButton once
                        lx, ly = int(loot_btn['x']), int(loot_btn['y'])
                        last_loot_btn_center = (lx, ly)
                        logger.info(f"Clicking LootTakeButton (conf={last_loot_btn_conf:.1f}%)")
                        self.click_center(lx, ly, label="LootTakeButton")

                        # If ss detected, click its center once
                        if ss_obj:
                            logger.info(f"SS detected (conf={ss_obj.get('confidence',0.0)*100:.1f}%) - clicking SS")
                            self.click_center(ss_obj['x'], ss_obj['y'], label="Select SS")

                        # Keep chest open for 2 seconds
                        logger.info(f"Holding chest open for {LOOT_KEEP_OPEN:.1f}s")
                        time.sleep(LOOT_KEEP_OPEN)

                        # If no special items, click TrashIcon
                        if not is_special:
                            logger.info(f"No special items; clicking TrashIcon (conf={last_trash_conf:.1f}%)")
                            self.click_center(trash_icon['x'], trash_icon['y'], label="TrashIcon")
                        else:
                            logger.info("Special item detected (fame/legendary); skipping TrashIcon")

                        # Update state
                        self.state["chests_opened"] += 1
                        self.save_state()
                        logger.info(f"Chest handled. Total chests_opened={self.state['chests_opened']}")

            time.sleep(0.05)  # prevent busy-wait

        logger.info("Bot stopped.")
        logger.info(f"Final state: bosses_defeated={self.state['bosses_defeated']} chests_opened={self.state['chests_opened']}")

if __name__ == "__main__":
    bot = GameBot()
    bot.run()