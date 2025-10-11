# filepath: e:\github_clone\Tlopo_Boss_AutoFarm\screenshottoapi.py
import pyautogui
import requests
import time
from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
import keyboard

# Load environment variables from .env file
load_dotenv()

# Get the API URL from the environment variable
api_url = os.getenv("API_URL")
print(f"API URL: {api_url}")  # Optional: Check if the URL is loaded correctly

def click_enemy_center(x, y):
    # The x, y from the API represents the center of the bounding box
    center_x = int(x)
    center_y = int(y)
    
    # Click at the center of the enemy
    pyautogui.click(center_x, center_y)
    print(f"Clicked at center: ({center_x}, {center_y})")

def click_loot_button(x, y):
    # Click on the loot button
    center_x = int(x)
    center_y = int(y)
    
    pyautogui.click(center_x, center_y)
    print(f"Clicked loot button at: ({center_x}, {center_y})")

def draw_detections(image, predictions):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 24)  # Use a larger font size (24)

    for pred in predictions:
        # Set color and label based on class
        if pred['class'] == 'enemy':
            color = "green"
        else:
            color = "yellow"  # Default color for other classes

        # The API returns center coordinates (x, y) and width, height
        center_x = int(pred['x'])
        center_y = int(pred['y'])
        width = int(pred['width'])
        height = int(pred['height'])
        
        # Calculate top-left corner for drawing the rectangle
        x1 = center_x - width // 2
        y1 = center_y - height // 2
        x2 = center_x + width // 2
        y2 = center_y + height // 2
        
        # Draw a rectangle around the detected object
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # Label the detection with confidence and class name
        label = f"{pred['class']} ({pred['confidence']:.2f})"
        draw.text((x1, y1 - 30), label, fill="#FF0000", font=font)  # Use bright red color

    return image

def take_screenshot_and_analyze():
    # Take a screenshot
    screenshot = pyautogui.screenshot()
    screenshot.save("screenshot.png")

    # Send the screenshot to the API as a binary file
    with open("screenshot.png", "rb") as image_file:
        response = requests.post(api_url, files={"file": image_file})

    # Get the response data
    data = response.json()
    print(data)

    # Get predictions
    predictions = data.get('predictions', [])
    
    # Save labeled screenshot
    labeled_image = draw_detections(screenshot.copy(), predictions)
    labeled_image.save("labeled_screenshot.png")
    
    return predictions

while True:
    # Check if 'q' is pressed to stop the script
    if keyboard.is_pressed('q'):
        print("Stopping the script.")
        break

    # Take screenshot and analyze
    predictions = take_screenshot_and_analyze()
    
    # Filter enemies with confidence > 80%
    high_confidence_enemies = [pred for pred in predictions if pred['class'] == 'enemy' and pred['confidence'] > 0.8]
    
    # Check for loot take button
    loot_buttons = [pred for pred in predictions if pred['class'] == 'LootTakeButton']

    if high_confidence_enemies:
        print(f"High confidence enemy detected! Found {len(high_confidence_enemies)} enemies with >80% confidence.")
        
        # Keep clicking on the first enemy until no more enemies are detected
        enemy = high_confidence_enemies[0]
        enemy_x, enemy_y = enemy['x'], enemy['y']
        
        while True:
            # Check if 'q' is pressed to stop the script
            if keyboard.is_pressed('q'):
                print("Stopping the script.")
                exit()
            
            # Click on the enemy
            click_enemy_center(enemy_x, enemy_y)
            
            # Wait 0.5 seconds
            time.sleep(0.5)
            
            # Take another screenshot to check if enemy is still there
            current_predictions = take_screenshot_and_analyze()
            current_enemies = [pred for pred in current_predictions if pred['class'] == 'enemy' and pred['confidence'] > 0.8]
            
            # If no more high confidence enemies, break the loop
            if not current_enemies:
                print("No more enemies detected. Stopping attack.")
                break
        
        # Press Shift once after defeating the enemy
        print("Pressing Shift key.")
        pyautogui.press('shift')
        
    elif loot_buttons:
        print(f"Loot button detected! Found {len(loot_buttons)} loot buttons.")
        # Click on the loot button 2 times
        loot_button = loot_buttons[0]
        for i in range(2):
            click_loot_button(loot_button['x'], loot_button['y'])
            time.sleep(0.2)  # Small delay between clicks
            
    else:
        print("No high confidence enemies or loot buttons detected.")

    # Wait for 3 seconds before taking the next screenshot (only if not in combat)
    time.sleep(3)