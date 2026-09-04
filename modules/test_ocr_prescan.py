import cv2
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from automation.utils.ocr_engine import detect_text_in_frame

input_video = "automation/processed/7389188474118720808.mp4" # I'll use a file from processed/ temp/
# The user's trace shows processing: "7389188474118720808.mp4"
# I'll find the video in the temp or processed directory