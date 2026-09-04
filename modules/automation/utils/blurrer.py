import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont
import config.config as cfg

# ===================================================
# PREMIUM BLUR ENGINE v4.0 - Polygon + Triple-Pass
# ===================================================
# - Polygon Mask: Dùng đúng hình dạng 4 góc từ EasyOCR (chữ xiên → blur xiên)
# - Triple-Pass: Pixelate → Heavy Gaussian → Medium Gaussian
# - Anti-Flicker: Chỉ blur đúng shape, không bị tràn ra ngoài
# ===================================================

_cached_fonts = {}

def get_cached_font(font_path, font_size):
    cache_key = (font_path, font_size)
    if cache_key not in _cached_fonts:
        try:
            _cached_fonts[cache_key] = ImageFont.truetype(font_path, font_size)
        except IOError:
            _cached_fonts[cache_key] = ImageFont.load_default()
    return _cached_fonts[cache_key]


def premium_blur(roi):
    """
    Triple-Pass Premium Censor Blur:
    Tầng 1: Pixelate Mosaic (kỹ thuật cảnh sát)
    Tầng 2: Heavy Gaussian tỷ lệ theo kích thước ROI
    Tầng 3: Medium Gaussian phủ mương
    """
    h, w = roi.shape[:2]
    if h < 2 or w < 2:
        return roi

    # Tầng 1: Pixelate
    pixel_size = max(6, w // 12)
    small = cv2.resize(roi, (max(1, w // pixel_size), max(1, h // pixel_size)), interpolation=cv2.INTER_LINEAR)
    mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    # Tầng 2: Heavy Gaussian
    ksize = max(51, (w // 3) | 1)
    if ksize % 2 == 0: ksize += 1
    blurred = cv2.GaussianBlur(mosaic, (ksize, ksize), 0)

    # Tầng 3: Medium Gaussian
    ksize2 = max(25, (w // 6) | 1)
    if ksize2 % 2 == 0: ksize2 += 1
    final = cv2.GaussianBlur(blurred, (ksize2, ksize2), 0)

    return final


def apply_polygon_blur(frame, item):
    """
    Áp dụng Blur theo đúng hình dạng polygon (4 góc thực tế từ EasyOCR).
    Chữ xiên góc → Blur xiên góc. Chữ thẳng → Blur thẳng.
    """
    fh, fw = frame.shape[:2]
    polygon = item.get("polygon")
    
    if polygon and len(polygon) == 4:
        # Tạo mask hình polygon chính xác
        pts = np.array(polygon, dtype=np.int32)
        # Mở rộng vùng đa giác thêm 4% (Padding) để bám khít theo chữ
        center = pts.mean(axis=0)
        padded_pts = (pts + (pts - center) * 0.04).astype(np.int32)
        padded_pts = np.clip(padded_pts, 0, [fw-1, fh-1])
        
        # Lấy bounding rect để chỉ blur vùng nhỏ (không blur cả frame → nhanh hơn)
        x, y, w, h = cv2.boundingRect(padded_pts)
        x, y = max(0, x), max(0, y)
        w = min(w, fw - x)
        h = min(h, fh - y)
        if w < 2 or h < 2:
            return frame
        
        # Blur toàn bộ bounding rect
        roi = frame[y:y+h, x:x+w]
        blurred_roi = premium_blur(roi)
        
        # Mask polygon: Chỉ copy vùng nằm trong polygon, không ảnh hưởng ngoài polygon
        mask = np.zeros((fh, fw), dtype=np.uint8)
        cv2.fillConvexPoly(mask, padded_pts, 255)
        mask_roi = mask[y:y+h, x:x+w]
        
        # Blend: pixel trong polygon → dùng blurred, ngoài → giữ nguyên
        for c in range(3):
            frame[y:y+h, x:x+w, c] = np.where(mask_roi > 0, blurred_roi[:, :, c], frame[y:y+h, x:x+w, c])
    
    else:
        # Fallback: dùng bounding box thông thường nếu không có polygon
        x_min, y_min, x_max, y_max = item["box"]
        x_min = max(0, x_min); y_min = max(0, y_min)
        x_max = min(fw, x_max); y_max = min(fh, y_max)
        if x_max > x_min and y_max > y_min:
            roi = frame[y_min:y_max, x_min:x_max]
            frame[y_min:y_max, x_min:x_max] = premium_blur(roi)
    
    return frame


def apply_blur_and_text(frame, detected_items, add_sub=True, bypass_filters=False):
    """Engine làm mờ và thêm chữ - v4.0 Polygon Mask."""
    frame_height, frame_width = frame.shape[:2]
    
    for item in detected_items:
        x_min, y_min, x_max, y_max = item["box"]
        translated_text = item.get("text", "")
        
        x_min = max(0, x_min); y_min = max(0, y_min)
        x_max = min(frame_width, x_max); y_max = min(frame_height, y_max)
        
        box_height = y_max - y_min
        box_width = x_max - x_min
        
        if not bypass_filters:
            # TỐI ƯU HÓA: BỘ LỌC KÍCH THƯỚC CƠ BẢN
            # Bỏ qua chữ quá nhỏ hoặc chữ quá dài tràn viền
            if box_height < frame_height * 0.015: continue
            if box_width > frame_width * 0.95: continue
            
            # Bỏ qua chữ lệch hẳn ra mép trái/phải (Thường là rác/watermark rìa)
            center_x = x_min + (box_width / 2)
            if center_x < frame_width * 0.15 or center_x > frame_width * 0.85:
                continue
            
        if x_max > x_min and box_height > 0:
            # Polygon Blur (theo đúng hình dạng chữ)
            frame = apply_polygon_blur(frame, item)
            
            if add_sub and translated_text:
                frame = put_vietnamese_text(frame, translated_text, (x_min, y_min), box_height=box_height)
            
    return frame


def put_vietnamese_text(img_cv2, text, position, box_height):
    img_pil = Image.fromarray(cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font_size = max(20, int(box_height * 0.9)) 
    font_path = os.path.join(cfg.ASSETS_DIR, cfg.FONT_NAME)
    font = get_cached_font(font_path, font_size)
    x, y = position
    y = y - int(box_height * 0.1) 
    draw.text((x, y), text, font=font, fill=(255,255,0), stroke_width=5, stroke_fill=(0,0,0))
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def wrap_text(text, max_width, font, draw_context):
    def get_text_size(t):
        t = t.strip()
        if not t: return 0, 0
        bbox = draw_context.textbbox((0, 0), t, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    width, _ = get_text_size(text)
    if width <= max_width:
        return [text]

    _wrapped_lines_ = []
    words = text.split(" ")
    _txt_ = ""
    processed = True
    for word in words:
        _before = _txt_
        _txt_ += f"{word} "
        _width, _ = get_text_size(_txt_)
        if _width <= max_width:
            continue
        if _txt_.strip() == word.strip():
            processed = False; break
        _wrapped_lines_.append(_before)
        _txt_ = f"{word} "
    _wrapped_lines_.append(_txt_)
    if processed:
        return [line.strip() for line in _wrapped_lines_ if line.strip()]

    _wrapped_lines_ = []
    _txt_ = ""
    for char in list(text):
        _txt_ += char
        _width, _ = get_text_size(_txt_)
        if _width > max_width:
            _wrapped_lines_.append(_txt_[:-1])
            _txt_ = char
    _wrapped_lines_.append(_txt_)
    return [line.strip() for line in _wrapped_lines_ if line.strip()]


def put_vietnamese_subtitle(img_cv2, text, width, height, active_results=None):
    # Chuẩn hoá và tách các dòng có sẵn ký tự xuống dòng (\n hoặc \N)
    text = text.replace("\\N", "\n").replace("\\n", "\n")
    raw_lines = text.split("\n")

    img_pil = Image.fromarray(cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    is_vertical = height > width
    if is_vertical:
        base_font_size = max(28, int(width * 0.045))
        y = int(height * cfg.SUB_Y_POS_DOC)
        font_size = int(base_font_size * cfg.FONT_SIZE_SCALE_DOC)
    else:
        base_font_size = max(32, int(height * 0.055)) 
        y = int(height * cfg.SUB_Y_POS_NGANG)
        font_size = int(base_font_size * cfg.FONT_SIZE_SCALE_NGANG)
    stroke_width = max(2, int(font_size * 0.05))
    try:
        font_path = cfg.FONT_NAME if (os.path.isabs(cfg.FONT_NAME) or os.path.exists(cfg.FONT_NAME)) else os.path.join(cfg.ASSETS_DIR, cfg.FONT_NAME)
        font = get_cached_font(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
    max_text_width = width * 0.9
    
    # Wrap từng dòng riêng biệt rồi gộp lại thành mảng lines phẳng
    lines = []
    for r_line in raw_lines:
        lines.extend(wrap_text(r_line, max_text_width, font, draw))
    
    # Mặc định: Neo dòng cuối cùng cố định tại Y để văn bản phát triển ngược lên trên khi có nhiều dòng (khoảng cách 1.65x tránh chạm dấu)
    line_height = int(font_size * 1.65)
    y_offset = y - (line_height * (len(lines) - 1))
    
    # CỐ ĐỊNH TỌA ĐỘ: Không cho phép Phụ đề mới nhảy múa theo tọa độ rung lắc của OCR nữa.
    # Sử dụng nguyên y_offset tĩnh đã tính ở trên (dựa theo cấu hình SUB_Y_POS)

    sub_color = getattr(cfg, "SUB_COLOR", (255, 255, 0))
    if isinstance(sub_color, str) and sub_color.startswith("#"):
        try:
            h = sub_color.lstrip('#')
            sub_color = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        except:
            sub_color = (255, 255, 0)

    sub_x_pos = getattr(cfg, "SUB_X_POS_DOC" if is_vertical else "SUB_X_POS_NGANG", 0.5)

    for line in lines:
        try:
            bbox = draw.textbbox((0,0), line, font=font)
            line_w = bbox[2] - bbox[0]
        except:
            line_w = font_size * len(line) * 0.5
        line_x = int(width * sub_x_pos - line_w / 2)
        draw.text((line_x, y_offset), line, font=font, fill=sub_color, stroke_width=stroke_width, stroke_fill=(0,0,0))
        y_offset += line_height
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)