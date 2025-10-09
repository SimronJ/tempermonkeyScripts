import logging
import os
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

from regions import REGIONS
from config import (
    BOSS_BAR_TEMPLATE,
    CHEST_TRASH_TEMPLATE,
    TAKE_SMALL_TEMPLATE,
    TRASH_BUTTON_TEMPLATE,
    LOWER_RED1, UPPER_RED1, LOWER_RED2, UPPER_RED2,
    LOWER_BLUE, UPPER_BLUE,
    MIN_CONTOUR_AREA,
    CHEST_ICON_CONFIDENCE,
    TAKE_SMALL_CONFIDENCE,
    TRASH_BUTTON_CONFIDENCE,
    BOSS_TEMPLATE_THRESHOLD,
)


def is_boss_present() -> bool:
    if not REGIONS.HEALTH_BAR_REGION:
        logging.debug("Boss detection skipped: HEALTH_BAR_REGION not set.")
        return False
    if not os.path.exists(BOSS_BAR_TEMPLATE):
        logging.error(f"Boss template missing: {BOSS_BAR_TEMPLATE}")
        return False
    screenshot = ImageGrab.grab(bbox=REGIONS.HEALTH_BAR_REGION)
    img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    template = cv2.imread(BOSS_BAR_TEMPLATE, cv2.IMREAD_UNCHANGED)
    if template is None:
        logging.error("Failed to load boss template image.")
        return False
    res = cv2.matchTemplate(img_cv, template, cv2.TM_CCOEFF_NORMED)
    return np.max(res) >= BOSS_TEMPLATE_THRESHOLD


def is_chest_open() -> bool:
    if not os.path.exists(CHEST_TRASH_TEMPLATE):
        logging.debug(f"Chest icon template missing: {CHEST_TRASH_TEMPLATE}")
        return False
    try:
        pos = pyautogui.locateOnScreen(CHEST_TRASH_TEMPLATE, confidence=CHEST_ICON_CONFIDENCE)
        return pos is not None
    except pyautogui.ImageNotFoundException:
        return False


def locate_take_small():
    if not os.path.exists(TAKE_SMALL_TEMPLATE):
        logging.debug(f"Take Small template missing: {TAKE_SMALL_TEMPLATE}")
        return None
    try:
        return pyautogui.locateCenterOnScreen(TAKE_SMALL_TEMPLATE, confidence=TAKE_SMALL_CONFIDENCE)
    except pyautogui.ImageNotFoundException:
        return None


def locate_trash():
    template = TRASH_BUTTON_TEMPLATE if os.path.exists(TRASH_BUTTON_TEMPLATE) else CHEST_TRASH_TEMPLATE
    if not os.path.exists(template):
        logging.debug("Trash button template missing.")
        return None
    try:
        return pyautogui.locateCenterOnScreen(template, confidence=TRASH_BUTTON_CONFIDENCE)
    except pyautogui.ImageNotFoundException:
        return None


def has_rare_items() -> bool:
    screenshot = ImageGrab.grab(bbox=REGIONS.LOOT_REGION)
    img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)

    mask_red1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    mask_red2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)

    mask_blue = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
    mask = cv2.bitwise_or(mask_red, mask_blue)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > MIN_CONTOUR_AREA:
            return True
    return False


