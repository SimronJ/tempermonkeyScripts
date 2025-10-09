import os
import pyautogui

# User-configurable window settings
WINDOW_TITLE = "The Legend of Pirates Online [Beta]"
WINDOW_SIZE = (1280, 720)  # width, height
WINDOW_POS = (0, 0)  # x, y

# Template images
BOSS_BAR_TEMPLATE = 'boss_health_bar_template.png'
CHEST_TRASH_TEMPLATE = 'chest_trash_icon.png'
TAKE_SMALL_TEMPLATE = 'take_small_items_button.png'
TRASH_BUTTON_TEMPLATE = 'trash_button.png'

# Color ranges in HSV for rare items
import numpy as np
LOWER_RED1 = np.array([0, 100, 100])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([160, 100, 100])
UPPER_RED2 = np.array([180, 255, 255])

LOWER_BLUE = np.array([80, 50, 150])
UPPER_BLUE = np.array([120, 150, 255])

MIN_CONTOUR_AREA = 200

# Screenshot dir
SCREENSHOT_DIR = "rare_loots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# PyAutoGUI safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

# Image search parameters
CHEST_ICON_CONFIDENCE = 0.8
TAKE_SMALL_CONFIDENCE = 0.8
TRASH_BUTTON_CONFIDENCE = 0.8

# Timeouts / retries (seconds)
OPEN_CHEST_WAIT_S = 1.0
DETECTION_RETRY_DELAY_S = 0.3
DETECTION_RETRIES = 5

# Boss detection
BOSS_TEMPLATE_THRESHOLD = 0.8


