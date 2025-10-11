# filepath: e:\github_clone\Tlopo_Boss_AutoFarm\screenshottoapi.py
import pyautogui
import requests
import time
from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
import keyboard
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL")
ENEMY_CONFIDENCE_THRESHOLD = 0.8
ATTACK_DELAY = 0.5
LOOT_CLICK_COUNT = 2
SCREENSHOT_INTERVAL = 3
FONT_SIZE = 24
SCREENSHOT_FILENAME = "screenshot.png"        # always overwrite this file
LABELED_FILENAME = "labeled_screenshot.png"   # always overwrite this file

# Validate configuration
if not API_URL:
    logger.error("API_URL not found in .env file")
    exit(1)

logger.info(f"API URL: {API_URL}")

# Color scheme for different classes
CLASS_COLORS = {
    'enemy': 'green',
    'LootTakeButton': 'blue',
    'LootExitIcon': 'orange',
    'TrashIcon': 'purple'
}

class GameBot:
    def __init__(self):
        self.screenshot_count = 0
        self.enemies_defeated = 0
        self.loot_collected = 0
        
    def click_position(self, x, y, action_type="generic"):
        """Click at the specified coordinates"""
        center_x = int(x)
        center_y = int(y)
        
        try:
            pyautogui.click(center_x, center_y)
            logger.info(f"{action_type} click at: ({center_x}, {center_y})")
            return True
        except Exception as e:
            logger.error(f"Failed to click at ({center_x}, {center_y}): {e}")
            return False

    def draw_detections(self, image, predictions):
        """Draw bounding boxes and labels on the image"""
        draw = ImageDraw.Draw(image)
        
        try:
            font = ImageFont.truetype("arial.ttf", FONT_SIZE)
        except OSError:
            # Fallback to default font if arial.ttf is not available
            font = ImageFont.load_default()
            logger.warning("Arial font not found, using default font")

        for pred in predictions:
            # Get color for the class
            color = CLASS_COLORS.get(pred['class'], 'yellow')

            # Calculate bounding box coordinates
            center_x = int(pred['x'])
            center_y = int(pred['y'])
            width = int(pred['width'])
            height = int(pred['height'])
            
            x1 = center_x - width // 2
            y1 = center_y - height // 2
            x2 = center_x + width // 2
            y2 = center_y + height // 2
            
            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

            # Create label with confidence
            confidence_percent = pred['confidence'] * 100
            label = f"{pred['class']} ({confidence_percent:.1f}%)"
            
            # Draw label background for better visibility
            bbox = draw.textbbox((x1, y1 - 30), label, font=font)
            draw.rectangle(bbox, fill='black', outline='white')
            draw.text((x1, y1 - 30), label, fill="#FF0000", font=font)

        return image

    def take_screenshot_and_analyze(self):
        """Take screenshot, send to API, and return predictions"""
        try:
            # Take screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(SCREENSHOT_FILENAME)  # overwrite the same file
            self.screenshot_count += 1

            # Send to API
            with open(SCREENSHOT_FILENAME, "rb") as image_file:
                response = requests.post(API_URL, files={"file": image_file}, timeout=10)
                
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}")
                return []

            data = response.json()
            predictions = data.get('predictions', [])
            
            # Log detection summary
            detection_summary = {}
            for pred in predictions:
                class_name = pred['class']
                detection_summary[class_name] = detection_summary.get(class_name, 0) + 1
            
            if detection_summary:
                logger.info(f"Detected: {detection_summary}")
            
            # Save labeled screenshot (overwrite)
            if predictions:
                labeled_image = self.draw_detections(screenshot.copy(), predictions)
                labeled_image.save(LABELED_FILENAME)
            
            return predictions
            
        except requests.exceptions.Timeout:
            logger.error("API request timeout")
            return []
        except Exception as e:
            logger.error(f"Error in screenshot analysis: {e}")
            return []

    def filter_high_confidence_enemies(self, predictions):
        """Filter enemies with confidence above threshold"""
        return [pred for pred in predictions 
                if pred['class'] == 'enemy' and pred['confidence'] > ENEMY_CONFIDENCE_THRESHOLD]

    def get_loot_buttons(self, predictions):
        """Get loot take buttons from predictions"""
        return [pred for pred in predictions if pred['class'] == 'LootTakeButton']

    def attack_enemies(self, enemies):
        """Attack enemies until they're defeated"""
        if not enemies:
            return
            
        logger.info(f"Starting attack on {len(enemies)} high confidence enemies")
        
        # Attack the first enemy
        target = enemies[0]
        target_x, target_y = target['x'], target['y']
        
        attack_count = 0
        max_attacks = 50  # Prevent infinite loops
        
        while attack_count < max_attacks:
            # Check for quit signal
            if keyboard.is_pressed('q'):
                logger.info("Quit signal received during combat")
                return False
            
            # Attack the enemy
            if self.click_position(target_x, target_y, "Attack"):
                attack_count += 1
                
            time.sleep(ATTACK_DELAY)
            
            # Check if enemies are still present
            current_predictions = self.take_screenshot_and_analyze()
            current_enemies = self.filter_high_confidence_enemies(current_predictions)
            
            if not current_enemies:
                logger.info(f"Enemy defeated after {attack_count} attacks")
                self.enemies_defeated += 1
                
                # Press Shift after defeating enemy
                pyautogui.press('shift')
                logger.info("Pressed Shift key after combat")
                return True
                
        logger.warning(f"Max attacks ({max_attacks}) reached, stopping attack")
        return True

    def collect_loot(self, loot_buttons):
        """Collect loot by clicking loot buttons"""
        if not loot_buttons:
            return
            
        logger.info(f"Collecting loot from {len(loot_buttons)} buttons")
        
        for loot_button in loot_buttons:
            for i in range(LOOT_CLICK_COUNT):
                if self.click_position(loot_button['x'], loot_button['y'], "Loot"):
                    time.sleep(0.2)
                    
        self.loot_collected += len(loot_buttons)

    def print_statistics(self):
        """Print bot statistics"""
        logger.info(f"Statistics - Screenshots: {self.screenshot_count}, "
                   f"Enemies defeated: {self.enemies_defeated}, "
                   f"Loot collected: {self.loot_collected}")

    def run(self):
        """Main bot loop"""
        logger.info("Starting Tlopo Boss AutoFarm Bot")
        logger.info("Press 'q' to quit at any time")
        
        try:
            while True:
                # Check for quit signal
                if keyboard.is_pressed('q'):
                    logger.info("Quit signal received")
                    break

                # Take screenshot and analyze
                predictions = self.take_screenshot_and_analyze()
                
                if not predictions:
                    time.sleep(SCREENSHOT_INTERVAL)
                    continue
                
                # Check for enemies
                enemies = self.filter_high_confidence_enemies(predictions)
                
                # Check for loot
                loot_buttons = self.get_loot_buttons(predictions)

                # Priority: Attack enemies first, then collect loot
                if enemies:
                    if not self.attack_enemies(enemies):
                        break  # Quit signal received
                elif loot_buttons:
                    self.collect_loot(loot_buttons)
                else:
                    logger.info("No targets detected, scanning...")

                # Wait before next iteration
                time.sleep(SCREENSHOT_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.print_statistics()
            logger.info("Bot shutdown complete")

if __name__ == "__main__":
    bot = GameBot()
    bot.run()