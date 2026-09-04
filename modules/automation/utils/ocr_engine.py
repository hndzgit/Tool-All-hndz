import easyocr
import cv2
import re
import numpy as np
import threading
from config.config import OCR_LANGUAGES, ROI_RATIO

# Ổ khóa luồng: Bắt buộc các luồng phải xếp hàng khi dùng chung AI Model để tránh chết GPU/MPS
ocr_lock = threading.Lock()

reader = easyocr.Reader(OCR_LANGUAGES, gpu=True) # Bật GPU để tự kích hoạt Neural Engine/MPS trên Mac

def is_contains_chinese(text):
    if re.search(r'[\u4e00-\u9fff]', text):
        return True
    return False

def detect_text_in_frame(frame, scan_full_screen=False):
    height, width, _ = frame.shape
    
    import config.config as cfg
    roi_ratio = getattr(cfg, "ROI_RATIO", 0.50)
    
    # --- QUÉT MÀN HÌNH THEO CẤU HÌNH GIAO DIỆN ---
    if scan_full_screen:
        y_start = 0
    else:
        # roi_ratio là tỷ lệ phần trăm chiều cao quét từ đáy lên (ví dụ: 0.30 cho 30% dưới cùng)
        y_start = int(height * (1.0 - roi_ratio)) if 0.0 < roi_ratio < 1.0 else (0 if roi_ratio >= 1.0 else height)
    y_end = height 
    
    roi_frame = frame[y_start:y_end, 0:width]

    # --- NÂNG CẤP 1: TIỀN XỬ LÝ ẢNH ĐỂ TĂNG ĐỘ CHUẨN XÁC ---
    # 1. Chuyển sang ảnh xám
    gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    # 2. Tăng cường độ tương phản (Giúp chữ trắng/đen nổi bần bật)
    # Kỹ thuật CLAHE giúp làm rõ nét chữ trong vùng tối/sáng khác nhau
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced_gray = clahe.apply(gray)
    
    # AI sẽ quét trên ảnh đã được làm nét này. CÓ KHÓA CHỐNG SẬP GPU.
    with ocr_lock:
        results = reader.readtext(enhanced_gray, detail=1, paragraph=False)
    
    detected_data = []
    for bbox, text, prob in results:
        (top_left, top_right, bottom_right, bottom_left) = bbox
        
        # Tính toán tọa độ chuẩn
        y_min_real = int(min(top_left[1], top_right[1])) + y_start
        y_max_real = int(max(bottom_left[1], bottom_right[1])) + y_start
        x_min = int(min(top_left[0], bottom_left[0]))
        x_max = int(max(top_right[0], bottom_right[0]))
        
        box_height = y_max_real - y_min_real
        box_width = x_max - x_min

        # BỘ LỌC 1: KÍCH THƯỚC BẤT THƯỜNG
        if box_height < height * 0.015 or box_height > height * 0.40 or box_width < width * 0.02:
            continue
            
        # BỘ LỌC 3: PHÂN LOẠI NGÔN NGỮ (Kiểm tra trước để lọc thông minh theo địa lý)
        is_chinese = is_contains_chinese(text)
        
        # BỘ LỌC 2: VỊ TRÍ ĐỊA LÝ (Tuyệt đối không quét vùng giữa màn hình nếu không quét full)
        center_y = y_min_real + (box_height / 2)
        if not scan_full_screen:
            is_vertical = height > width
            min_y_limit = height * 0.60 if is_vertical else height * 0.70
            if is_chinese:
                # Tiếng Trung (Phụ đề gốc cần dịch): Chấp nhận vùng đáy (>= min_y_limit) hoặc vùng đỉnh (<25%)
                if not (height * 0.05 < center_y < height * 0.95) or (height * 0.25 < center_y < min_y_limit):
                    continue
            else:
                # Chữ Latinh/Rác khác: Phụ đề thật chỉ nằm ở Rìa Đáy (>70%) hoặc Rìa Đỉnh (<25%)
                if height * 0.25 < center_y < height * 0.70:
                    continue
            
        is_sub = False
        if is_chinese:
            is_sub = True
        else:
            if scan_full_screen:
                # Nếu quét full màn hình, chấp nhận mọi vị trí có xác suất tốt
                if prob > 0.3:
                    is_sub = True
            else:
                # Text Latinh hoặc rác -> Bắt buộc phải nằm ở nửa dưới video mới tính là Phụ Đề
                if y_min_real >= height * 0.45:
                    # Đáy màn hình thì chấp nhận làm mờ
                    if prob > 0.3:
                        is_sub = True

        if is_sub: 
            # Lưu đủ 4 góc polygon thực tế (để hỗ trợ blur hình xiên chéo)
            polygon_pts = [
                (int(top_left[0]),    int(top_left[1])    + y_start),
                (int(top_right[0]),   int(top_right[1])   + y_start),
                (int(bottom_right[0]),int(bottom_right[1])+ y_start),
                (int(bottom_left[0]), int(bottom_left[1]) + y_start),
            ]
            
            # Padding thông minh (Rộng hơn một chút để che hết bóng đổ của chữ)
            padding = 4
            detected_data.append({
                "box": (max(0, x_min - padding), max(0, y_min_real - padding), 
                        min(width, x_max + padding), min(height, y_max_real + padding)),
                "polygon": polygon_pts,
                "text": text
            })
            
    return detected_data
import datetime

def format_srt_time(seconds):
    dt = datetime.datetime.utcfromtimestamp(int(seconds))
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{dt.strftime('%H:%M:%S')},{milliseconds:03d}"

def extract_srt_from_video_ocr(video_path, srt_path):
    print("👁️ Đang quét video để trích xuất phụ đề (OCR Fallback)...")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30
    
    # Quét 2 frames mỗi giây để tối ưu tốc độ
    frame_jump = max(1, int(fps / 2))
    
    subs = []
    current_text = ""
    start_time = 0.0
    
    frame_count = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_time = frame_count / fps
        
        if frame_count % frame_jump == 0:
            raw_data = detect_text_in_frame(frame)
            if raw_data:
                # Gộp tất cả text tìm được trong frame (nếu có nhiều dòng)
                frame_text = " ".join([d['text'] for d in raw_data])
                
                if not current_text:
                    current_text = frame_text
                    start_time = frame_time
                elif frame_text != current_text:
                    # Chuyển sang câu mới
                    subs.append({
                        "start": start_time,
                        "end": frame_time,
                        "text": current_text
                    })
                    current_text = frame_text
                    start_time = frame_time
            else:
                if current_text:
                    subs.append({
                        "start": start_time,
                        "end": frame_time,
                        "text": current_text
                    })
                    current_text = ""
                    start_time = 0.0
                    
        frame_count += int(fps / 2)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
        
    cap.release()
    
    if current_text:
         subs.append({
             "start": start_time,
             "end": frame_time + 1.0,
             "text": current_text
         })
         
    # Ghi ra file SRT
    if not subs:
        print("⚠️ OCR không tìm thấy phụ đề nào trên màn hình.")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("")
        return False
        
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subs):
            f.write(f"{i+1}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")
            
    print(f"✅ Đã trích xuất SRT từ OCR thành công: {len(subs)} câu.")
    return True

# Compatibility alias for developer test scripts (test_ocr.py, test_ocr2.py)
detect_subtitle_boxes_in_frame = detect_text_in_frame