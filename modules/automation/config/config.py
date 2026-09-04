import os

# --- 1. CẤU HÌNH ĐƯỜNG DẪN TỰ ĐỘNG ---
# Tự động lấy đường dẫn gốc của thư mục VIDEO-AUTOMATION-PRO
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR_DEFAULT = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

FONT_PATH = os.path.join(ASSETS_DIR, "BeVietnamPro-Bold.ttf")

# Đảm bảo các thư mục luôn tồn tại (Trừ OUTPUT_DIR để khởi tạo động sau)
for d in [INPUT_DIR, TEMP_DIR, PROCESSED_DIR, ASSETS_DIR]:
    os.makedirs(d, exist_ok=True)

# --- 2. CẤU HÌNH AI & NGÔN NGỮ ---
import json

SETTINGS_FILE = os.path.join(BASE_DIR, "config", "settings.json")
QUEUE_FILE = os.path.join(BASE_DIR, "config", "queue.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "gemini_api_key": "", 
        "gemini_api_key_2": "", 
        "gemini_api_key_3": "", 
        "gemini_api_key_4": "", 
        "gemini_api_key_5": "", 
        "vbee_app_id": "", 
        "vbee_api_key": "", 
        "vbee_voice": "hn_female_ngochuyen_full_48k-fhg",
        "font_name": "BeVietnamPro-Bold.ttf",
        "font_size_scale_ngang": 1.0,
        "sub_y_pos_ngang": 0.85,
        "font_size_scale_doc": 1.0,
        "sub_y_pos_doc": 0.85,
        "max_concurrent_jobs": 2,
        "enable_watermark": False,
        "watermark_text": "@BanQuyenCuaToi",
        "watermark_size": 40,
        "watermark_opacity": 0.5,
        "watermark_position": "Góc phải - dưới",
        "enable_amf": True,
        "enable_sub": True,
        "enable_voice": True,
        "keep_bgm": True,
        "enable_blur": True,
        "enable_anti_reup": False,
        "reup_mirror": True,
        "reup_crop": True,
        "reup_color": True,
        "reup_speed": True,
        "reup_trim": True,
        "reup_audio_pitch": True,
        "reup_audio_eq": True,
        "reup_metadata": True,
        "convert_to_vertical": False,
        "enable_thumbnail": True,
        "target_language": "Tiếng Việt",
        "static_logo_blur": "Không",
        "output_dir": OUTPUT_DIR_DEFAULT,
        "rescue_srt_dir": os.path.join(OUTPUT_DIR_DEFAULT, "GIAI_DOAN_1_XUAT_THO"),
        "rescue_mp3_dir": "",
        "specified_product_name": "",
        "processing_mode": "Tự Động 100% (Tất Cả Trong Một)",
        "source_language": "Tự Động (AI)"
    }
def save_settings(new_settings):
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=4)

USER_SETTINGS = load_settings()
GEMINI_API_KEY = USER_SETTINGS.get("gemini_api_key", "")
GEMINI_API_KEY_2 = USER_SETTINGS.get("gemini_api_key_2", "")
GEMINI_API_KEY_3 = USER_SETTINGS.get("gemini_api_key_3", "")
GEMINI_API_KEY_4 = USER_SETTINGS.get("gemini_api_key_4", "")
GEMINI_API_KEY_5 = USER_SETTINGS.get("gemini_api_key_5", "")
VBEE_APP_ID = USER_SETTINGS.get("vbee_app_id", "")
VBEE_API_KEY = USER_SETTINGS.get("vbee_api_key", "")
VBEE_VOICE = USER_SETTINGS.get("vbee_voice", "hn_female_ngochuyen_full_48k-fhg") # Default voice
OUTPUT_DIR = USER_SETTINGS.get("output_dir", OUTPUT_DIR_DEFAULT)
if not os.path.exists(OUTPUT_DIR):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except:
        OUTPUT_DIR = OUTPUT_DIR_DEFAULT
        os.makedirs(OUTPUT_DIR, exist_ok=True)

RESCUE_SRT_DIR = USER_SETTINGS.get("rescue_srt_dir", os.path.join(OUTPUT_DIR_DEFAULT, "GIAI_DOAN_1_XUAT_THO"))
RESCUE_MP3_DIR = USER_SETTINGS.get("rescue_mp3_dir", "")
SPECIFIED_PRODUCT_NAME = USER_SETTINGS.get("specified_product_name", "")
PROCESSING_MODE = USER_SETTINGS.get("processing_mode", "Tự Động 100% (Tất Cả Trong Một)")
SOURCE_LANGUAGE = USER_SETTINGS.get("source_language", "Tự Động (AI)")

