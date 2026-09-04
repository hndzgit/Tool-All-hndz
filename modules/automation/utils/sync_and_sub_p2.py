import os
import glob
import subprocess
import shutil
import platform
import config.config as cfg
import utils.thumbnail_maker as thmb

def has_audio_stream(video_path):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', video_path]
    try:
        out = subprocess.check_output(cmd, text=True).strip()
        return len(out) > 0
    except:
        return False

def process_phase_2(input_video_path, phase2_audio_dir, file_index, progress_callback=None, use_hw_accel=False, keep_bgm=True, phase1_export_dir="", is_fast_track=False):
    filename = os.path.basename(input_video_path)
    base_name = os.path.splitext(filename)[0]
    
    # Đọc lại file Video Câm đã được Render từ Giai Đoạn 1
    p1_dir = phase1_export_dir if phase1_export_dir else os.path.join(cfg.OUTPUT_DIR, "GIAI_DOAN_1_XUAT_THO")
    vid_pdir = os.path.join(p1_dir, "Video_Cam_Tam_Thoi")
    muted_video_path = os.path.join(vid_pdir, f"{file_index:02d}_Video_Mute_{base_name}.mp4")
    
    from .sync_and_sub import generate_natural_filename
    output_name, output_video_path = generate_natural_filename(cfg.OUTPUT_DIR)
    
    # ── SKIP LOGIC FOR FAST-TRACKED MUTED VIDEOS ──
    if not is_fast_track and not os.path.exists(muted_video_path) and os.path.exists(output_video_path):
        print(f"⏩ Video [{file_index:02d}] đã được Hoàn Thiện Tự Động từ Màn 1 (Do Câm Thoại). Dẹp Màn 2!")
        if progress_callback: progress_callback(100)
        return
    
    if not os.path.exists(muted_video_path):
        if is_fast_track:
            muted_video_path = os.path.join(cfg.OUTPUT_DIR, f"vietsub_{filename}")
        else:
            muted_video_path = input_video_path # Fallback to original if something goes wrong
        print(f"⚠️ Trích xuất Video Câm gốc. Thư mục hiện tại: {muted_video_path}")
        
    print(f"🎬 [GIAI ĐOẠN 2] Đang xử lý Video: {filename} (Index: {file_index})")
    
    import cv2
    cap = cv2.VideoCapture(input_video_path)
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    is_landscape = getattr(cfg, "CONVERT_TO_VERTICAL", False) and abs(orig_w / orig_h - 9/16) > 0.05

    if progress_callback: progress_callback(10)
    
    import re
    # 1. Tìm File Audio Vbee
    target_mp3 = None
    if not is_fast_track:
        if not os.path.isdir(phase2_audio_dir):
            print(f"❌ Lỗi: Thư mục chứa MP3 Giai Đoạn 2 không hợp lệ ({phase2_audio_dir})")
            return
            
        mp3_files = sorted(glob.glob(os.path.join(phase2_audio_dir, "*.mp3")))
        if not mp3_files:
            print(f"❌ Lỗi: Không tìm thấy bất kỳ file .mp3 nào trong {phase2_audio_dir}")
            return
            
        # Lấy danh sách MP3: Ưu tiên bắt Khớp số ở Đầu Tên File (Vbee format: "01sub...", v.v)
        for mp3 in mp3_files:
            base_mp3 = os.path.basename(mp3)
            # Bắt số đầu tiên: [01], 01_, 01sub, ...
            match = re.match(r'^\[?0*(\d+)', base_mp3)
            if match and int(match.group(1)) == file_index:
                target_mp3 = mp3
                break
                
        if not target_mp3:
            print(f"⚠️ Cảnh báo: Không có Audio MP3 Vbee số [{file_index:02d}]! Giả định Video này không có lời thoại. Bỏ qua móc nối Mạng Voice AI.")
                
        if target_mp3:
            print(f"🎯 Đã bắt cặp Audio MP3: {os.path.basename(target_mp3)}")
    if progress_callback: progress_callback(30)
    
    # 2. Chuẩn bị đầu ra
    if progress_callback: progress_callback(60)
    
    ffmpeg_cmd = ['ffmpeg', '-y']
    ffmpeg_cmd.extend(['-i', muted_video_path]) # input 0: Video (with BGM [0:a] merged from Phase 1)
    if target_mp3:
        ffmpeg_cmd.extend(['-i', target_mp3])       # input 1: AI Audio [1:a]
        
    temp_thumb_path = ""
    if getattr(cfg, "ENABLE_THUMBNAIL", True):
        # 1. Tìm File text chứa Title
        title_txts = glob.glob(os.path.join(cfg.OUTPUT_DIR, f"*{base_name}.srt.title.txt")) + \
                     glob.glob(os.path.join(cfg.RESCUE_SRT_DIR, f"*{base_name}.srt.title.txt"))
        thumb_text = "SIÊU PHẨM MỚI"
        if title_txts:
            try:
                with open(title_txts[0], "r", encoding="utf-8") as ft:
                    thumb_text = ft.read().strip()
            except: pass
        if not thumb_text: thumb_text = "SIÊU PHẨM MỚI"
        
        # 2. Sinh Ảnh Bìa Tạm
        temp_thumb_path = os.path.join(cfg.TEMP_DIR, f"thumb_{base_name}.jpg")
        print(f"🎨 Đang chế tác Ảnh Bìa Clickbait: '{thumb_text}'...")
        if thmb.create_thumbnail(input_video_path, thumb_text, temp_thumb_path):
            ffmpeg_cmd.extend(['-loop', '1', '-t', '0.2', '-i', temp_thumb_path])  # Input 2 (or 1)
            thumb_idx = 2 if target_mp3 else 1
        else:
            temp_thumb_path = ""
    
    # Trimming (Anti-Reup Trim)
    if getattr(cfg, "ENABLE_ANTI_REUP", False) and getattr(cfg, "REUP_TRIM", False):
        ffmpeg_cmd.extend(['-ss', '0.5'])
        
    v_filters = []
    a_filters = []
    
    current_v = "[0:v]"
    
    has_audio = has_audio_stream(muted_video_path)
    current_a = "[1:a]" if target_mp3 else ("[0:a]" if has_audio else None)
    
    # Anti-Reup video filters
    if getattr(cfg, "ENABLE_ANTI_REUP", False):
        reup_v_filters = []
        if getattr(cfg, "REUP_CROP", False):
            reup_v_filters.append(f"crop=iw*0.98:ih*0.98")
        if getattr(cfg, "REUP_COLOR", False):
            reup_v_filters.append(f"eq=saturation=1.05")
        if getattr(cfg, "REUP_SPEED", False):
            reup_v_filters.append(f"setpts=PTS/1.01")
            
        if reup_v_filters:
            v_filters.append(f"{current_v}{','.join(reup_v_filters)}[v_reup]")
            current_v = "[v_reup]"
            
    # Dán Ảnh Bìa (Overlay Thumbnail)
    if temp_thumb_path:
        v_filters.append(f"{current_v}[{thumb_idx}:v]overlay=enable='between(t,0,0.2)'[v_out]")
        current_v = "[v_out]"
            
    # Audio ducking (BGM on [0:a], AI on [1:a])
    if keep_bgm and target_mp3 and has_audio:
        a_filters.append("[1:a]asplit[ai1][ai2]; [0:a][ai1]sidechaincompress=threshold=0.08:ratio=4:attack=5:release=50[bgm_ducked]; [bgm_ducked][ai2]amix=inputs=2:duration=first:dropout_transition=2[a_out]")
        current_a = "[a_out]"
        
    if current_a and getattr(cfg, "ENABLE_ANTI_REUP", False) and getattr(cfg, "REUP_SPEED", False):
        a_filters.append(f"{current_a}atempo=1.01[a_speed]")
        current_a = "[a_speed]"
        
    filter_complex = "; ".join(v_filters + a_filters) if (v_filters or a_filters) else ""
    
    def map_str(s):
        if s and s.startswith('[') and ':' in s:
            return s.replace('[', '').replace(']', '')
        return s
        
    if filter_complex:
        ffmpeg_cmd.extend(['-filter_complex', filter_complex])
        ffmpeg_cmd.extend(['-map', map_str(current_v)])
        if current_a:
            ffmpeg_cmd.extend(['-map', map_str(current_a)])
    else:
        ffmpeg_cmd.extend(['-map', '0:v'])
        if current_a:
            ffmpeg_cmd.extend(['-map', current_a.replace('[', '').replace(']', '')])
        
    # Encoding
    codec = "libx264"
    hw_params = []
    if use_hw_accel:
        system_os = platform.system()
        if system_os == "Darwin":
            if getattr(cfg, "ENABLE_ANTI_REUP", False) and getattr(cfg, "REUP_METADATA", True):
                print("⚡ [M1 HEVC Giai Đoạn 2] Đang sử dụng hevc_videotoolbox để giả lập camera iPhone HDR!")
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
                codec = "h264_videotoolbox"
                hw_params = ['-b:v', '6000k', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
        elif system_os == "Windows":
            codec = "h264_amf"
            
    ffmpeg_cmd.extend(['-c:v', codec])
    if hw_params:
        ffmpeg_cmd.extend(hw_params)
    elif codec == "libx264":
        ffmpeg_cmd.extend(['-preset', 'ultrafast'])
    if current_a:
        ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    
    meta_params = []
    if getattr(cfg, "ENABLE_ANTI_REUP", False) and getattr(cfg, "REUP_METADATA", True):
        import time
        print("🛡️ [Giai Đoạn 2] Đang giả lập Metadata chuẩn CapCut (Mac) để vượt qua bộ lọc TikTok...")
        meta_params = [
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
        ]
        ffmpeg_cmd.extend(meta_params)
        
    if is_landscape:
        ffmpeg_cmd.extend(['-aspect', '9:16'])
        
    ffmpeg_cmd.extend(['-shortest'])
    ffmpeg_cmd.append(output_video_path)
    
    print(f"DEBUG PHASE 2 CMD: {' '.join(ffmpeg_cmd)}")
    if progress_callback: progress_callback(80)
    
    process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if process.returncode != 0:
        print(f"❌ Lỗi FFmpeg Auto-Ducking Phase 2: {process.stderr[-300:]}")
        print("⚠️ Chuyển sang phương án Ép tiếng thô (Không tách trộn BGM)...")
        aspect_params = ['-aspect', '9:16'] if is_landscape else []
        if target_mp3:
            ffmpeg_fallback = ['ffmpeg', '-y', '-i', muted_video_path, '-i', target_mp3, '-c:v', codec] + hw_params + ['-c:a', 'aac', '-map', '0:v', '-map', '1:a'] + aspect_params
        else:
            ffmpeg_fallback = ['ffmpeg', '-y', '-i', muted_video_path, '-c:v', codec] + hw_params + ['-c:a', 'aac', '-map', '0:v', '-map', '0:a'] + aspect_params
        ffmpeg_fallback += meta_params + ['-shortest', output_video_path]
        subprocess.run(ffmpeg_fallback, capture_output=True)
        
    if progress_callback: progress_callback(100)
    print(f"🎉 GIAI ĐOẠN 2 HOÀN TẤT: {filename} -> {output_name}")
    
    # Dọn dẹp rác Ảnh bìa tạm
    if temp_thumb_path and os.path.exists(temp_thumb_path):
        try: os.remove(temp_thumb_path)
        except: pass