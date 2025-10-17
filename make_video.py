import moviepy as mp
from PIL import Image, ImageDraw, ImageFont
import os
import imageio_ffmpeg
from pathlib import Path
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp_proc
import time
from datetime import datetime, timedelta

SCREENSHOT_FOLDER = Path("chestScreenShot")
OUTPUT_VIDEO = "chest_openings.mp4"
FRAME_DURATION = 0.125  # 8x speed: 1/8 = 0.125 seconds per image (8 images per second)

def add_timestamp_to_image(args):
    """Function to resize and add timestamp to a single image - for threading"""
    img_path, target_size, output_path, timestamp = args
    try:
        with Image.open(img_path) as img:
            # Resize image
            img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed for drawing
            if img_resized.mode != 'RGB':
                img_resized = img_resized.convert('RGB')
            
            # Add timestamp
            draw = ImageDraw.Draw(img_resized)
            
            # Try to use a decent font, fallback to default if not available
            font_size = max(24, target_size[1] // 60)  # Scale font with image size
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            
            # Format timestamp
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get text size and position
            bbox = draw.textbbox((0, 0), time_str, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Position in top-left with padding
            x = 20
            y = 20
            
            # Add background rectangle for better readability
            padding = 10
            draw.rectangle([x-padding, y-padding, x+text_width+padding, y+text_height+padding], 
                         fill=(0, 0, 0, 180))  # Semi-transparent black background
            
            # Draw the timestamp text in white
            draw.text((x, y), time_str, font=font, fill=(255, 255, 255))
            
            img_resized.save(output_path)
        return True
    except Exception as e:
        print(f"Error processing {img_path}: {e}")
        return False

def delete_single_file(file_path):
    """Function to delete a single file - for threading"""
    try:
        file_path.unlink()
        return True
    except Exception as e:
        print(f"Failed to delete {file_path.name}: {e}")
        return False

def resize_and_timestamp_images(image_paths, target_size=None):
    """
    Resize all images to the same size and add timestamps using threading
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
    
    # Prepare arguments for threading with timestamps
    resize_args = []
    resized_paths = []
    
    # Calculate timestamps based on file creation time
    first_file_time = None
    for i, img_path in enumerate(image_paths):
        file_stat = Path(img_path).stat()
        file_time = datetime.fromtimestamp(file_stat.st_mtime)
        
        if first_file_time is None:
            first_file_time = file_time
        
        # Calculate relative time from first image
        relative_time = first_file_time + timedelta(seconds=i * 1)  # 1 second intervals in real time
        
        output_path = os.path.join(temp_dir, f"processed_{i:06d}.png")
        resize_args.append((img_path, target_size, output_path, relative_time))
        resized_paths.append(output_path)
    
    print("Processing images (resizing + adding timestamps)...")
    total_images = len(image_paths)
    
    max_workers = min(32, mp_proc.cpu_count() * 2)
    print(f"Using {max_workers} threads for image processing...")
    
    completed_count = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(add_timestamp_to_image, arg): i for i, arg in enumerate(resize_args)}
        
        for future in as_completed(future_to_index):
            completed_count += 1
            
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
    
    successful_resizes = completed_count
    elapsed_time = time.time() - start_time
    print(f"✓ Successfully processed {successful_resizes}/{total_images} images in {elapsed_time:.1f}s!")
    
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

def combine_videos(new_video_path, existing_video_path):
    """Combine new video with existing video"""
    print(f"Combining with existing video: {existing_video_path}")
    
    try:
        # Load both videos
        existing_clip = mp.VideoFileClip(existing_video_path)
        new_clip = mp.VideoFileClip(new_video_path)
        
        # Concatenate videos
        combined_clip = mp.concatenate_videoclips([existing_clip, new_clip])
        
        # Create temporary combined video
        temp_combined = "temp_combined.mp4"
        codec = get_video_codec()
        
        if codec == 'libx264':
            combined_clip.write_videofile(
                temp_combined,
                codec=codec,
                audio=False,
                preset="medium",
                threads=mp_proc.cpu_count(),
                bitrate="2000k"  # Compressed bitrate
            )
        else:
            combined_clip.write_videofile(
                temp_combined,
                codec=codec,
                audio=False,
                ffmpeg_params=['-preset', 'medium', '-crf', '28', '-b:v', '2000k']  # More compressed
            )
        
        # Close clips to free memory
        existing_clip.close()
        new_clip.close()
        combined_clip.close()
        
        # Replace original with combined
        shutil.move(temp_combined, existing_video_path)
        
        # Remove the new video file since it's now part of combined
        if os.path.exists(new_video_path):
            os.remove(new_video_path)
            
        print(f"✓ Videos combined successfully")
        return existing_video_path
        
    except Exception as e:
        print(f"Error combining videos: {e}")
        return new_video_path

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
    print(f"Video will be 8x speed ({len(files) * FRAME_DURATION:.1f}s total duration)")

    image_paths = [str(p) for p in files]
    durations = [FRAME_DURATION] * len(image_paths)

    # Process images (resize + timestamp)
    processed_image_paths, temp_dir = resize_and_timestamp_images(image_paths)

    try:
        print("Creating video clip...")
        clip = mp.ImageSequenceClip(processed_image_paths, durations=durations)

        fps = max(1, int(round(1.0 / FRAME_DURATION)))
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

        codec = get_video_codec()
        
        print(f"Rendering 8x speed video with {codec} codec at {fps} FPS...")
        video_start_time = time.time()
        
        # Check if video already exists
        final_video_path = OUTPUT_VIDEO
        if os.path.exists(OUTPUT_VIDEO):
            # Create new video with temporary name first
            temp_video = "temp_new_video.mp4"
            output_path = temp_video
        else:
            output_path = OUTPUT_VIDEO
        
        # Render with compression
        if codec == 'libx264':
            clip.write_videofile(
                output_path,
                codec=codec,
                audio=False,
                fps=fps,
                preset="medium",  # Better compression
                threads=mp_proc.cpu_count(),
                bitrate="2000k"  # Compressed bitrate (2 Mbps)
            )
        else:
            clip.write_videofile(
                output_path,
                codec=codec,
                audio=False,
                fps=fps,
                ffmpeg_params=['-preset', 'medium', '-crf', '28', '-b:v', '2000k']  # More compressed
            )

        # Close the clip to free memory
        clip.close()

        video_elapsed = time.time() - video_start_time
        print(f"✓ Video rendered in {video_elapsed:.1f}s")
        
        # Combine with existing video if it exists
        if os.path.exists(OUTPUT_VIDEO) and output_path != OUTPUT_VIDEO:
            final_video_path = combine_videos(output_path, OUTPUT_VIDEO)
        else:
            final_video_path = output_path
        
        # Get final file size
        file_size_mb = os.path.getsize(final_video_path) / (1024 * 1024)
        print(f"✓ Final video: {final_video_path} ({file_size_mb:.1f} MB)")
        
        # Delete all original images using threading
        print("Cleaning up original images...")
        cleanup_start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(32, len(files))) as executor:
            future_to_file = {executor.submit(delete_single_file, file_path): file_path for file_path in files}
            deleted_count = 0
            
            for future in as_completed(future_to_file):
                if future.result():
                    deleted_count += 1
                
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
        # Clean up any leftover temp files
        for temp_file in ["temp_new_video.mp4", "temp_combined.mp4"]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        print("✓ Temporary files cleaned up")

    print("Video creation complete!")

if __name__ == '__main__':
    main()