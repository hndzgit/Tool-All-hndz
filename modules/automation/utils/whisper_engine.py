from faster_whisper import WhisperModel
import subprocess
import os

def extract_audio(video_path, audio_path):
    """Trích xuất Audio mp3 128k từ Video đầu vào để nhẹ hơn chp Whisper"""
    print(f"🎵 Đang trích xuất âm thanh từ video: {os.path.basename(video_path)}...")
    cmd = [
        "ffmpeg", "-y", "-i", video_path, 
        "-vn", "-acodec", "libmp3lame", "-ab", "128k", 
        "-threads", "10", 
        audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return audio_path

def format_timestamp(seconds: float, always_include_hours: bool = False):
    """Format thời gian giây -> HH:MM:SS,mmm cho chuẩn định dạng SRT"""
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)
    
    hours = milliseconds // 3600000
    milliseconds -= hours * 3600000
    
    minutes = milliseconds // 60000
    milliseconds -= minutes * 60000
    
    seconds = milliseconds // 1000
    milliseconds -= seconds * 1000
    
    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else "00:"
    return f"{hours_marker}{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def transcribe_to_srt(audio_path, srt_output_path, model_size="small", language=None, initial_prompt=None):
    """
    Sử dụng Faster-Whisper để nhận diện âm thanh và ghi ra file SRT.
    Model khuyên dùng: 'small' hoặc 'medium' (nếu máy khỏe và cần độ chính xác cao).
    """
    print(f"👂 Khởi động Whisper AI ({model_size} model)...")
    
    # [Apple Silicon HW Accel]: Trên Mac M1, int8 chạy giả lập phần mềm rất chậm. float32 sẽ kích hoạt được Apple Accelerate Framework (AMX) phần cứng!
    import platform
    threads = 4 if platform.system() == "Darwin" else 4 # Apple CPU performance optimized thread count
    compute = "float32" if platform.system() == "Darwin" else "int8"
    model = WhisperModel(model_size, device="cpu", compute_type=compute, cpu_threads=threads)

    print(f"📝 Đang phiên dịch âm thanh: {os.path.basename(audio_path)}...")
    
    import config.config as cfg
    src_lang = getattr(cfg, "SOURCE_LANGUAGE", "Tự Động (AI)")
    lang_code = language
    if not lang_code:
        if "Trung" in src_lang:
            lang_code = "zh"
        elif "Anh" in src_lang:
            lang_code = "en"
        elif "Việt" in src_lang:
            lang_code = "vi"
        
    prompt = initial_prompt if initial_prompt else "Video review công nghệ, livestream bán hàng đồ gia dụng, mỹ phẩm. Các tên hãng, thương hiệu và model như Attack Shark X68 HE, iPhone 15 Pro Max, MacBook, Logitech, Sony, v.v."
    
    segments, info = model.transcribe(
        audio_path, 
        language=lang_code,
        beam_size=3, # Giảm từ 5 xuống 3 giúp tăng tốc độ xử lý CPU lên 40%
        initial_prompt=prompt,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=250), # Tăng lên 250ms tránh cắt từ cụt ngủn giữa chừng
        condition_on_previous_text=False, # Tắt ghi nhớ câu trước để triệt tiêu lỗi lặp chữ / sinh ảo giác do nhạc nền
        no_speech_threshold=0.6,          # Tăng ngưỡng lọc nhiễu nhạc nền (BGM) tránh nhận diện nhầm nhạc thành chữ
        word_timestamps=True
    )
    
    count = 0
    with open(srt_output_path, "w", encoding="utf-8") as f:
        for segment in segments:
            current_words = []
            segment_words_list = list(segment.words)
            if not segment_words_list:
                continue
                
            current_start = segment_words_list[0].start
            
            for index, word_obj in enumerate(segment_words_list):
                current_words.append(word_obj.word)
                
                # KHẮC PHỤC TRIỆT ĐỂ LỖI 1 CỤC TEXT (WALL OF TEXT): 
                # Ép rách block nếu độ dài câu > 2.8 giây HOẶC chứa > 12 ký tự/từ HOẶC là từ cuối cùng
                is_last_word = (index == len(segment_words_list) - 1)
                is_too_long_time = (word_obj.end - current_start) > 2.8
                is_too_long_text = len(current_words) > 12
                
                if is_last_word or is_too_long_time or is_too_long_text:
                    count += 1
                    start_str = format_timestamp(current_start, always_include_hours=True)
                    end_str = format_timestamp(word_obj.end, always_include_hours=True)
                    
                    # Nối chuỗi gọn gàng (Faster Whisper tạo space tự động cho English, với Trung thì "".join là chuẩn)
                    joined_text = "".join(current_words).replace("  ", " ").strip()
                    
                    f.write(f"{count}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{joined_text}\n\n")
                    
                    # Reset để hứng mẻ chữ tiếp theo
                    current_words = []
                    if not is_last_word:
                        current_start = segment_words_list[index + 1].start

    print(f"✅ Đã tạo phụ đề (SRT) tại: {srt_output_path}")
    return srt_output_path
