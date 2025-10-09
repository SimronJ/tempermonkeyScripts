import pyautogui
import time
import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageTk
import os
import random
import threading
from pynput import keyboard
import win32gui
import win32con
import tkinter as tk
from tkinter import messagebox
import json

# Replace the region constants with a class
class Regions:
    def __init__(self):
        self.HEALTH_BAR_REGION = None
        self.LOOT_REGION = None

REGIONS = Regions()
# Safety features
pyautogui.FAILSAFE = True  # Move mouse to top-left to abort
pyautogui.PAUSE = 0.01

# User-configurable
WINDOW_TITLE = "The Legend of Pirates Online [Beta]"
WINDOW_SIZE = (1280, 720)  # Width, height - adjust if needed
WINDOW_POS = (0, 0)  # Top-left corner

# Regions relative to window top-left (adjust based on your window size)
HEALTH_BAR_REGION = (536, 63632083, 757, 10606)  # x1, y1, x2, y2 - crop where health bar appears
LOOT_REGION = (259, 17575, 600, 40606)  # Area where item names/icons appear in chest

# Template images - save these from your screenshots (crop tightly)
BOSS_BAR_TEMPLATE = 'boss_health_bar_template.png'  # Crop the empty bar or common part
CHEST_TRASH_TEMPLATE = 'chest_trash_icon.png'  # Crop the trash can icon
TAKE_SMALL_TEMPLATE = 'take_small_items_button.png'  # Crop the button
TRASH_BUTTON_TEMPLATE = 'trash_button.png'  # If different from trash icon, else reuse

CHEST_TRASH_TEMPLATE = TRASH_BUTTON_TEMPLATE

# Color ranges in HSV
# Legendary red
LOWER_RED1 = np.array([0, 100, 100])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([160, 100, 100])
UPPER_RED2 = np.array([180, 255, 255])

# Fame light blue - adjust based on exact shade from screenshot
LOWER_BLUE = np.array([80, 50, 150])  # Lighter cyan/blue
UPPER_BLUE = np.array([120, 150, 255])

# Threshold for rare detection: min contiguous area (use contours for patches)
MIN_CONTOUR_AREA = 200  # Pixels for a "patch" - tune to avoid single pixels

# Screenshot dir
SCREENSHOT_DIR = "rare_loots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Globals
attacking = False
paused = False
attack_thread = None

def on_press(key):
    global paused
    try:
        if key.char == 'p':
            paused = not paused
            print(f"Script {'paused' if paused else 'resumed'}.")
    except AttributeError:
        pass

listener = keyboard.Listener(on_press=on_press)
listener.start()

def set_window_position():
    hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
    if hwnd:
        rect = (WINDOW_POS[0], WINDOW_POS[1], WINDOW_POS[0] + WINDOW_SIZE[0], WINDOW_POS[1] + WINDOW_SIZE[1])
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, *rect, 0)
        print("Window positioned and sized.")
    else:
        raise Exception("Game window not found. Ensure it's running and title matches.")

def is_boss_present():
    screenshot = ImageGrab.grab(bbox=REGIONS.HEALTH_BAR_REGION)
    img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    # Load template
    template = cv2.imread(BOSS_BAR_TEMPLATE, cv2.IMREAD_UNCHANGED)
    if template is None:
        raise Exception("Template not found: " + BOSS_BAR_TEMPLATE)
    
    # Match template (use TM_CCOEFF_NORMED for similarity)
    res = cv2.matchTemplate(img_cv, template, cv2.TM_CCOEFF_NORMED)
    threshold = 0.8  # Adjust similarity threshold
    return np.max(res) >= threshold

def is_chest_open():
    # Locate trash icon on screen
    pos = pyautogui.locateOnScreen(CHEST_TRASH_TEMPLATE, confidence=0.8)
    return pos is not None

def locate_take_small():
    return pyautogui.locateCenterOnScreen(TAKE_SMALL_TEMPLATE, confidence=0.8)

def locate_trash():
    return pyautogui.locateCenterOnScreen(TRASH_BUTTON_TEMPLATE, confidence=0.8)

def has_rare_items():
    screenshot = ImageGrab.grab(bbox=REGIONS.LOOT_REGION)
    img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    
    mask_red1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    mask_red2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    
    mask_blue = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
    
    mask = cv2.bitwise_or(mask_red, mask_blue)
    
    # Find contours to detect patches
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > MIN_CONTOUR_AREA:
            # Save screenshot
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = os.path.join(SCREENSHOT_DIR, f"rare_loot_{timestamp}.png")
            screenshot.save(filename)
            print(f"Rare patch detected (area: {area})! Saved: {filename}")
            return True
    return False

