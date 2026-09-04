import sys
import os
import shutil

# Setup correct import path for the automation module
current_dir = os.path.dirname(os.path.abspath(__file__))
automation_dir = os.path.join(current_dir, "automation")
if automation_dir not in sys.path:
    sys.path.append(automation_dir)

import automation.config.config as cfg
from automation.utils.sync_and_sub import process_video_pipeline

# Force enable watermark for this test run
cfg.ENABLE_WATERMARK = True
cfg.WATERMARK_TEXT = "@TestWatermark"

def progress(val):
    print(f"PROGRESS: {val}%")

try:
    print("Testing Video Pipeline with forced Watermark...")
    process_video_pipeline(
        os.path.join(current_dir, "automation", "processed", "SnapVideoTools-1767976818352.mp4"),
        progress_callback=progress,
        use_hw_accel=False, # Faster for testing on CPU if needed
        add_sub=False # Skip sub processing to reach the end faster
    )
    print("Test finished.")
except Exception as e:
    print(f"PIPELINE CRASHED: {e}")