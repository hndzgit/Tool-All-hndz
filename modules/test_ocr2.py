import cv2
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from automation.utils.ocr_engine import detect_subtitle_boxes_in_frame
import tempfile

try:
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation/temp/temp_video_SnapVideoTools-1767976876026.mp4")
    if not os.path.exists(video_path):
        print(f"Video not found at: {video_path}")
        sys.exit(1)
        
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) // 2))
    ret, frame = cap.read()
    if ret:
        boxes = detect_subtitle_boxes_in_frame(frame)
        print(f"Boxes detected: {boxes}")
    else:
        print("Could not read frame")
except Exception as e:
    print(f"Error: {e}")