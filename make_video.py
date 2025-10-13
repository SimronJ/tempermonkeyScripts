import moviepy as mp
from PIL import Image
import os
import imageio_ffmpeg
from pathlib import Path
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp_proc
import time

SCREENSHOT_FOLDER = Path("chestScreenShot")
OUTPUT_VIDEO = "chest_openings.mp4"
FRAME_DURATION = 1.0  # seconds per image

def resize_single_image(args):
    """Function to resize a single image - for threading"""
    img_path, target_size, output_path = args
    try:
        with Image.open(img_path) as img:
            img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
            img_resized.save(output_path)
        return True
    except Exception as e:
        print(f"Error resizing {img_path}: {e}")
        return False

def delete_single_file(file_path):
    """Function to delete a single file - for threading"""
    try:
        file_path.unlink()
        return True
    except Exception as e:
        print(f"Failed to delete {file_path.name}: {e}")
        return False

# Function to resize images using threading with progress
def resize_images_threaded(image_paths, target_size=None):
    """
    Resize all images to the same size using threading with progress updates
    """
    if not image_paths:
        return []
    
    print("Analyzing image sizes...")
    # Get target size from first image if not specified
    if target_size is None:
        with Image.open(image_paths[0]) as first_img:
            target_size = first_img.size
        print(f"Target size set to: {target_size[0]}x{target_size[1]}")
    
    temp_dir = "temp_resized"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Prepare arguments for threading
    resize_args = []
    resized_paths = []
    for i, img_path in enumerate(image_paths):
        output_path = os.path.join(temp_dir, f"resized_{i}.png")
        resize_args.append((img_path, target_size, output_path))
        resized_paths.append(output_path)
    
    print("Resizing images using threading...")
    total_images = len(image_paths)
    
    # Use threading instead of multiprocessing for better Windows compatibility
    max_workers = min(32, mp_proc.cpu_count() * 2)  # Use more threads since it's I/O bound
    print(f"Using {max_workers} threads for image processing...")
    
    completed_count = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {executor.submit(resize_single_image, arg): i for i, arg in enumerate(resize_args)}
        
        # Process completed tasks and show progress
        for future in as_completed(future_to_index):
            completed_count += 1
            
            # Show progress every 50 images or every 10% or on last image
            if (completed_count % 50 == 0 or 
                completed_count % max(1, total_images // 10) == 0 or 
                completed_count == total_images):
                
                elapsed_time = time.time() - start_time
                progress_pct = (completed_count / total_images) * 100
                
                if completed_count > 0:
                    avg_time_per_image = elapsed_time / completed_count
                    remaining_images = total_images - completed_count
                    eta_seconds = remaining_images * avg_time_per_image
                    
                    print(f"Progress: {completed_count}/{total_images} ({progress_pct:.1f}%) - "
                          f"ETA: {eta_seconds:.0f}s")
    
    successful_resizes = completed_count  # All completed tasks
    elapsed_time = time.time() - start_time
    print(f"✓ Successfully resized {successful_resizes}/{total_images} images in {elapsed_time:.1f}s!")
    
    return resized_paths, temp_dir

# Check for GPU acceleration availability
def get_video_codec():
    """Determine the best available codec for GPU acceleration"""
    try:
        # Try NVIDIA GPU acceleration first
        import subprocess
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        if 'h264_nvenc' in result.stdout:
            print("NVIDIA GPU encoder detected - using h264_nvenc")
            return 'h264_nvenc'
        elif 'h264_amf' in result.stdout:
            print("AMD GPU encoder detected - using h264_amf")
            return 'h264_amf'
        elif 'h264_qsv' in result.stdout:
            print("Intel Quick Sync detected - using h264_qsv")
            return 'h264_qsv'
    except:
        pass
    
    print("No GPU acceleration available - using CPU encoding")
    return 'libx264'

def main():
    if not SCREENSHOT_FOLDER.is_dir():
        print(f"Folder not found: {SCREENSHOT_FOLDER.resolve()}")
        sys.exit(1)

    files = [p for p in SCREENSHOT_FOLDER.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    files.sort(key=lambda p: p.stat().st_mtime)
    if not files:
        print(f"No images found in {SCREENSHOT_FOLDER.resolve()}")
        sys.exit(1)

    print(f"Found {len(files)} images to process...")

    image_paths = [str(p) for p in files]
    durations = [FRAME_DURATION] * len(image_paths)

    # Resize images before creating clip
    resized_image_paths, temp_dir = resize_images_threaded(image_paths)

    try:
        print("Creating video clip...")
        clip = mp.ImageSequenceClip(resized_image_paths, durations=durations)

        fps = max(1, int(round(1.0 / FRAME_DURATION)))
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

        # Get optimal codec
        codec = get_video_codec()
        
        print(f"Rendering video with {codec} codec at {fps} FPS... This may take a while...")
        video_start_time = time.time()
        
        # Optimized encoding parameters
        if codec == 'libx264':
            # CPU encoding - use all cores
            clip.write_videofile(
                OUTPUT_VIDEO,
                codec=codec,
                audio=False,
                fps=fps,
                preset="faster",  # Faster preset for CPU
                threads=mp_proc.cpu_count()
            )
        else:
            # GPU encoding - different parameters
            clip.write_videofile(
                OUTPUT_VIDEO,
                codec=codec,
                audio=False,
                fps=fps,
                ffmpeg_params=['-preset', 'fast', '-crf', '23']  # GPU-specific params
            )

        video_elapsed = time.time() - video_start_time
        print(f"✓ Video saved as {OUTPUT_VIDEO} from {len(image_paths)} frames in {video_elapsed:.1f}s")
        
        # Delete all original images using threading for I/O operations
        print("Cleaning up original images using threading...")
        cleanup_start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(32, len(files))) as executor:
            # Submit all deletion tasks
            future_to_file = {executor.submit(delete_single_file, file_path): file_path for file_path in files}
            deleted_count = 0
            
            # Process completed deletions with progress
            for future in as_completed(future_to_file):
                if future.result():
                    deleted_count += 1
                
                # Show progress every 100 deletions or every 20%
                if (deleted_count % 100 == 0 or 
                    deleted_count % max(1, len(files) // 5) == 0 or 
                    deleted_count == len(files)):
                    print(f"Deleted: {deleted_count}/{len(files)} files...")
        
        cleanup_elapsed = time.time() - cleanup_start_time
        print(f"✓ Deleted {deleted_count}/{len(files)} original images in {cleanup_elapsed:.1f}s")
        
    except Exception as e:
        print(f"Error during video creation: {e}")
        raise
        
    finally:
        # Clean up temporary files
        print("Cleaning up temporary files...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("✓ Temporary files cleaned up")

    print("Video creation complete!")

if __name__ == '__main__':
    main()