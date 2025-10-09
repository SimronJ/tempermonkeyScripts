import time
import random
import logging
import pyautogui

from config import WINDOW_SIZE, OPEN_CHEST_WAIT_S, DETECTION_RETRIES, DETECTION_RETRY_DELAY_S
from detection import is_chest_open, locate_take_small, has_rare_items, locate_trash


def attack_loop(attacking_flag, paused_flag):
    while attacking_flag() and not paused_flag():
        pyautogui.press('ctrl')
        if random.random() < 0.2:
            center_x, center_y = WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2
            wiggle_x = random.randint(-50, 50)
            wiggle_y = random.randint(-50, 50)
            pyautogui.moveTo(center_x + wiggle_x, center_y + wiggle_y, duration=0.1)
        time.sleep(0.5 + random.uniform(-0.1, 0.1))


def handle_chest():
    logging.info("Attempting to open chest...")
    pyautogui.press('shift')
    time.sleep(OPEN_CHEST_WAIT_S)

    # Wait/retry brief period for chest UI to appear
    appeared = False
    for _ in range(DETECTION_RETRIES):
        if is_chest_open():
            appeared = True
            break
        time.sleep(DETECTION_RETRY_DELAY_S)
    if not appeared:
        logging.info("No chest appeared.")
        return

    logging.info("Chest open. Taking small items...")
    take_pos = None
    for _ in range(DETECTION_RETRIES):
        take_pos = locate_take_small()
        if take_pos:
            break
        time.sleep(DETECTION_RETRY_DELAY_S)
    if take_pos:
        pyautogui.click(take_pos)
    else:
        logging.warning("Take Small button not found!")
        return
    time.sleep(0.5)

    if has_rare_items():
        logging.info("Rare items found - taking all.")
        pyautogui.doubleClick(take_pos)
    else:
        logging.info("No rares - trashing.")
        trash_pos = locate_trash()
        if trash_pos:
            pyautogui.click(trash_pos)
        else:
            logging.warning("Trash button not found!")
    time.sleep(0.5)
    logging.info("Closing chest...")
    pyautogui.press('esc')
    time.sleep(0.5)