def attack_loop():
    while attacking and not paused:
        pyautogui.press('ctrl')
        
        # Random mouse wiggle to mimic human
        if random.random() < 0.2:  # 20% chance
            center_x, center_y = WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2
            wiggle_x = random.randint(-50, 50)
            wiggle_y = random.randint(-50, 50)
            pyautogui.moveTo(center_x + wiggle_x, center_y + wiggle_y, duration=0.1)
        
        time.sleep(0.5 + random.uniform(-0.1, 0.1))

def handle_chest():
    print("Attempting to open chest...")
    pyautogui.press('shift')
    time.sleep(1)  # Wait for open animation
    
    if not is_chest_open():
        print("No chest appeared.")
        return
    
    print("Chest open. Taking small items...")
    take_pos = locate_take_small()
    if take_pos:
        pyautogui.click(take_pos)
    else:
        print("Take Small button not found!")
        return
    time.sleep(0.5)
    
    if has_rare_items():
        print("Rare items found - taking all.")
        pyautogui.doubleClick(take_pos)  # Double click to take rares?
    else:
        print("No rares - trashing.")
        trash_pos = locate_trash()
        if trash_pos:
            pyautogui.click(trash_pos)
        else:
            print("Trash button not found!")
    
    time.sleep(0.5)
    print("Closing chest...")
    pyautogui.press('esc')
    time.sleep(0.5)

def calibrate_regions():
    """Interactive region selection for health bar and loot areas"""
    root = tk.Tk()
    root.withdraw()
    
    messagebox.showinfo(
        "Calibration", 
        "We'll now calibrate the bot regions.\n"
        "1. First, we'll select the boss health bar region\n"
        "2. Then, we'll select the loot/chest region\n"
        "Press OK to start, then click and drag to select regions."
    )

    def on_region_select(region_name):
        screenshot = ImageGrab.grab()
        
        window = tk.Toplevel(root)
        window.attributes('-fullscreen', True, '-alpha', 0.3)
        window.configure(bg='grey')

        canvas = tk.Canvas(window)
        canvas.pack(fill='both', expand=True)
        
        photo = ImageTk.PhotoImage(screenshot)
        canvas.create_image(0, 0, image=photo, anchor='nw')

        start_x = start_y = end_x = end_y = None
        selection_rect = None

        def on_mouse_down(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x, event.y

        def on_mouse_move(event):
            nonlocal selection_rect, end_x, end_y
            if start_x is not None:
                end_x, end_y = event.x, event.y
                canvas.delete(selection_rect)
                selection_rect = canvas.create_rectangle(
                    start_x, start_y, end_x, end_y,
                    outline='red', width=2
                )

        def on_mouse_up(event):
            nonlocal start_x, start_y, end_x, end_y
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            
            if region_name == "HEALTH_BAR_REGION":
                REGIONS.HEALTH_BAR_REGION = (x1, y1, x2, y2)
            else:
                REGIONS.LOOT_REGION = (x1, y1, x2, y2)
            
            window.destroy()

        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        
        window.mainloop()

    on_region_select("HEALTH_BAR_REGION")
    messagebox.showinfo("Calibration", "Now select the loot/chest region")
    on_region_select("LOOT_REGION")
    
    save_calibration()
    root.destroy()

def save_calibration():
    """Save calibrated regions to a config file"""
    config = {
        'HEALTH_BAR_REGION': REGIONS.HEALTH_BAR_REGION,
        'LOOT_REGION': REGIONS.LOOT_REGION
    }
    with open('region_config.json', 'w') as f:
        json.dump(config, f)

def load_calibration():
    """Load calibrated regions from config file"""
    try:
        with open('region_config.json', 'r') as f:
            config = json.load(f)
            REGIONS.HEALTH_BAR_REGION = tuple(config['HEALTH_BAR_REGION'])
            REGIONS.LOOT_REGION = tuple(config['LOOT_REGION'])
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False

def main():
    global attacking, attack_thread
    set_window_position()
    
    # Add calibration check
    if not load_calibration():
        print("No calibration found. Starting calibration process...")
        calibrate_regions()
    
    print("Starting auto-farm. Press 'p' to toggle pause. Top-left mouse to abort.")
    
    was_boss_present = False
    
    try:
        while True:
            if paused:
                time.sleep(0.5)
                continue
            
            boss_present = is_boss_present()
            
            if boss_present and not was_boss_present:
                print("Boss appeared! Waiting 5s to attack...")
                time.sleep(5)
                attacking = True
                attack_thread = threading.Thread(target=attack_loop)
                attack_thread.start()
            
            elif not boss_present and was_boss_present:
                print("Boss died! Stopping attack, waiting 1s for chest...")
                attacking = False
                if attack_thread:
                    attack_thread.join()
                time.sleep(1)
                handle_chest()
            
            was_boss_present = boss_present
            time.sleep(1)  # Check interval - adjust for responsiveness
            
    except pyautogui.FailSafeException:
        print("Emergency stop.")
    finally:
        listener.stop()

if __name__ == "__main__":
    main()