import cv2
import os
import shutil
import subprocess
import platform
from utils.ocr_engine import detect_text_in_frame
from utils.blurrer import apply_blur_and_text, put_vietnamese_subtitle
from utils.whisper_engine import extract_audio, transcribe_to_srt
from utils.gemini_translator import translate_srt_with_gemini
from utils.vbee_tts import generate_vbee_audio_from_srt
from utils.audio_separator import separate_audio
from config.config import TEMP_DIR, PROCESSED_DIR
import config.config as cfg
import numpy as np
import time

# Hàm landscape_to_vertical_bokeh cũ bằng OpenCV đã bị xóa vì gây nghẽn rác CPU.
# Việc tạo Bokeh giờ sẽ do phần cứng Apple GPU đảm nhiệm thông qua FFmpeg.

def cleanup_temp_files():
    """Dọn dẹp thư mục tạm"""
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
        except:
            pass
    os.makedirs(TEMP_DIR, exist_ok=True)

def parse_srt_to_list(srt_path):
    """Phân tích file SRT thành mảng các object chứa timecode giây"""
    import re
    if not os.path.exists(srt_path):
        return []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def time_to_sec(t_str):
        if not t_str: return 0
        h, m, s_ms = t_str.strip().split(':')
        s, ms = s_ms.split(',')
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
        
    pattern = re.compile(r'\d+\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n|\Z)', re.DOTALL)
    matches = pattern.findall(content)
    
    subs = []
    for start_str, end_str, text in matches:
        subs.append({
            "start": time_to_sec(start_str),
            "end": time_to_sec(end_str),
            "text": text.strip().replace('\n', ' ')
        })
    return subs

def generate_natural_filename(output_dir, prefix="IMG_", extension=".mov"):
    """
    Sinh ngẫu nhiên tên file dạng IMG_XXXX.mov không trùng lặp trong thư mục đầu ra.
    """
    import random
    os.makedirs(output_dir, exist_ok=True)
    for _ in range(1000):
        num = random.randint(1000, 9999)
        candidate = f"{prefix}{num:04d}{extension}"
        full_path = os.path.join(output_dir, candidate)
        if not os.path.exists(full_path):
            return candidate, full_path
    import time
    ts = int(time.time())
    return f"{prefix}{ts}{extension}", os.path.join(output_dir, f"{prefix}{ts}{extension}")

