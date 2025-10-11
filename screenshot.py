import os
import time
import threading
import pyautogui
import keyboard
import pygetwindow as gw

# Function to list all available windows
def list_windows():
    windows = gw.getAllWindows()
    valid_windows = []
    
    print("\nAvailable windows:")
    print("-" * 50)
    
    for i, window in enumerate(windows):
        # Filter out windows with empty titles or minimized windows
        if window.title.strip() and window.visible and window.width > 0 and window.height > 0:
            valid_windows.append(window)
            print(f"{len(valid_windows)}. {window.title} (Size: {window.width}x{window.height})")
    
    return valid_windows

# Function to take screenshots of a specific window
def take_screenshot(interval, stop_event, target_window):
    # Create a directory for screenshots if it doesn't exist
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    while not stop_event.is_set():
        try:
            # Check if window still exists and is visible
            if target_window.visible:
                # Bring window to front (optional)
                # target_window.activate()
                
                # Get window position and size
                left, top, width, height = target_window.left, target_window.top, target_window.width, target_window.height
                
                # Take screenshot of the specific window region
                timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
                
                # Create filename with window title (sanitized for filesystem)
                window_name = "".join(c for c in target_window.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"screenshots/screenshot_{window_name}_{timestamp}.png"
                screenshot.save(filename)
                
            else:
                print(f"Warning: Target window '{target_window.title}' is no longer visible.")
                
        except Exception as e:
            print(f"Error taking screenshot: {e}")

        # Wait for the specified interval
        stop_event.wait(interval)

# Main function
def main():
    print("Window Screenshot Tool")
    print("=" * 30)
    
    # List all available windows
    windows = list_windows()
    
    if not windows:
        print("No valid windows found!")
        return
    
    # Ask user to select a window
    while True:
        try:
            choice = int(input(f"\nSelect a window (1-{len(windows)}): ")) - 1
            if 0 <= choice < len(windows):
                selected_window = windows[choice]
                break
            else:
                print(f"Please enter a number between 1 and {len(windows)}")
        except ValueError:
            print("Please enter a valid number")
    
    print(f"\nSelected window: '{selected_window.title}'")
    
    # Ask for the interval between screenshots
    while True:
        try:
            interval = int(input("Enter the interval between screenshots (in seconds): "))
            if interval > 0:
                break
            else:
                print("Please enter a positive number")
        except ValueError:
            print("Please enter a valid number")
    
    # Create a stop event for the screenshot thread
    stop_event = threading.Event()
    
    # Create and start the screenshot thread
    screenshot_thread = threading.Thread(target=take_screenshot, args=(interval, stop_event, selected_window))
    screenshot_thread.start()

    print(f"\nScreenshot program started for window: '{selected_window.title}'")
    print("Press 'q' to quit.")

    # Listen for keyboard input to quit the program
    keyboard.wait("q")

    # Set the stop event to end the screenshot thread
    stop_event.set()

    # Wait for the screenshot thread to finish
    screenshot_thread.join()

    print("Program ended.")

if __name__ == "__main__":
    main()