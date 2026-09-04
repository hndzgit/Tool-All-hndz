import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)
sys.path.append(os.path.join(base_dir, "automation"))

from automation.utils.sync_and_sub import process_video_pipeline
import config.config as cfg

def progress(val):
    print(f"PROGRESS: {val}%")

# We will run the pipeline with OCR only to see the pre-scan console output quickly
# Set config properties for testing
cfg.TARGET_LANGUAGE = "Tiếng Anh"
cfg.VBEE_VOICE = "gtts:en"

try:
    process_video_pipeline(
        "/Users/hoainam/Documents/Tiktok France/7652246960941894919.mp4",
        progress_callback=progress,
        use_hw_accel=False,
        add_sub=True,
        sub_source="ocr", 
        keep_bgm=True
    )
except Exception as e:
    print(f"PIPELINE CRASHED: {e}")