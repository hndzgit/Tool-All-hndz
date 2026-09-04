import os
import random
import string
import subprocess
import json
from automation.config import config as cfg

def get_video_duration(video_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0

def generate_random_id(length=5):
    letters_and_digits = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(length))

def run_threads_pipeline(input_video_path, progress_callback=None):
    filename = os.path.basename(input_video_path)
    print(f"🎬 [THREADS] Bắt đầu xử lý: {filename}")
    
    # 1. Sinh ID dùng chung
    shared_id = f"THZ_{generate_random_id()}"
    output_video = os.path.join(cfg.OUTPUT_DIR, f"{shared_id}.mp4")
    output_image = os.path.join(cfg.OUTPUT_DIR, f"{shared_id}.jpg")
    
    duration = get_video_duration(input_video_path)
    if duration <= 0:
        raise Exception("Không thể lấy độ dài video!")

    if progress_callback: progress_callback(10)

    # 2. Xây dựng bộ lọc Video/Audio FFmpeg dựa trên config cũ của Automation
    vf_filters = []
    af_filters = []

    # CHỐNG REUP VIDEO
    if cfg.ENABLE_ANTI_REUP:
        if getattr(cfg, "REUP_MIRROR", True):
            pass # [ĐÃ TẮT] Không lật ngược màn hình để tránh ngược Text/Sub
        if getattr(cfg, "REUP_CROP", True):
            vf_filters.append("crop=iw*0.98:ih*0.98")
        if getattr(cfg, "REUP_COLOR", True):
            vf_filters.append("eq=brightness=0.03:contrast=1.05:saturation=1.05")
        if getattr(cfg, "REUP_SPEED", True):
            vf_filters.append("setpts=0.98*PTS")
            af_filters.append("atempo=1.02")

        # CHỐNG REUP AUDIO
        if getattr(cfg, "REUP_AUDIO_PITCH", True):
            af_filters.append("asetrate=44100*1.04,aresample=44100,aphaser=type=t:speed=2:decay=0.4,tremolo=f=4.0:d=0.2")
        if getattr(cfg, "REUP_AUDIO_EQ", True):
            af_filters.append("bass=g=10:f=110:w=0.6,equalizer=f=1000:width_type=h:width=200:g=-5,treble=g=5:f=8000:w=0.5")

    # WATERMARK
    if getattr(cfg, "ENABLE_WATERMARK", False) and getattr(cfg, "WATERMARK_TEXT", ""):
        font_file = cfg.FONT_PATH
        if os.path.exists(font_file):
            text = getattr(cfg, 'WATERMARK_TEXT', 'Video AI Pro')
            size = getattr(cfg, 'WATERMARK_SIZE', 40)
            opacity = getattr(cfg, 'WATERMARK_OPACITY', 0.6)
            pos = getattr(cfg, 'WATERMARK_POSITION', 'Góc phải - dưới')
            
            # Map position to ffmpeg expression
            x, y = "(w-tw-20)", "(h-th-20)"
            if pos == "Giữa màn hình": x, y = "(w-tw)/2", "(h-th)/2"
            elif pos == "Góc trái - trên": x, y = "20", "20"
            elif pos == "Góc phải - trên": x, y = "(w-tw-20)", "20"
            elif pos == "Góc trái - dưới": x, y = "20", "(h-th-20)"
            
            color = f"white@{opacity}"
            # Protect special chars
            text = text.replace(":", "\\:").replace("'", "\\'")
            vf_filters.append(f"drawtext=fontfile='{font_file}':text='{text}':fontsize={size}:fontcolor={color}:x={x}:y={y}:shadowcolor=black@0.5:shadowx=2:shadowy=2")

    # BOKEH DỌC BẮT BUỘC (16:9 to 9:16) DÀNH CHO THREADS
    ffmpeg_cmd = ['ffmpeg', '-y', '-i', input_video_path]
    
    # Tối ưu siêu tốc độ M-Series: Downscale nền trước khi làm mờ (giảm 75% khối lượng công việc cho CPU) rồi scale ngược lại
    scale_filter = "[0:v]scale=540:960,boxblur=10:10,scale=1080:1920[bg];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
    if vf_filters:
        scale_filter += f";[base]{','.join(vf_filters)}[v]"
        filter_complex = scale_filter
        ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[v]', '-map', '0:a?'])
    else:
        filter_complex = scale_filter
        ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[base]', '-map', '0:a?'])


    # Kích âm lượng to lên 1.8 lần (chống rè, vừa đủ nghe cho Mobile)
    af_filters.append("volume=1.8")

    if af_filters:
        ffmpeg_cmd.extend(['-af', ','.join(af_filters)])

    # Video Encoding settings (Sử dụng lõi Đồ Họa phần cứng của Macbook để xuất băng thông siêu tốc độ)
    ffmpeg_cmd.extend([
        '-c:v', 'h264_videotoolbox', '-b:v', '4000k',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        output_video
    ])

    if progress_callback: progress_callback(40)
    print("⏳ Đang render Video Affiliate (Anti-Reup FFmpeg)...")
    try:
        subprocess.run(ffmpeg_cmd, check=True, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Lỗi Render Video: {e.stderr}")
        raise Exception(f"Lỗi FFmpeg: {e.stderr[-100:]}")

    if progress_callback: progress_callback(85)
    
    # 3. Trích xuất Ảnh ngẫu nhiên
    print("📸 Đang trích xuất Ảnh Bìa ngẫu nhiên...")
    random_time = random.uniform(duration * 0.1, duration * 0.9)
    img_cmd = [
        'ffmpeg', '-y', '-ss', str(random_time), '-i', output_video, 
        '-vframes', '1', '-q:v', '2', output_image
    ]
    subprocess.run(img_cmd, check=True)

    if progress_callback: progress_callback(100)
    print(f"🎉 Hoàn thành Affiliate!\nVideo: {output_video}\nẢnh: {output_image}")
    return output_video, output_image