def process_video_pipeline(input_video_path, progress_callback=None, use_hw_accel=False, add_sub=True, add_voice=True, sub_source="audio", keep_bgm=True, processing_mode="Bình Thường (Tự Động 100%)", phase2_audio_dir="", file_index=1, phase1_export_dir="", enable_blur=True, manual_blur_boxes=None, order_image_path=None, enable_watermark=None, is_ai_video_pair=False, output_filename=None):
    """
    Hàm xử lý chính (Main Pipeline V2)
    """
    filename = os.path.basename(input_video_path)
    
    is_phase_1 = "Giai Đoạn 1" in processing_mode
    is_phase_2 = "Giai Đoạn 2" in processing_mode
    
    if is_phase_2:
        from .sync_and_sub_p2 import process_phase_2 # Put it in a new util to keep this clean!
        return process_phase_2(input_video_path, phase2_audio_dir, file_index, progress_callback, use_hw_accel, keep_bgm, phase1_export_dir=phase1_export_dir)
        
    if is_phase_1:
        add_voice = False # Tắt AI Voice để xuất thô
    
    # Hot-reload configurations to bypass Thread/Process caching issues
    live_cfg = cfg.load_settings()
    cfg.ENABLE_ANTI_REUP = live_cfg.get("enable_anti_reup", False)
    cfg.REUP_MIRROR = live_cfg.get("reup_mirror", True)
    cfg.REUP_CROP = live_cfg.get("reup_crop", True)
    cfg.REUP_COLOR = live_cfg.get("reup_color", True)
    cfg.REUP_SPEED = False if is_ai_video_pair else live_cfg.get("reup_speed", True)
    cfg.REUP_TRIM = False if is_ai_video_pair else live_cfg.get("reup_trim", True)
    cfg.REUP_AUDIO_PITCH = live_cfg.get("reup_audio_pitch", True)
    cfg.REUP_AUDIO_EQ = live_cfg.get("reup_audio_eq", True)
    cfg.REUP_METADATA = live_cfg.get("reup_metadata", True)
    
    print(f"DEBUG: Tình trạng Lá Chắn Chống Reup: {cfg.ENABLE_ANTI_REUP}")
    
    # Fix: Get the live OUTPUT_DIR from config in case it was changed by GUI
    if output_filename:
        output_name = output_filename
        output_video_path = os.path.join(cfg.OUTPUT_DIR, output_filename)
    else:
        output_name, output_video_path = generate_natural_filename(cfg.OUTPUT_DIR)
    
    temp_original_audio = os.path.join(TEMP_DIR, f"original_audio_{filename}.mp3")
    temp_original_srt = os.path.join(TEMP_DIR, f"original_{filename}.srt")
    temp_translated_srt = os.path.join(TEMP_DIR, f"translated_{filename}.srt")
    temp_ai_audio_path = os.path.join(TEMP_DIR, f"vbee_audio_{filename}.mp3")
    temp_video_no_audio = os.path.join(TEMP_DIR, f"temp_video_{filename}")
    
    # --- CLEAN SLATE CHIẾN LƯỢC: CHỐNG LỖI GHOST FILES KHI XỬ LÝ HÀNG LOẠT BATCH ---
    for temp_str in [temp_original_audio, temp_original_srt, temp_translated_srt, temp_ai_audio_path, temp_video_no_audio]:
        if os.path.exists(temp_str):
            try:
                os.remove(temp_str)
            except:
                pass

    cap_temp = cv2.VideoCapture(input_video_path)
    fps_temp = cap_temp.get(cv2.CAP_PROP_FPS) or 25
    frames_temp = cap_temp.get(cv2.CAP_PROP_FRAME_COUNT) or 100
    video_duration = frames_temp / fps_temp if fps_temp else 0
    cap_temp.release()

    print(f"🎬 [START Hn.dz tool] Đang xử lý: {filename}")
    
    # 1. TRÍCH XUẤT ÂM THANH & TÁCH NỀN (NẾU CẦN)
    if progress_callback: progress_callback(5)
    extract_audio(input_video_path, temp_original_audio)
    
    vocals_audio = temp_original_audio
    bgm_audio = None
    
    if keep_bgm and os.path.exists(temp_original_audio):
        print("🎧 Đang tách nhạc nền và giọng nói gốc...")
        v_path, nv_path = separate_audio(temp_original_audio, TEMP_DIR)
        if v_path and nv_path:
            vocals_audio = v_path # Dùng giọng nói để Whisper nhận diện
            bgm_audio = nv_path   # Nhạc nền để ghép lại khúc cuối
            
            # --- ÁP DỤNG AUDIO SPOOFING (CHỐNG REUP) LÊN NHẠC NỀN ---
            if cfg.ENABLE_ANTI_REUP and (cfg.REUP_AUDIO_PITCH or cfg.REUP_AUDIO_EQ):
                print("🛡️ Đang áp dụng khiên tàng hình Âm Thanh (Anti-Reup Audio)...")
                audio_filters = []
                # [MẠNH HƠN TIKTOK]: Trí tuệ ảo hóa Phân tử âm thanh (Acoustic Fingerprint Destruction)
                # Nâng tông 4% + Dịch pha tần số (Phaser) + Rung âm lượng liti (Tremolo) đè sập điểm neo FFT
                if cfg.REUP_AUDIO_PITCH: 
                    audio_filters.append("asetrate=44100*1.04,aresample=44100,aphaser=type=t:speed=2:decay=0.4,tremolo=f=4.0:d=0.2")
                
                # [MẠNH HƠN TIKTOK]: Bóp méo dải phổ (V-Shape Spectral Crushing)
                # Đẩy Max Bass +10dB, Xóa sổ dải Trung (-5dB ở 1000Hz), Kéo Treble +5dB để làm AI nhận diện bài hát bị "Mù"
                if cfg.REUP_AUDIO_EQ: 
                    audio_filters.append("bass=g=10:f=110:w=0.6,equalizer=f=1000:width_type=h:width=200:g=-5,treble=g=5:f=8000:w=0.5")
                
                if audio_filters:
                    reup_audio_path = os.path.join(TEMP_DIR, f"reup_bgm_{filename}.mp3")
                    filter_str = ",".join(audio_filters)
                    
                    cmd = ['ffmpeg', '-y', '-threads', '10', '-i', bgm_audio, '-af', filter_str, reup_audio_path]
                    process = subprocess.run(cmd, capture_output=True, text=True)
                    if process.returncode == 0 and os.path.exists(reup_audio_path):
                        bgm_audio = reup_audio_path # Tráo đổi con bài nhạc nền đã bị bóp méo
                        print("✅ Đã hack tông/wave âm thanh thành công!")
                    else:
                        print(f"⚠️ Lỗi xử lý âm thanh Anti-Reup: {process.stderr[-200:] if process.stderr else 'Undefined'}")
    
    # 2. XỬ LÝ PHỤ ĐỀ & LỒNG TIẾNG
    subs_data = []
    original_subs = []
    use_vbee = False
    
    if add_sub or add_voice:
        methods_to_try = []
        if sub_source == "image":
            methods_to_try = ["image"]
        elif sub_source == "audio":
            methods_to_try = ["audio", "ocr"]
        else:
            methods_to_try = ["ocr", "audio"]
            
        is_ai_generated = False
        
        for method in methods_to_try:
            # Dọn dẹp tàn dư của phương pháp trước
            for fpath in [temp_original_srt, temp_translated_srt]:
                if os.path.exists(fpath):
                    try: os.remove(fpath)
                    except: pass
            
            print(f"🔄 Đang thử lấy phụ đề bằng phương pháp: {method.upper()}...")
            original_subs = []
            
            if method == "audio":
                if progress_callback: progress_callback(10)
                if not os.path.exists(vocals_audio) or os.path.getsize(vocals_audio) == 0:
                    print("⚠️ Video không có âm thanh hoặc file âm thanh rỗng.")
                    continue
                else:
                    print("🎙️ Đang nhận diện giọng nói (Whisper)...")
                    try:
                        transcribe_to_srt(vocals_audio, temp_original_srt)
                        original_subs = parse_srt_to_list(temp_original_srt)
                    except Exception as e:
                        print(f"⚠️ Whisper gặp lỗi nhận diện: {e}")
                        continue
            if method == "image":
                if progress_callback: progress_callback(10)
                print(f"🖼️ Chế độ ảnh sản phẩm: Đang gọi Gemini phân tích đơn hàng...")
                from utils.gemini_vision import generate_ai_srt_from_image
                generate_ai_srt_from_image(order_image_path, video_duration, temp_translated_srt)
                if os.path.exists(temp_translated_srt) and os.path.getsize(temp_translated_srt) > 10:
                    original_subs = parse_srt_to_list(temp_translated_srt)
                    is_ai_generated = True
            elif method == "ocr":
                if progress_callback: progress_callback(10)
                print("👁️ Chế độ OCR: Sẽ quét toàn bộ video để tìm chữ...")
                from utils.ocr_engine import extract_srt_from_video_ocr
                extract_srt_from_video_ocr(input_video_path, temp_original_srt)
                original_subs = parse_srt_to_list(temp_original_srt)
            elif method == "vision":
                print("⚠️ Cả âm thanh và Chữ đều TRỐNG! Tự động đánh thức Lò Hạt Nhân Mắt Thần AI (Gemini Vision) để tự Sáng Tác Kịch Bản...")
                from utils.gemini_vision import generate_ai_srt_from_video
                ai_srt_path = generate_ai_srt_from_video(input_video_path, temp_translated_srt, video_duration=video_duration)
                if ai_srt_path:
                    original_subs = parse_srt_to_list(temp_translated_srt)
                    is_ai_generated = True
            
            # Nếu phương pháp này tìm thấy phụ đề gốc, tiến hành dịch & thẩm định
            if original_subs:
                if is_ai_generated:
                    print("🤖 (Bỏ qua Dịch thuật vì Mắt Thần AI đã nhả Code SRT Thuần Việt 100%)")
                    shutil.copy(temp_translated_srt, temp_original_srt)
                else:
                    if progress_callback: progress_callback(25)
                    print("🤖 Đang dịch thuật (Gemini)...")
                    try:
                        translate_srt_with_gemini(temp_original_srt, temp_translated_srt)
                    except Exception as e:
                        print(f"⚠️ Lỗi dịch thuật Gemini: {e}")
                        continue
                
                # Thẩm định kết quả dịch thuật (tránh trường hợp OCR rác bị Gemini xoá rỗng)
                if os.path.exists(temp_translated_srt) and os.path.getsize(temp_translated_srt) > 10:
                    subs_data = parse_srt_to_list(temp_translated_srt)
                    if subs_data:
                        print(f"✅ Lấy phụ đề thành công bằng phương pháp: {method.upper()} ({len(subs_data)} câu).")
                        break
                    else:
                        print(f"⚠️ Phương pháp {method.upper()} trả về phụ đề rỗng sau dịch.")
                else:
                    print(f"⚠️ Phương pháp {method.upper()} bị Gemini từ chối (rác/bài hát/không dịch được).")
                    
        if subs_data:
            if add_voice:
                if progress_callback: progress_callback(40)
                voice_code = cfg.VBEE_VOICE
                
                # Dynamic random voice selection
                if not voice_code or "random" in voice_code.lower():
                    import random
                    vbee_pool = [
                        "hn_female_ngochuyen_full_48k-fhg",
                        "hn_female_maiphuong_ngam_48k-fhg",
                        "hn_female_thaotrinh_full_48k-fhg",
                        "sg_female_huonggiang_full_48k-fhg",
                        "sg_male_minhhoang_full_48k-fhg",
                        "hn_male_minhquan_yt-stable",
                        "hn_male_phuthang_news65dt_44k-fhg",
                        "hue_male_duyphuong_full_48k-fhg",
                        "n_hanoi_female_dieuhuong20260421111346189_news_vc",
                        "n_tuyenquang_female_vuthilanhuong_advertise_vc",
                        "n_hanoi_female_ngocanhdangg_book_vc",
                        "n_hanoi_male_namnhenhangamap_story_vc",
                        "n_hanoi_male_sizonguyen_education_vc",
                        "n_hanoi_male_nhabaohoangnam_news_vc"
                    ]
                    selected_voice = random.choice(vbee_pool)
                    voice_code = f"vbee:{selected_voice}"
                    print(f"🎲 [Random Voice] Đã chọn ngẫu nhiên giọng lồng tiếng cho video: {selected_voice}")
                    
                print(f"🔊 Đang tạo giọng đọc AI ({voice_code})...")
                try:
                    if voice_code.startswith("gtts:"):
                        from .gtts_engine import generate_gtts_audio_from_srt
                        generate_gtts_audio_from_srt(temp_translated_srt, temp_ai_audio_path, voice_code=voice_code)
                    else:    
                        generate_vbee_audio_from_srt(temp_translated_srt, temp_ai_audio_path, voice_code=voice_code)
                    
                    use_vbee = True  # Variable name stays use_vbee for backward compatibility with downstream MoviePy mixing
                    
                    # Cập nhật lại list phụ đề vì TTS engine đã phân bổ lại timeline chuẩn khớp
                    subs_data = parse_srt_to_list(temp_translated_srt)
                except Exception as e:
                    print(f"⚠️ Lỗi tạo giọng đọc AI: {e}")
        else:
            print("⚠️ Video không có giọng nói lẫn chữ trên hình. Sẽ chỉ xử lý làm mờ và giữ nguyên âm thanh gốc.")

    # 3. XỬ LÝ VIDEO: BLUR & BURN SUBTITLE
    if progress_callback: progress_callback(55)
    cap = cv2.VideoCapture(input_video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # === GHI CHÚ GIAI ĐOẠN 1: OPENCV CHỈ RENDER PHỤ ĐỀ, KHÔNG LÀM BOKEH ===
    # Bản cập nhật: Kích hoạt Bokeh HW cho TOÀN BỘ video khác tỷ lệ 9:16 (Bao gồm Vuông 1:1, 4:5...)
    is_landscape = cfg.CONVERT_TO_VERTICAL and abs(width / height - 9/16) > 0.05
    target_out_h = int(width * 16 / 9) if is_landscape else height
    if is_landscape:
        print(f"📐 Phát hiện video chưa chuẩn tỷ lệ 9:16 ({width}x{height}) → Chuyển dọc 9:16 ở bước phần cứng (Bokeh HW Acceleration)")

    import platform
    success = False
    codecs_to_try = ['avc1', 'mp4v', 'MJPG'] if platform.system() == "Darwin" else ['mp4v', 'avc1', 'XVID', 'MJPG']
    
    for codec_name in codecs_to_try:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec_name)
            out = cv2.VideoWriter(temp_video_no_audio, fourcc, fps, (width, height))
            if out.isOpened():
                # Ghi thử 1 frame đen để kiểm tra xem file có thực sự ghi được xuống ổ đĩa không (tránh lỗi câm trên Mac)
                dummy_frame = np.zeros((height, width, 3), dtype=np.uint8)
                out.write(dummy_frame)
                out.release()
                
                if os.path.exists(temp_video_no_audio) and os.path.getsize(temp_video_no_audio) > 0:
                    print(f"✅ VideoWriter initialized successfully with codec: {codec_name}")
                    # Khởi tạo lại để ghi thật (sẽ ghi đè/xóa file test)
                    out = cv2.VideoWriter(temp_video_no_audio, fourcc, fps, (width, height))
                    success = True
                    break
                else:
                    print(f"⚠️ Codec {codec_name} opened but failed to write data on disk.")
                    if os.path.exists(temp_video_no_audio):
                        os.remove(temp_video_no_audio)
        except Exception as e:
            print(f"⚠️ Failed to try codec {codec_name}: {e}")
            if os.path.exists(temp_video_no_audio):
                try: os.remove(temp_video_no_audio)
                except: pass
                
    if not success:
        raise Exception("Không thể khởi tạo cv2.VideoWriter với bất kỳ codec nào trong danh sách!")
    
    from automation.utils.blurrer import apply_blur_and_text
    from automation.utils.ocr_engine import detect_text_in_frame
    
    # === STATIC LOGO BLUR PRE-CALCULATION & FULL-VIDEO OCR SCAN ===
    static_logo_boxes = []
    blur_segments = []
    
    if enable_blur:
        if getattr(cfg, "STATIC_LOGO_BLUR", "Không") != "Không":
            pos = cfg.STATIC_LOGO_BLUR
            # Kích thước tiêu chuẩn: Dài 32% Rộng, Cao 12% Cao (Đủ che Logo TikTok/Douyin và User ID)
            logo_w, logo_h = int(width * 0.32), int(height * 0.12)
            margin_x, margin_y = int(width * 0.02), int(height * 0.02)
            
            if pos == "Góc Phải Trên":
                box = (max(0, width - logo_w - margin_x), margin_y, width - margin_x, margin_y + logo_h)
            elif pos == "Góc Trái Trên":
                box = (margin_x, margin_y, margin_x + logo_w, margin_y + logo_h)
            elif pos == "Góc Phải Dưới":
                box = (max(0, width - logo_w - margin_x), max(0, height - logo_h - margin_y), width - margin_x, height - margin_y)
            elif pos == "Góc Trái Dưới":
                box = (margin_x, max(0, height - logo_h - margin_y), margin_x + logo_w, height - margin_y)
            else:
                box = None
                
            if box:
                static_logo_boxes.append({"box": box, "text": ""})
                print(f"🛑 Đã kích hoạt Che Logo Tĩnh: {pos} {box}")

        # === FULL-VIDEO PER-SECOND OCR SCAN ===
        # Quét phần dưới video theo cấu hình ocr_roi_ratio, mỗi 0.5 giây 1 lần để có độ phân giải thời gian tốt nhất.
        # Không phụ thuộc vào SRT. Không bỏ sót đoạn nào.
        if progress_callback: progress_callback(55)
        roi_ratio = getattr(cfg, "ROI_RATIO", 0.50)
        print(f"🔍 Full-Video OCR Scan (mỗi 0.5 giây, vùng quét: {int(roi_ratio * 100)}% từ đáy)...")

        SCAN_STEP = 0.5  # 0.5 giây/lần — chuẩn và bao quát toàn video chính xác hơn
        raw_ocr_map = {} # {t_sec: [{"box": [], "text": ""}]}
        
        video_duration = total_frames / fps
        total_scan_steps = int(video_duration / SCAN_STEP) + 1
        scan_times = [round(i * SCAN_STEP, 1) for i in range(total_scan_steps)]

        cap_scan = cv2.VideoCapture(input_video_path)
        # Cố định nhỏ padding để vừa khít chữ
        pad_y = 2
        pad_x = 4
        
        for i, t in enumerate(scan_times):
            frame_idx = int(t * fps)
            cap_scan.set(cv2.CAP_PROP_POS_MSEC, t * 1000)  # Dùng millisecond để chính xác hơn
            ret, scan_frame = cap_scan.read()
            if not ret:
                continue

            raw_ocr = detect_text_in_frame(scan_frame, scan_full_screen=False)
            if raw_ocr:
                raw_ocr_map[t] = raw_ocr

            # In tiến trình để user thấy đang quét (mỗi 10 giây)
            if i % 20 == 0:
                print(f"   ⏱ Đang quét: giây {t:.0f}/{video_duration:.0f} | Tìm thấy chữ: {len(raw_ocr_map)} mốc")
            if progress_callback and i % 20 == 0:
                p = 55 + int((i / max(total_scan_steps, 1)) * 10)
                progress_callback(min(65, p))

        cap_scan.release()
        print(f"✅ Scan xong: {len(raw_ocr_map)} mốc có chữ / {len(scan_times)} mốc tổng")

        # === AI TỰ ĐỘNG PHÁT HIỆN LOGO TĨNH ===
        # Gom cụm các hộp chữ dựa trên khoảng cách. Nếu xuất hiện ở cùng 1 chỗ >= 25% thời lượng video -> Logo Tĩnh!
        clusters = [] # [{"center": (cx, cy), "frames": set(), "box_union": [min_x, min_y, max_x, max_y]}]
        for t_sec, ocr_items in raw_ocr_map.items():
            for item in ocr_items:
                b = item["box"]
                cx = (b[0] + b[2]) / 2
                cy = (b[1] + b[3]) / 2
                
                # Tìm cluster phù hợp (chuẩn sai lệch tâm < 40 pixel)
                matched = False
                for cl in clusters:
                    if abs(cl["center"][0] - cx) < 40 and abs(cl["center"][1] - cy) < 40:
                        cl["frames"].add(t_sec)
                        cb = cl["box_union"]
                        cl["box_union"] = [min(cb[0], b[0]), min(cb[1], b[1]), max(cb[2], b[2]), max(cb[3], b[3])]
                        # Cập nhật trung bình tâm
                        l = len(cl["frames"])
                        cl["center"] = ((cl["center"][0] * (l - 1) + cx) / l, (cl["center"][1] * (l - 1) + cy) / l)
                        matched = True
                        break
                
                if not matched:
                    clusters.append({
                        "center": (cx, cy),
                        "frames": {t_sec},
                        "box_union": [b[0], b[1], b[2], b[3]]
                    })

        ai_static_logos = []
        # Kích hoạt logo tự động nếu nó có tần suất xuất hiện > 75% thời lượng video (tránh đánh nhầm sub động thành logo tĩnh)
        THRESHOLD_FRAMES = max(3, int(total_scan_steps * 0.75))
        for cl in clusters:
            if len(cl["frames"]) >= THRESHOLD_FRAMES:
                cb = cl["box_union"]
                # Thêm padding nhẹ
                pad = 10
                cb_padded = (max(0, cb[0] - pad), max(0, cb[1] - pad), min(width, cb[2] + pad), min(height, cb[3] + pad))
                ai_static_logos.append(cb_padded)
                # Thêm trực tiếp vào Master Static Boxes
                static_logo_boxes.append({"box": cb_padded, "text": ""})
                print(f"🤖 Đã Tự Động Định Vị 1 Logo Tĩnh (Xuất hiện {len(cl['frames'])}/{total_scan_steps} mốc): {cb_padded}")

        def is_inside_static_logo(bx):
            for s_box in ai_static_logos:
                # Nếu tâm của text nằm trong hộp của logo tĩnh
                cx, cy = (bx[0] + bx[2])/2, (bx[1] + bx[3])/2
                if s_box[0] <= cx <= s_box[2] and s_box[1] <= cy <= s_box[3]:
                    return True
            return False

        # === GOM CỤM SUB ĐỘNG VÀ TÌM KHUNG HÌNH DÀI NHẤT ===
        # Lọc các chữ không thuộc vùng logo tĩnh, có kích thước của subtitle hợp lệ
        dynamic_ocr_items = []
        for t_sec, ocr_items in raw_ocr_map.items():
            for item in ocr_items:
                b = item["box"]
                if is_inside_static_logo(b):
                    continue
                    
                box_w = b[2] - b[0]
                box_h = b[3] - b[1]
                
                # Lọc theo tiêu chuẩn phụ đề chính chủ (Subtitle)
                is_valid_height = height * 0.015 < box_h < height * 0.08
                is_long_text = (box_w > box_h * 1.8) and (box_w > width * 0.08)
                
                # Subtitle phải nằm ở vùng đáy của video, không nằm ở vùng giữa/trên
                # Tránh hoàn toàn việc quét/làm mờ vùng từ giữa lên trên (e.g. y_min < 62% chiều cao video dọc, hoặc < 70% video ngang)
                is_vertical = height > width
                min_y_limit = height * 0.62 if is_vertical else height * 0.70
                is_in_sub_area = b[1] >= min_y_limit
                
                # Subtitle luôn căn giữa màn hình (loại bỏ sticker/logo ở góc trái/phải)
                center_x = b[0] + (box_w / 2)
                is_centered = abs(center_x - width / 2) < width * 0.18
                
                if is_valid_height and is_long_text and is_in_sub_area and is_centered:
                    dynamic_ocr_items.append({
                        "time": t_sec,
                        "box": b,
                        "polygon": item.get("polygon"),
                        "text": item.get("text", "")
                    })

        # Sắp xếp theo trình tự thời gian
        dynamic_ocr_items.sort(key=lambda x: x["time"])
        sub_segments = []
        for item in dynamic_ocr_items:
            placed = False
            for seg in sub_segments:
                last_item = seg[-1]
                time_gap = item["time"] - last_item["time"]
                # Gom cụm các phát hiện cách nhau không quá 1.5 giây và thẳng hàng dọc (Y)
                if time_gap <= 1.5:
                    y1_last, y2_last = last_item["box"][1], last_item["box"][3]
                    y1_curr, y2_curr = item["box"][1], item["box"][3]
                    
                    overlap = min(y2_last, y2_curr) - max(y1_last, y1_curr)
                    h_last = y2_last - y1_last
                    h_curr = y2_curr - y1_curr
                    min_h = min(h_last, h_curr)
                    
                    cy_last = (y1_last + y2_last) / 2
                    cy_curr = (y1_curr + y2_curr) / 2
                    
                    if overlap > 0.5 * min_h or abs(cy_last - cy_curr) < 20:
                        seg.append(item)
                        placed = True
                        break
            if not placed:
                sub_segments.append([item])

        # Tạo danh sách các hộp làm mờ động theo thời gian xuất hiện thực tế của phân đoạn phụ đề (Subtitle Segments)
        # Giúp mờ đúng lúc chữ xuất hiện, tắt đi khi chữ biến mất, và chỉ mờ đúng vùng có chữ chứ không làm mờ vĩnh viễn video.
        for seg in sub_segments:
            # Tọa độ X và Y bao phủ toàn bộ segment này
            y_min_all = min(x["box"][1] for x in seg)
            y_max_all = max(x["box"][3] for x in seg)
            x_min_all = min(x["box"][0] for x in seg)
            x_max_all = max(x["box"][2] for x in seg)
            
            # Áp dụng padding rộng rãi để che phủ hoàn hảo chữ nhảy
            pad_y_val = max(10, pad_y)
            y_min = max(0, y_min_all - pad_y_val)
            y_max = min(height, y_max_all + pad_y_val)
            
            # Chỉ che phủ chiều ngang thực tế của hộp chữ (cộng biên an toàn 30px)
            pad_x_val = 30
            x_min = max(0, x_min_all - pad_x_val)
            x_max = min(width, x_max_all + pad_x_val)
            
            # Lấy thời gian bắt đầu và kết thúc của phân đoạn này
            times = [x["time"] for x in seg]
            t_start = min(times)
            t_end = max(times)
            
            # Thêm padding thời gian (0.4s) để tránh bị chớp giật hoặc leak chữ ở khung hình chuyển cảnh đầu/cuối
            start_time = max(0.0, t_start - 0.4)
            end_time = min(video_duration, t_end + 0.4)
            
            blur_segments.append({
                "start": start_time,
                "end": end_time,
                "box": (x_min, y_min, x_max, y_max),
                "polygon": None,  # Đóng cứng hộp chữ nhật để bao phủ toàn bộ vùng dao động của chữ nhảy
                "text": ""
            })

    def get_blur_boxes_at_time(current_t):
        """Trả về danh sách hộp mờ của các đoạn sub hoạt động tại thời điểm current_t."""
        active_boxes = []
        for bs in blur_segments:
            if bs["start"] <= current_t <= bs["end"]:
                active_boxes.append({
                    "box": bs["box"],
                    "polygon": bs["polygon"],
                    "text": ""
                })
        return active_boxes

    # Backward compatibility cho code khác nếu có tham chiếu tới all_keyframe_times / original_subs
    all_keyframe_times = [bs["start"] for bs in blur_segments]
    if original_subs:
        for sub in original_subs:
            sub["keyframe_times"] = [t for t in all_keyframe_times if sub["start"] - 0.5 <= t <= sub["end"] + 0.5]
            # Gán box đầu tiên tìm được
            matched_segs = [bs for bs in blur_segments if bs["start"] <= sub["start"] <= bs["end"]]
            sub["target_blur_boxes"] = [{"box": bs["box"], "polygon": bs["polygon"], "text": ""} for bs in matched_segs]

    if progress_callback: progress_callback(65)
    print("🚀 Đang Render Video hoàn chỉnh (Premium Blur Engine v3.0)...")
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame_count += 1
        current_time_sec = frame_count / fps
        
        # --- A1. LẬT NGANG (ANTI-REUP) ---
        if cfg.ENABLE_ANTI_REUP and cfg.REUP_MIRROR:
            frame = cv2.flip(frame, 1)
        
        # === A. BLUR ENGINE: QUERY GLOBAL KEYFRAME MAP DIRECTLY ===
        active_blur_boxes = get_blur_boxes_at_time(current_time_sec)
        
        manual_blur_items = []
        if manual_blur_boxes:
            for (x1, y1, x2, y2) in manual_blur_boxes:
                manual_blur_items.append({
                    "box": [x1, y1, x2, y2],
                    "polygon": None,
                    "text": ""
                })
        
        combined_blur_boxes = active_blur_boxes + static_logo_boxes + manual_blur_items
        if combined_blur_boxes:
            frame = apply_blur_and_text(frame, combined_blur_boxes, add_sub=False, bypass_filters=True)


        # --- B. IN PHỤ ĐỀ MỚI ---
        if add_sub and subs_data:
            current_sub = next((s["text"] for s in subs_data if s["start"] <= current_time_sec <= s["end"]), None)
            if current_sub:
                frame = put_vietnamese_subtitle(frame, current_sub, width, height, active_blur_boxes)
        
        # === LANDSCAPE → VERTICAL BOKEH CONVERSION ===
        # Đã bị xoá khỏi CPU Loop. Chỉ viết frame gốc ra file tạm để FFmpeg scale bằng GPU ở bước 5.
        
        
        out.write(frame)
        
        if frame_count % 30 == 0 and progress_callback:
            progress_base = 55
            progress_added = int((frame_count / total_frames) * 30)
            progress_callback(progress_base + progress_added)

    cap.release()
    out.release()

    # 5. MERGE ÂM THANH VÀ VIDEO BẰNG FFMPEG NATIVE (HW ACCEL)
    if progress_callback: progress_callback(85)
    
    try:
        print("🚀 Đang khởi động FFmpeg Multiplexing (Bypass MoviePy)...")
        ffmpeg_cmd = ['ffmpeg', '-y']
        
        # Inputs
        ffmpeg_cmd.extend(['-i', temp_video_no_audio]) # [0:v]
        
        audio_idx_ai = -1
        audio_idx_bgm = -1
        audio_idx_orig = -1
        
        input_idx = 1
        has_audio = False
        
        if use_vbee and os.path.exists(temp_ai_audio_path):
            ffmpeg_cmd.extend(['-i', temp_ai_audio_path])
            audio_idx_ai = input_idx
            input_idx += 1
            has_audio = True
            
            if bgm_audio and os.path.exists(bgm_audio):
                ffmpeg_cmd.extend(['-i', bgm_audio])
                audio_idx_bgm = input_idx
                input_idx += 1
        else:
            # Giai Đoạn 1 hoặc Không dùng giọng AI
            if bgm_audio and os.path.exists(bgm_audio):
                ffmpeg_cmd.extend(['-i', bgm_audio])
                audio_idx_orig = input_idx # map BGM as the main fallback track Instead of original!
                input_idx += 1
                has_audio = True
            else:
                if os.path.exists(temp_original_audio):
                    ffmpeg_cmd.extend(['-i', temp_original_audio])
                    audio_idx_orig = input_idx
                    input_idx += 1
                    has_audio = True

        # Trimming (Anti-Reup Trim)
        if cfg.ENABLE_ANTI_REUP and cfg.REUP_TRIM:
            # Drop the first 0.5s by input seeking (faster) or output seeking
            ffmpeg_cmd.extend(['-ss', '0.5'])

        # --- VIDEO FILTERS ---
        v_filters = []
        
        if is_landscape:
            # Thuật toán Mờ Hậu Cảnh Siêu Tốc (Copy từ Threads Affiliate hoàn thiện):
            # Downscale hình nền xuống 540x960 rồi mới Blur để giải phóng 75% khối lượng công việc cho CPU/VGA, sau đó Zoom lại 1080x1920.
            v_filters.append("[0:v]scale=540:960,boxblur=10:10,scale=1080:1920[bg];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setdar=9/16,setsar=1[v_bokeh]")
            current_v = "[v_bokeh]"
        else:
            current_v = "0:v"
            
        # 2. Anti-Reup crop, color, speed
        reup_v_filters = []
        if cfg.ENABLE_ANTI_REUP:
            if cfg.REUP_CROP:
                reup_v_filters.append(f"crop=iw*0.98:ih*0.98")
            if cfg.REUP_COLOR:
                reup_v_filters.append(f"eq=saturation=1.05")
            if cfg.REUP_SPEED:
                reup_v_filters.append(f"setpts=PTS/1.01")
        
        if reup_v_filters:
            pad_v_in = current_v if current_v.startswith('[') else f"[{current_v}]"
            v_filters.append(f"{pad_v_in}{','.join(reup_v_filters)}[v_out]")
            current_v = "[v_out]"
            
        # --- AUDIO FILTERS ---
        a_filters = []
        current_a = None
        
        if has_audio:
            if audio_idx_ai != -1 and audio_idx_bgm != -1:
                # Áp dụng SideChain Compress (Auto-Ducking) mạnh mẽ + Giảm âm lượng nhạc nền xuống 30% để lọc sạch giọng gốc bị lọt
                # Tách AI Voice thành 2 (1 để kích hoạt Ducking, 1 để ghép đầu ra)
                a_filters.append(
                    f"[{audio_idx_bgm}:a]volume=0.30[bgm_scaled]; "
                    f"[{audio_idx_ai}:a]asplit[ai1][ai2]; "
                    f"[bgm_scaled][ai1]sidechaincompress=threshold=0.015:ratio=20:attack=5:release=200[bgm_ducked]; "
                    f"[bgm_ducked][ai2]amix=inputs=2:duration=first:dropout_transition=2[a_out]"
                )
                current_a = "[a_out]"
            elif audio_idx_ai != -1:
                # Chỉ có AI Voice (chuẩn nguyên bản)
                current_a = f"{audio_idx_ai}:a"
            else:
                # Chỉ dùng âm thanh gốc (hoặc nhạc nền bị bóp)
                current_a = f"{audio_idx_orig}:a"

            # Anti-reup audio speed filter if tracking video speed
            if cfg.ENABLE_ANTI_REUP and cfg.REUP_SPEED:
                pad_a_in = current_a if current_a.startswith('[') else f"[{current_a}]"
                a_filters.append(f"{pad_a_in}atempo=1.01[a_speed]")
                current_a = "[a_speed]"
        
        # Build Filter Complex String
        filter_complex = "; ".join(v_filters + a_filters)
        
        if filter_complex:
            ffmpeg_cmd.extend(['-filter_complex', filter_complex])
            ffmpeg_cmd.extend(['-map', current_v])
            if has_audio and current_a:
                ffmpeg_cmd.extend(['-map', current_a])
        else:
            ffmpeg_cmd.extend(['-map', '0:v'])
            if has_audio and current_a:
                ffmpeg_cmd.extend(['-map', current_a])

        # --- HW ACCEL ENCODING ---
        codec = "libx264"
        preset = "ultrafast"
        hw_params = []
        
        if use_hw_accel:
            system_os = platform.system()
            if system_os == "Darwin":
                if cfg.ENABLE_ANTI_REUP and getattr(cfg, "REUP_METADATA", True):
                    print("⚡ [M1 HEVC Optimization] Đang sử dụng hevc_videotoolbox để giả lập camera iPhone HDR!")
                    codec = "hevc_videotoolbox"
                    hw_params = [
                        '-b:v', '10000k',
                        '-color_primaries', 'bt2020',
                        '-color_trc', 'arib-std-b67',
                        '-colorspace', 'bt2020nc',
                        '-movflags', 'write_colr',
                        '-tag:v', 'hvc1'
                    ]
                else:
                    print("⚡ [M1 Pro Optimization] Đã mở khóa H264_VideoToolbox Apple Silicon!")
                    codec = "h264_videotoolbox"
                    hw_params = ['-b:v', '6000k', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
            elif system_os == "Windows":
                codec = "h264_amf"
                
        ffmpeg_cmd.extend(['-c:v', codec])
        if hw_params:
            ffmpeg_cmd.extend(hw_params)
        elif codec == "libx264":
            ffmpeg_cmd.extend(['-preset', preset])
            
        if has_audio:
            ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '192k'])

        # Metadata Scrubbing & CapCut-like Spoofing
        if cfg.ENABLE_ANTI_REUP and getattr(cfg, "REUP_METADATA", True):
            print("🛡️ Đang giả lập Metadata chuẩn CapCut (Mac) để vượt qua bộ lọc TikTok...")
            ffmpeg_cmd.extend([
                "-map_metadata", "-1",
                "-f", "mov",
                "-fflags", "+bitexact",
                "-flags:v", "+bitexact",
                "-flags:a", "+bitexact",
                "-metadata:g", "major_brand=qt  ",
                "-metadata:g", "minor_version=512",
                "-metadata:g", "compatible_brands=qt  ",
                "-metadata:g", "com.apple.quicktime.full-frame-rate-playback-intent=1",
                "-metadata:g", "com.apple.quicktime.make=Apple",
                "-metadata:g", "com.apple.quicktime.model=iPhone 17 Pro Max",
                "-metadata:g", "com.apple.quicktime.software=19.5",
                "-metadata:g", "software=26.0.1",
                "-metadata:g", "location=21.0148+105.5256/",
                "-metadata:s:v:0", "handler_name=Core Media Video",
                "-metadata:s:v:0", "vendor_id=[0][0][0][0]",
                "-metadata:s:v:0", f"encoder={'HEVC' if codec == 'hevc_videotoolbox' else 'H.264'}",
                "-metadata:s:a:0", "handler_name=Core Media Audio",
                "-metadata:s:a:0", "vendor_id=[0][0][0][0]",
                "-metadata:s:a:0", "encoder=",
                "-metadata", f"creation_time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            ])
            
        if is_landscape:
            ffmpeg_cmd.extend(['-aspect', '9:16'])

        # Thay thế -shortest bằng thời lượng chính xác của video đầu ra để tránh bị cắt ngắn khi giọng đọc ngắn hơn video
        target_duration = video_duration
        if cfg.ENABLE_ANTI_REUP:
            if cfg.REUP_TRIM:
                target_duration = max(0.1, target_duration - 0.5)
            if cfg.REUP_SPEED:
                target_duration = target_duration / 1.01
        ffmpeg_cmd.extend(['-t', f'{target_duration:.3f}'])
        ffmpeg_cmd.append(output_video_path)
        
        print(f"DEBUG COMMAND: {' '.join(ffmpeg_cmd)}")
        
        # Execute natively
        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise Exception(f"FFmpeg ghép Video/Audio thất bại: {process.stderr[-300:]}")
        print("✅ Ghép luồng A/V siêu tốc bằng FFmpeg thành công!")

            
        # ==========================================
        # 6. AUTO WATERMARK PASS (POST-PROCESSING)
        # ==========================================
        is_watermark_enabled = enable_watermark if enable_watermark is not None else getattr(cfg, "ENABLE_WATERMARK", False)
        if is_watermark_enabled:
            if progress_callback: progress_callback(95)
            print("💧 Áp dụng Watermark...")
            
            # Temporary file for watermarking
            temp_wm_path = output_video_path.replace(".mp4", "_wm_temp.mp4")
            
            # Khởi tạo giá trị config watermark
            text = getattr(cfg, "WATERMARK_TEXT", "")
            font_size = getattr(cfg, "WATERMARK_SIZE", 40)
            opacity = getattr(cfg, "WATERMARK_OPACITY", 0.5)
            position = getattr(cfg, "WATERMARK_POSITION", "Góc phải - dưới")
            
            if position == "Giữa màn hình": pos_xy = "x=(w-text_w)/2:y=(h-text_h)/2"
            elif position == "Góc trái - trên": pos_xy = "x=20:y=20"
            elif position == "Góc phải - trên": pos_xy = "x=w-text_w-20:y=20"
            elif position == "Góc trái - dưới": pos_xy = "x=20:y=h-text_h-20"
            else: pos_xy = "x=w-text_w-20:y=h-text_h-20"
            
            # Tìm font chữ trên máy
            font_path = ""
            system_os = platform.system()
            if system_os == "Windows":
                font_path = "C\\:/Windows/Fonts/arial.ttf"
            elif system_os == "Darwin":
                mac_fonts = [
                    "/Library/Fonts/Arial.ttf",
                    "/System/Library/Fonts/Supplemental/Arial.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/Library/Fonts/Times New Roman.ttf"
                ]
                for f in mac_fonts:
                    if os.path.exists(f):
                        font_path = f
                        break
            else:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                
            print(f"DEBUG WATERMARK - Font Path: {font_path}, Text: {text}")
            if font_path and text:
                safe_text = text.replace("'", "").replace(":", "")
                drawtext_filter = f"drawtext=fontfile='{font_path}':text='{safe_text}':fontsize={font_size}:fontcolor=white@{opacity}:{pos_xy}"
                
                # Render parameters matching MoviePy HW accel
                wm_codec = "libx264"
                wm_params = []
                if use_hw_accel:
                    if system_os == "Darwin":
                        wm_codec = "h264_videotoolbox"
                        wm_params = ['-b:v', '5000k']
                    elif system_os == "Windows":
                        wm_codec = "h264_amf"
                
                command = [
                    'ffmpeg', '-y',
                    '-i', output_video_path,
                    '-vf', drawtext_filter,
                    '-c:v', wm_codec,
                    '-codec:a', 'copy'  # Giữ nguyên âm thanh đã mix
                ]
                if cfg.ENABLE_ANTI_REUP and getattr(cfg, "REUP_METADATA", True):
                    command.extend([
                        "-map_metadata", "-1",
                        "-f", "mov",
                        "-fflags", "+bitexact",
                        "-flags:v", "+bitexact",
                        "-flags:a", "+bitexact",
                        "-metadata:g", "major_brand=qt  ",
                        "-metadata:g", "minor_version=0",
                        "-metadata:g", "compatible_brands=qt  ",
                        "-metadata:g", "com.apple.quicktime.full-frame-rate-playback-intent=1",
                        "-metadata:s:v:0", "handler_name=Core Media Video",
                        "-metadata:s:v:0", "vendor_id=[0][0][0][0]",
                        "-metadata:s:v:0", "encoder=H.264",
                        "-metadata:s:a:0", "handler_name=Core Media Audio",
                        "-metadata:s:a:0", "vendor_id=[0][0][0][0]",
                        "-metadata:s:a:0", "encoder=",
                        "-metadata", f"creation_time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
                    ])
                command.extend(wm_params + [temp_wm_path])
                
                kwargs = {'capture_output': True, 'text': True}
                if system_os == "Windows":
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    
                process = subprocess.run(command, **kwargs)
                
                if process.returncode == 0 and os.path.exists(temp_wm_path):
                    shutil.move(temp_wm_path, output_video_path)
                    print("✅ Đóng dấu thành công!")
                else:
                    print(f"⚠️ Lỗi Watermark: {process.stderr[-200:] if process.stderr else 'Undefined error'}")

            
    except Exception as e:
        print(f"❌ Lỗi khi render final Video: {e}")
        if use_hw_accel:
            process_video_pipeline(
                input_video_path, progress_callback, use_hw_accel=False,
                add_sub=add_sub, add_voice=add_voice, sub_source=sub_source,
                keep_bgm=keep_bgm, processing_mode=processing_mode,
                phase2_audio_dir=phase2_audio_dir, file_index=file_index,
                phase1_export_dir=phase1_export_dir, enable_blur=enable_blur
            )

    # ==========================================
    # 6.5. TRÍCH XUẤT THUMBNAIL GỐC
    # ==========================================
    if cfg.ENABLE_ANTI_REUP and getattr(cfg, "REUP_THUMBNAIL", False):
        try:
            print("🖼️ Đang trích xuất Ảnh Bìa (Thumbnail) Gốc...")
            # Tạo file ảnh jpg dùng chung thư mục Output
            base_fname = os.path.splitext(filename)[0]
            thumbnail_out = os.path.join(cfg.OUTPUT_DIR, f"{base_fname}.jpg")
            
            # Cắt đúng 1 khung hình ở giây đầu tiên (tránh màn hình đen 0s)
            thumb_cmd = [
                'ffmpeg', '-y', '-ss', '00:00:01', '-i', input_video_path, 
                '-vframes', '1', '-q:v', '2', thumbnail_out
            ]
            
            # Ẩn popup cmd trên Windows
            kwargs = {'capture_output': True}
            if platform.system() == "Windows":
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            subprocess.run(thumb_cmd, **kwargs)
            if os.path.exists(thumbnail_out):
                print(f"✅ Đã cắt Ảnh bìa (Thumbnail) thành công!")
        except Exception as e:
            print(f"⚠️ Trục trặc cắt Thumbnail: {e}")

    # 7. DỌN DẸP
    if progress_callback: progress_callback(100)
    
    if is_phase_1:
        print(f"📦 [GIAI ĐOẠN 1] Trút file thô cho Video thứ [{file_index}]...")
        p1_dir = phase1_export_dir if phase1_export_dir else os.path.join(cfg.OUTPUT_DIR, "GIAI_DOAN_1_XUAT_THO")
        os.makedirs(p1_dir, exist_ok=True)
        
        base_name = os.path.splitext(filename)[0]
        # Đuôi file SRT có Index (Không chứa dấu ngoặc vuông và đuôi .mp4 để tương thích Vbee)
        srt_export = os.path.join(p1_dir, f"{file_index:02d}_Sub_{base_name}.srt")
        has_voice = False
        if os.path.exists(temp_translated_srt) and os.path.getsize(temp_translated_srt) > 10:
            shutil.copy(temp_translated_srt, srt_export)
            has_voice = True
        else:
            print(f"⚠️ Video không lời thoại (Hoặc quá ngắn). Cắt rác rỗng, triệt tiêu Subtitle cho Video [{file_index:02d}].")
            
        if has_voice:
            # Move original muted video
            vid_pdir = os.path.join(p1_dir, "Video_Cam_Tam_Thoi")
            os.makedirs(vid_pdir, exist_ok=True)
            vid_export = os.path.join(vid_pdir, f"{file_index:02d}_Video_Mute_{base_name}.mp4")
            if os.path.exists(output_video_path):
                shutil.move(output_video_path, vid_export)
            print(f"✅ Đã xuất File chờ Lồng Tiếng Thủ Công: {srt_export}")
        else:
            print(f"⏩ Fast-track: Video rỗng thoại. Bẻ lái vọt thẳng qua Khâu 2 để Cất Cánh ngay!")
            # Chạy ngay Khâu 2 cho file này để nhả thẳng ra HOAN_THIEN_ luôn vì chả cần chờ Vbee
            from .sync_and_sub_p2 import process_phase_2
            process_phase_2(input_video_path, "", file_index, progress_callback, use_hw_accel, keep_bgm, phase1_export_dir=p1_dir, is_fast_track=True)
            if os.path.exists(output_video_path):
                try: os.remove(output_video_path)
                except: pass

    cleanup_temp_files()
    print(f"🎉 HOÀN TẤT Hn.dz tool: {filename} -> {output_name}")