# --- BIẾN TOÀN CỤC CHO PHỤ ĐỀ (Thay đổi được qua UI) ---
FONT_NAME = USER_SETTINGS.get("font_name", "BeVietnamPro-Bold.ttf")
FONT_SIZE_SCALE_NGANG = USER_SETTINGS.get("font_size_scale_ngang", USER_SETTINGS.get("font_size_scale", 1.0))
SUB_Y_POS_NGANG = USER_SETTINGS.get("sub_y_pos_ngang", USER_SETTINGS.get("sub_y_pos", 0.85))
FONT_SIZE_SCALE_DOC = USER_SETTINGS.get("font_size_scale_doc", USER_SETTINGS.get("font_size_scale", 1.0))
SUB_Y_POS_DOC = USER_SETTINGS.get("sub_y_pos_doc", USER_SETTINGS.get("sub_y_pos", 0.85))

# Tùy chỉnh xử lý đa luồng (song song)
MAX_CONCURRENT_JOBS = USER_SETTINGS.get("max_concurrent_jobs", 2)

# Cấu hình Thumbnail Dán Ảnh Bìa
ENABLE_THUMBNAIL = USER_SETTINGS.get("enable_thumbnail", True)

# Ngôn ngữ mục tiêu dịch tự động
TARGET_LANGUAGE = USER_SETTINGS.get("target_language", "Tiếng Việt")

# Cấu hình Watermark (Đóng dấu video)
ENABLE_WATERMARK = USER_SETTINGS.get("enable_watermark", False)
WATERMARK_TEXT = USER_SETTINGS.get("watermark_text", "@BanQuyenCuaToi")
WATERMARK_SIZE = USER_SETTINGS.get("watermark_size", 40)
WATERMARK_OPACITY = USER_SETTINGS.get("watermark_opacity", 0.5)
WATERMARK_POSITION = USER_SETTINGS.get("watermark_position", "Góc phải - dưới")

# Gỡ lỗi voice cũ không còn hoạt động cho user cũ
if VBEE_VOICE == "hn-quynhanh":
    VBEE_VOICE = "hn_female_ngochuyen_full_48k-fhg"

# Cấu hình cài đặt nhanh
ENABLE_AMF = USER_SETTINGS.get("enable_amf", True)
ENABLE_SUB = USER_SETTINGS.get("enable_sub", True)
ENABLE_VOICE = USER_SETTINGS.get("enable_voice", True)
KEEP_BGM = USER_SETTINGS.get("keep_bgm", True)

# Cấu hình làm mờ
ENABLE_BLUR = USER_SETTINGS.get("enable_blur", True)
OCR_LANGUAGES = ['ch_sim', 'en']
BLUR_INTENSITY = (51, 51)         # Độ mờ (Càng to càng mờ, phải là số lẻ)
ROI_RATIO = USER_SETTINGS.get("ocr_roi_ratio", 0.50)  # Vùng quét chữ. Bản Đồ: 0.50 = Từ giữa xuống đáy. 0.0 = Quét toàn bộ video
STATIC_LOGO_BLUR = USER_SETTINGS.get("static_logo_blur", "Không") # Vị trí logo tĩnh cần che (Góc Trái Trên, Góc Phải Trên, etc)

# --- 3. CẤU HÌNH LÁ CHẮN CHỐNG REUP ---
ENABLE_ANTI_REUP = USER_SETTINGS.get("enable_anti_reup", False)
REUP_MIRROR = USER_SETTINGS.get("reup_mirror", True)
REUP_CROP = USER_SETTINGS.get("reup_crop", True)
REUP_COLOR = USER_SETTINGS.get("reup_color", True)
REUP_SPEED = USER_SETTINGS.get("reup_speed", True)
REUP_TRIM = USER_SETTINGS.get("reup_trim", True)
REUP_AUDIO_PITCH = USER_SETTINGS.get("reup_audio_pitch", True)
REUP_AUDIO_EQ = USER_SETTINGS.get("reup_audio_eq", True)
REUP_METADATA = USER_SETTINGS.get("reup_metadata", True)

# Tính năng chuyển Video Ngang → Dọc Bokeh (TikTok 9:16)
CONVERT_TO_VERTICAL = USER_SETTINGS.get("convert_to_vertical", False)