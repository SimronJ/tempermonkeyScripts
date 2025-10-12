import moviepy as mp
from pathlib import Path
import os, sys
import imageio_ffmpeg

SCREENSHOT_FOLDER = Path("chestScreenShot")
OUTPUT_VIDEO = "chest_openings.mp4"
FRAME_DURATION = 1.0  # seconds per image

if not SCREENSHOT_FOLDER.is_dir():
    print(f"Folder not found: {SCREENSHOT_FOLDER.resolve()}")
    sys.exit(1)

files = [p for p in SCREENSHOT_FOLDER.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
files.sort(key=lambda p: p.stat().st_mtime)
if not files:
    print(f"No images found in {SCREENSHOT_FOLDER.resolve()}")
    sys.exit(1)

image_paths = [str(p) for p in files]
durations = [FRAME_DURATION] * len(image_paths)

clip = mp.ImageSequenceClip(image_paths, durations=durations)

fps = max(1, int(round(1.0 / FRAME_DURATION)))
os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

clip.write_videofile(
    OUTPUT_VIDEO,
    codec="libx264",
    audio=False,
    fps=fps,
    preset="medium",
    threads=os.cpu_count() or 4,
)

print(f"Video saved as {OUTPUT_VIDEO} from {len(image_paths)} frames")