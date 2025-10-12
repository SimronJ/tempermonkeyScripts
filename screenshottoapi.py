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
import plyer  # NEW - for desktop notifications
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import win32gui
import win32process
import win32con
import win32api

# -------------------- Config --------------------
load_dotenv()
API_URL = os.getenv("API_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH")
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "cpu")
YOLO_CONF = float(os.getenv("YOLO_CONF", "0.15"))
YOLO_IMGSZ = int(os.getenv("YOLO_IMGSZ", "1280"))
INFERENCE_MODE = os.getenv("INFERENCE_MODE", "auto").lower()  # NEW: local | api | auto

PROCESS_NAME = "tlopo.exe"

# Detection thresholds
ENEMY_CLASS = "enemy"
ENEMY_CONFIDENCE_THRESHOLD = 0.7  # CHANGED from 0.8 to 0.7
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
NO_CHEST_WAIT = 3.0             # wait N seconds for chest to appear after enemy defeat
BUTTON_PRESS_DELAY = 0.5        # NEW: delay after each button press

# No-enemy fallback
ENEMY_ABSENCE_CTRL_THRESHOLD = 5  # press Ctrl if no enemy for N polls

# Mouse behavior
USE_REAL_MOUSE_CLICKS = True
MOUSE_MOVE_DURATION = 0.05       # fast move to target
MOUSE_RETURN_DURATION = 0.05     # fast return to original position
MOUSE_BETWEEN_ACTIONS = 0.05     # small gap between sequential clicks
RESTORE_PRE_FOCUS = True         # try to restore previous foreground window

# Notifications
SPECIAL_NOTIFICATION_DIR = "specialNotifications"
CHEST_SHOT_DIR = "chestScreenShot"

# Files
SCREENSHOT_FILENAME = "screenshot.png"  # ensure PNG for local inference
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

# NOTE: removed unconditional API_URL exit so local mode can run without API

# Optional: class aliases to normalize names  # NEW
CLASS_ALIASES = {
    "loot": "Loot",  # keep if you use it for context
    "lootbutton": "LootTakeButton",
    "loot_take_button": "LootTakeButton",
    "loot take button": "LootTakeButton",
    "take": "LootTakeButton",
    "trash": "TrashIcon",
    "trash_icon": "TrashIcon",
    "bin": "TrashIcon",
    "enemy": "enemy",
    "legendary": "legendary",
    "fame": "fame",
    "ss": "ss",
    "lootexiticon": "LootExitIcon",
    "loot_exit_icon": "LootExitIcon",
}

def canonical_class(name: str) -> str:  # NEW
    if not name:
        return ""
    key = name.strip().lower().replace("-", "_").replace(" ", "")
    return CLASS_ALIASES.get(key, name)

# -------------------- Window helpers --------------------
def get_pid_from_hwnd(hwnd):  # NEW
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid

def _enum_windows_for_pid(pid):  # NEW: enumerate top-level visible windows for PID
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
            # Ensure top-level (no parent) window
            if w_pid == pid and win32gui.GetParent(hwnd) == 0:
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

# Background (no-focus) input helpers
def _make_lparam_xy(x, y):
    return (int(y) << 16) | (int(x) & 0xFFFF)

def post_key(hwnd, vk):
    # Build keyboard messages for background window
    sc = win32api.MapVirtualKey(vk, 0)
    lparam_down = 1 | (sc << 16)
    lparam_up = lparam_down | (1 << 30) | (1 << 31)
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP,   vk, lparam_up)

def post_left_click(hwnd, screen_x, screen_y):
    # Convert screen -> client coords for the target window
    try:
        cx, cy = win32gui.ScreenToClient(hwnd, (int(screen_x), int(screen_y)))
    except Exception as e:
        logger.error(f"ScreenToClient failed: {e}")
        return False
    lp = _make_lparam_xy(cx, cy)
    # Move (optional), then down/up
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
    return True

# Map friendly names to VK codes
KEY_TO_VK = {
    'ctrl':  win32con.VK_CONTROL,
    'shift': win32con.VK_SHIFT,
    'esc':   win32con.VK_ESCAPE,
}

