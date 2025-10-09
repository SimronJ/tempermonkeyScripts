import time
import threading
import logging
import pyautogui
from pynput import keyboard
import win32gui
import win32con

from logger import setup_console_logging
from config import WINDOW_TITLE, WINDOW_SIZE, WINDOW_POS
from regions import REGIONS, load_calibration
from calibration import calibrate_regions
from detection import is_boss_present
from actions import attack_loop, handle_chest

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
        # SetWindowPos expects X, Y, width, height (not right/bottom)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            WINDOW_POS[0],
            WINDOW_POS[1],
            WINDOW_SIZE[0],
            WINDOW_SIZE[1],
            0
        )
        print("Window positioned and sized.")
    else:
        raise Exception("Game window not found. Ensure it's running and title matches.")


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
                attack_thread = threading.Thread(
                    target=attack_loop,
                    args=(lambda: attacking, lambda: paused)
                )
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

setup_console_logging()

if __name__ == "__main__":
    main()