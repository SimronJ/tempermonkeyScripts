import logging
from PIL import ImageGrab, ImageTk
import tkinter as tk
from tkinter import messagebox

from regions import REGIONS, save_calibration


def calibrate_regions() -> None:
    root = tk.Tk()
    root.withdraw()

    logging.info("Starting calibration process.")
    messagebox.showinfo(
        "Calibration",
        "We'll now calibrate the bot regions.\n"
        "1. First, we'll select the boss health bar region\n"
        "2. Then, we'll select the loot/chest region\n"
        "Press OK to start, then click and drag to select regions."
    )

    def get_region(region_name: str) -> None:
        while True:
            logging.info(f"Prompting user to select region: {region_name}")
            screenshot = ImageGrab.grab()
            window = tk.Toplevel(root)
            window.overrideredirect(True)
            window.attributes('-alpha', 0.3)
            window.attributes('-topmost', True)
            window.configure(bg='grey')
            window.geometry(f"{screenshot.width}x{screenshot.height}+0+0")

            canvas = tk.Canvas(window, width=screenshot.width, height=screenshot.height)
            canvas.pack(fill='both', expand=True)

            photo = ImageTk.PhotoImage(screenshot)
            canvas.create_image(0, 0, image=photo, anchor='nw')
            canvas.image = photo

            selection_rect = [None]
            coords = {'start_x': None, 'start_y': None, 'end_x': None, 'end_y': None}
            region_selected = [False]

            def on_mouse_down(event):
                coords['start_x'], coords['start_y'] = event.x, event.y
                coords['end_x'], coords['end_y'] = event.x, event.y
                logging.debug(f"Mouse down at ({event.x}, {event.y})")

            def on_mouse_move(event):
                coords['end_x'], coords['end_y'] = event.x, event.y
                if selection_rect[0]:
                    canvas.delete(selection_rect[0])
                selection_rect[0] = canvas.create_rectangle(
                    coords['start_x'], coords['start_y'], coords['end_x'], coords['end_y'],
                    outline='red', width=2
                )

            def on_mouse_up(event):
                coords['end_x'], coords['end_y'] = event.x, event.y
                x1, y1 = min(coords['start_x'], coords['end_x']), min(coords['start_y'], coords['end_y'])
                x2, y2 = max(coords['start_x'], coords['end_x']), max(coords['start_y'], coords['end_y'])
                logging.debug(f"Mouse up at ({event.x}, {event.y}), region: ({x1}, {y1}, {x2}, {y2})")
                if x2 - x1 > 5 and y2 - y1 > 5:
                    region_selected[0] = True
                    if region_name == "HEALTH_BAR_REGION":
                        REGIONS.HEALTH_BAR_REGION = (x1, y1, x2, y2)
                        logging.info(f"HEALTH_BAR_REGION set to: {REGIONS.HEALTH_BAR_REGION}")
                    else:
                        REGIONS.LOOT_REGION = (x1, y1, x2, y2)
                        logging.info(f"LOOT_REGION set to: {REGIONS.LOOT_REGION}")
                    window.destroy()
                else:
                    logging.warning("Region too small, prompting user to try again.")
                    messagebox.showerror("Calibration Error", "Region too small, please try again.")
                    window.destroy()

            def on_escape(event):
                logging.info("Selection cancelled by user (Escape). Restarting selection.")
                window.destroy()

            canvas.bind('<Button-1>', on_mouse_down)
            canvas.bind('<B1-Motion>', on_mouse_move)
            canvas.bind('<ButtonRelease-1>', on_mouse_up)
            window.bind('<Escape>', on_escape)

            try:
                window.grab_set()
            except Exception:
                pass
            try:
                window.focus_force()
            except Exception:
                pass
            window.wait_window(window)
            if region_selected[0]:
                break

    get_region("HEALTH_BAR_REGION")
    messagebox.showinfo("Calibration", "Now select the loot/chest region")
    get_region("LOOT_REGION")

    save_calibration()
    logging.info("Calibration complete and saved.")
    root.destroy()