# -------------------- Local YOLO detector --------------------
class LocalYOLODetector:
    def __init__(self, model_path: str, device: str = "cpu", conf: float = 0.25, imgsz: int = 640):
        self.model = YOLO(model_path)
        try:
            self.model.to(device)
        except Exception:
            pass
        self.device = device
        self.conf = conf
        self.imgsz = imgsz
        logger.info(f"Loaded YOLOv8 model: {model_path} on device={device}")
        if hasattr(self.model, "names"):
            logger.info(f"Model classes: {self.model.names}")

    def predict(self, image_path: str):
        results = self.model.predict(
            source=image_path,
            device=self.device,
            conf=self.conf,
            imgsz=self.imgsz,
            iou=0.5,
            verbose=False
        )
        preds = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                w, h = (x2 - x1), (y2 - y1)
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                raw_name = self.model.names[cls_id] if hasattr(self.model, "names") else str(cls_id)
                cls_name = canonical_class(raw_name)
                preds.append({
                    "x": cx, "y": cy, "width": w, "height": h,
                    "confidence": conf, "class": cls_name
                })
        if preds:
            top = sorted(preds, key=lambda p: p["confidence"], reverse=True)[:5]
            logger.info("Top detections: " + ", ".join(f"{p['class']} {p['confidence']:.2f}" for p in top))
        return preds

# -------------------- Bot --------------------
class GameBot:
    def __init__(self):
        self.last_api_time = 0.0
        self.last_ctrl_time = 0.0
        self.last_maint_time = time.time()
        self.enemy_active = False
        self.hwnd = None
        self.tlopo_pid = None            # NEW
        self.state = self.load_state()
        self.save_state()
        logger.info(f"State loaded: bosses_defeated={self.state['bosses_defeated']} chests_opened={self.state['chests_opened']}")
        self.no_enemy_count = 0
        self.waiting_for_chest = False   # NEW - track if we just defeated an enemy
        self.chest_wait_start = 0.0      # NEW - when we started waiting for chest
        try:
            pyautogui.PAUSE = 0
        except Exception:
            pass

        # Decide inference mode (NEW)
        self.inference_mode = INFERENCE_MODE
        resolved = self.inference_mode
        if resolved == "auto":
            resolved = "local" if (YOLO_MODEL_PATH and os.path.exists(YOLO_MODEL_PATH)) else "api"
        self.resolved_mode = resolved

        # Initialize according to resolved mode (NEW)
        self.detector = None
        if self.resolved_mode == "local":
            if YOLO_MODEL_PATH and os.path.exists(YOLO_MODEL_PATH):
                try:
                    self.detector = LocalYOLODetector(YOLO_MODEL_PATH, YOLO_DEVICE, conf=YOLO_CONF, imgsz=YOLO_IMGSZ)
                    logger.info("Using LOCAL YOLOv8 for inference.")
                except Exception as e:
                    logger.warning(f"Local YOLO init failed, falling back to API: {e}")
                    self.resolved_mode = "api"
            else:
                logger.warning("YOLO_MODEL_PATH not set or invalid; using API mode")
                self.resolved_mode = "api"

        if self.resolved_mode == "api":
            if not API_URL:
                logger.error("API_URL not found in .env but API mode requested")
                raise SystemExit(1)
            logger.info("Using Roboflow API for inference.")

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
    def ensure_hwnd(self):
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            self.hwnd = find_tlopo_hwnd()
            if self.hwnd:
                self.tlopo_pid = get_pid_from_hwnd(self.hwnd)  # NEW
                logger.info(f"tlopo hwnd={self.hwnd}, pid={self.tlopo_pid}")
        return self.hwnd

    # ---------- Background inputs (no focus) ----------
    def press_key(self, key, reason=None):
        hwnd = self.ensure_hwnd()
        if not hwnd:
            logger.warning(f"Skipped key '{key}' - tlopo window not found")
            return False
        vk = KEY_TO_VK.get(key.lower())
        if not vk:
            logger.error(f"Unknown key '{key}' for VK mapping")
            return False
        try:
            post_key(hwnd, vk)
            if reason:
                logger.info(f"Posted key '{key}' (background) - reason: {reason}")
            else:
                logger.info(f"Posted key '{key}' (background)")
            
            # Add delay after key press
            time.sleep(BUTTON_PRESS_DELAY)
            return True
        except Exception as e:
            logger.error(f"Post key failed ({key}): {e}")
            return False

    def _belongs_to_tlopo(self, hwnd):  # NEW
        if not hwnd or not win32gui.IsWindow(hwnd) or not self.tlopo_pid:
            return False
        try:
            return get_pid_from_hwnd(hwnd) == self.tlopo_pid
        except Exception:
            return False

    def click_center(self, cx, cy, label="click"):
        # If using real mouse, move-click-return fast; else post background Windows messages
        if USE_REAL_MOUSE_CLICKS:
            try:
                sx, sy = int(cx), int(cy)
                # Save current mouse position and foreground window
                prev_x, prev_y = pyautogui.position()
                prev_hwnd = None
                if RESTORE_PRE_FOCUS:
                    try:
                        prev_hwnd = win32gui.GetForegroundWindow()
                    except Exception:
                        prev_hwnd = None

                # Move -> click -> small gap -> return -> restore focus
                pyautogui.moveTo(sx, sy, duration=MOUSE_MOVE_DURATION)
                pyautogui.click(sx, sy)
                time.sleep(MOUSE_BETWEEN_ACTIONS)
                pyautogui.moveTo(prev_x, prev_y, duration=MOUSE_RETURN_DURATION)

                # Best-effort restore previous foreground window
                if RESTORE_PRE_FOCUS and prev_hwnd and win32gui.IsWindow(prev_hwnd):
                    try:
                        win32gui.SetForegroundWindow(prev_hwnd)
                    except Exception:
                        pass

                logger.info(f"Real-mouse click '{label}' at ({sx}, {sy}), returned to ({prev_x}, {prev_y})")
                
                # Add delay after click
                time.sleep(BUTTON_PRESS_DELAY)
                return True
            except Exception as e:
                logger.error(f"Real-mouse click failed for '{label}': {e}")
                return False
        else:
            # Background click (may be ignored by game)
            hwnd_main = self.ensure_hwnd()
            if not hwnd_main:
                logger.warning(f"Skipped click '{label}' - tlopo window not found")
                return False
            try:
                cx_client, cy_client = win32gui.ScreenToClient(hwnd_main, (int(cx), int(cy)))
                lp = _make_lparam_xy(cx_client, cy_client)
                win32gui.PostMessage(hwnd_main, win32con.WM_MOUSEMOVE, 0, lp)
                win32gui.PostMessage(hwnd_main, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
                win32gui.PostMessage(hwnd_main, win32con.WM_LBUTTONUP, 0, lp)
                logger.info(f"Posted background click '{label}' at screen ({int(cx)},{int(cy)})")
                
                # Add delay after click
                time.sleep(BUTTON_PRESS_DELAY)
                return True
            except Exception as e:
                logger.error(f"Post click exception for '{label}': {e}")
                return False

    # ---------- Vision ----------
    def take_screenshot(self):
        logger.info("Capturing screenshot")
        shot = pyautogui.screenshot()
        shot.save(SCREENSHOT_FILENAME)
        return shot

    def analyze_via_api(self):
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
            # Normalize class names if needed
            for p in preds:
                p["class"] = canonical_class(p.get("class", ""))
            labeled = self.draw_detections(img.copy(), preds)
            labeled.save(LABELED_FILENAME)
            img.close()
            logger.info("Updated labeled_screenshot.png")
            return preds
        except Exception as e:
            logger.error(f"Analyze(API) error: {e}")
            return []

    def analyze(self):
        try:
            img = Image.open(SCREENSHOT_FILENAME)
            width, height = img.size
            # NEW: choose by resolved_mode
            if self.resolved_mode == "local" and self.detector:
                logger.info(f"Local inference on screenshot (size={width}x{height})")
                t0 = time.perf_counter()
                preds = self.detector.predict(SCREENSHOT_FILENAME)
                elapsed = (time.perf_counter() - t0) * 1000.0
                logger.info(f"Local inference ok in {elapsed:.1f} ms - detections={len(preds)}")
                labeled = self.draw_detections(img.copy(), preds)
                labeled.save(LABELED_FILENAME)
                img.close()
                logger.info("Updated labeled_screenshot.png")
                return preds
            else:
                img.close()
                return self.analyze_via_api()
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
            logger.info(f"Enemy present - count={len(enemies)} top_conf={top_conf:.1f}% (threshold: {ENEMY_CONFIDENCE_THRESHOLD*100:.1f}%)")
        else:
            logger.info(f"No enemy present (threshold: {ENEMY_CONFIDENCE_THRESHOLD*100:.1f}%)")
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

    def notify_special_item(self, has_legendary, has_fame, ss_obj):
        """Create desktop notification and save screenshot for special items"""
        try:
            # Create notification directory
            os.makedirs(SPECIAL_NOTIFICATION_DIR, exist_ok=True)
            
            # Build notification message
            items = []
            if has_legendary:
                items.append("Legendary")
            if has_fame:
                items.append("Fame")
            if ss_obj:
                items.append("SS")
            
            title = "Special Item Found!"
            message = f"Found: {', '.join(items)}"
            
            # Save notification screenshot
            ts = time.strftime("%Y%m%d_%H%M%S")
            notif_path = os.path.join(SPECIAL_NOTIFICATION_DIR, f"special_{ts}.png")
            shutil.copyfile(LABELED_FILENAME, notif_path)
            
            # Send desktop notification
            plyer.notification.notify(
                title=title,
                message=message,
                timeout=10,  # seconds
                app_name="Tlopo AutoFarm"
            )
            
            logger.info(f"SPECIAL ITEM NOTIFICATION: {message} - Screenshot saved: {notif_path}")
            
        except Exception as e:
            logger.error(f"Failed to send special item notification: {e}")

    # ---------- Discord webhook ----------
    def send_discord_chest_notification(self, is_special, has_legendary, has_fame, ss_obj):
        """Send chest screenshot to Discord webhook"""
        if not DISCORD_WEBHOOK_URL:
            return
            
        try:
            # Prepare message content
            if is_special or ss_obj:
                items = []
                if has_legendary:
                    items.append("Legendary")
                if has_fame:
                    items.append("Fame")
                if ss_obj:
                    items.append("SS")
                content = f"🎉 **SPECIAL CHEST FOUND!** 🎉\nItems: {', '.join(items)}"
                color = 0x00FF00  # Green for special
            else:
                content = "📦 Chest opened (no special items)"
                color = 0x808080  # Gray for normal
            
            # Read the labeled screenshot
            with open(LABELED_FILENAME, 'rb') as f:
                files = {'file': (f'chest_{time.strftime("%Y%m%d_%H%M%S")}.png', f, 'image/png')}
                
                # Create embed
                embed = {
                    "title": "Tlopo AutoFarm - Chest Detection",
                    "description": content,
                    "color": color,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "image": {"url": f"attachment://chest_{time.strftime('%Y%m%d_%H%M%S')}.png"},
                    "footer": {"text": f"Bosses: {self.state['bosses_defeated']} | Chests: {self.state['chests_opened']}"}
                }
                
                payload = {"embeds": [embed]}
                
                # Send to Discord
                response = requests.post(
                    DISCORD_WEBHOOK_URL,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                    timeout=10
                )
                
                if response.status_code == 204:
                    logger.info("Discord notification sent successfully")
                else:
                    logger.warning(f"Discord webhook failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

    # ---------- Main loop ----------
    def run(self):
        logger.info("Starting bot. Press 'q' to quit.")
        logger.info(f"Inference mode: {INFERENCE_MODE} (resolved: {self.resolved_mode})")  # NEW
        if self.resolved_mode == "local":
            logger.info(f"YOLO device={YOLO_DEVICE}, conf={YOLO_CONF}, imgsz={YOLO_IMGSZ}")  # NEW
        logger.info(f"Enemy confidence threshold: {ENEMY_CONFIDENCE_THRESHOLD*100:.1f}%")
        if DISCORD_WEBHOOK_URL:
            logger.info("Discord webhook configured for chest notifications")
        else:
            logger.warning("No Discord webhook URL found in .env")
            
        # Initial poll
        self.take_screenshot()
        preds = self.analyze()
        self.last_api_time = time.time()
        self.enemy_active = self.have_enemy(preds)
        # Ensure maintenance waits full interval after start
        self.last_maint_time = time.time()

        last_loot_btn_center = None
        last_loot_btn_conf = None
        last_trash_conf = None

        while True:
            if keyboard.is_pressed('q'):
                logger.info("Quit requested.")
                break

            now = time.time()

            # Press Ctrl every second while enemy is active AND no loot chest is present (based on last poll)
            loot_btn_present = last_loot_btn_center is not None  # Track if we just processed loot
            if self.enemy_active and not loot_btn_present and (now - self.last_ctrl_time) >= CTRL_PRESS_INTERVAL:
                self.press_key('ctrl', reason="enemy active - attack tick")
                self.last_ctrl_time = now

            # Periodic maintenance keys (Esc then Ctrl)
            if (now - self.last_maint_time) >= MAINT_INTERVAL:
                logger.info("Maintenance keys: Esc then Ctrl")
                self.press_key('esc', reason="maintenance")
                time.sleep(0.1)
                self.press_key('ctrl', reason="maintenance")
                self.last_maint_time = now

            # Check for chest timeout after enemy defeat
            if self.waiting_for_chest and (now - self.chest_wait_start) >= NO_CHEST_WAIT:
                logger.info(f"No chest found after {NO_CHEST_WAIT}s, pressing Shift")
                self.press_key('shift', reason="no chest found after enemy defeat")
                self.waiting_for_chest = False

            # Poll API on interval
            if (now - self.last_api_time) >= API_POLL_INTERVAL:
                self.take_screenshot()
                preds = self.analyze()
                self.last_api_time = now

                enemy_now = self.have_enemy(preds)
                
                # Reset loot button tracking for this cycle
                last_loot_btn_center = None

                # PRIORITY 1: Handle loot first if chest is open (even if enemy is present)
                loot_btn = self.find_first(preds, 'LootTakeButton')
                trash_icon = self.find_first(preds, 'TrashIcon')

                if loot_btn and trash_icon:
                    # Found chest - prioritize loot handling
                    if enemy_now:
                        logger.info("PRIORITY: Chest detected while enemy present - handling loot first")
                    
                    if self.waiting_for_chest:
                        logger.info("Chest found after enemy defeat")
                        self.waiting_for_chest = False

                    # Log confidences
                    last_loot_btn_conf = loot_btn.get('confidence', 0.0) * 100
                    last_trash_conf = trash_icon.get('confidence', 0.0) * 100
                    logger.info(f"Chest open detected: LootTakeButton conf={last_loot_btn_conf:.1f}%, "
                                f"TrashIcon conf={last_trash_conf:.1f}%")

                    # Determine items (using current preds)
                    has_legendary, has_fame, ss_obj = self.find_items(preds)
                    is_special = has_legendary or has_fame

                    # Send Discord notification for ALL chests
                    self.send_discord_chest_notification(is_special, has_legendary, has_fame, ss_obj)

                    # Send notification for special items
                    if is_special or ss_obj:
                        self.notify_special_item(has_legendary, has_fame, ss_obj)

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

                    # Click LootTakeButton once (fast real-mouse)
                    lx, ly = int(loot_btn['x']), int(loot_btn['y'])
                    last_loot_btn_center = (lx, ly)  # Mark that we're handling loot
                    logger.info(f"Clicking LootTakeButton (conf={last_loot_btn_conf:.1f}%)")
                    self.click_center(lx, ly, label="LootTakeButton")

                    # If ss detected, click its center once (fast)
                    if ss_obj:
                        logger.info(f"SS detected (conf={ss_obj.get('confidence',0.0)*100:.1f}%) - clicking SS")
                        self.click_center(ss_obj['x'], ss_obj['y'], label="Select SS")

                    if is_special:
                        # Keep chest open for viewing/confirmation, then click LootTakeButton again
                        logger.info(f"Holding chest open for {LOOT_KEEP_OPEN:.1f}s (special item)")
                        time.sleep(LOOT_KEEP_OPEN)
                        logger.info("Clicking LootTakeButton again (special)")
                        self.click_center(last_loot_btn_center[0], last_loot_btn_center[1], label="LootTakeButton (2nd)")
                    else:
                        # No special: click TrashIcon immediately (fast chain)
                        time.sleep(MOUSE_BETWEEN_ACTIONS)
                        logger.info(f"No special items; clicking TrashIcon (conf={last_trash_conf:.1f}%)")
                        self.click_center(trash_icon['x'], trash_icon['y'], label="TrashIcon")

                    # Update state
                    self.state["chests_opened"] += 1
                    self.save_state()
                    logger.info(f"Chest handled. Total chests_opened={self.state['chests_opened']}")

                # PRIORITY 2: Handle enemy transitions (only after loot is processed)
                # Transition: enemy defeated
                if self.enemy_active and not enemy_now:
                    self.state["bosses_defeated"] += 1
                    self.save_state()
                    logger.info(f"Enemy defeated. Total bosses_defeated={self.state['bosses_defeated']}")
                    self.press_key('shift', reason="post-fight")
                    # Start waiting for chest (only if we didn't just process one)
                    if not (loot_btn and trash_icon):
                        self.waiting_for_chest = True
                        self.chest_wait_start = now

                self.enemy_active = enemy_now

                # Track no-enemy streak and press Ctrl if threshold reached (only if no loot present)
                if not self.enemy_active and not (loot_btn and trash_icon):
                    self.no_enemy_count += 1
                    logger.info(f"No-enemy streak: {self.no_enemy_count}/{ENEMY_ABSENCE_CTRL_THRESHOLD}")
                    if self.no_enemy_count >= ENEMY_ABSENCE_CTRL_THRESHOLD:
                        self.press_key('ctrl', reason=f"no enemy for {self.no_enemy_count} polls")
                        self.no_enemy_count = 0
                else:
                    if self.no_enemy_count:
                        logger.info("Enemy detected again (or loot present), resetting no-enemy streak")
                    self.no_enemy_count = 0

            time.sleep(0.05)  # prevent busy-wait

        logger.info("Bot stopped.")
        logger.info(f"Final state: bosses_defeated={self.state['bosses_defeated']} chests_opened={self.state['chests_opened']}")

if __name__ == "__main__":
    bot = GameBot()
    bot.run()