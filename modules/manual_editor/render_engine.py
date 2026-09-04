import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import subprocess
import time
import config.config as cfg

# Prepend macOS Homebrew / common paths to PATH to ensure ffmpeg and ffprobe are found
extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
current_path = os.environ.get("PATH", "")
new_paths = []
for path in extra_paths:
    if path not in current_path:
        new_paths.append(path)
if new_paths:
    os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + current_path

def has_audio_track(file_path):
    """Kiểm tra xem tệp video đầu vào có chứa luồng âm thanh nào không"""
    try:
        cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "a", 
            "-show_entries", "stream=codec_type", 
            "-of", "csv=p=0", 
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return "audio" in res.stdout
    except Exception as e:
        print(f"ffprobe check failed: {e}")
        return True # Giả định mặc định là có

def render_manual_video(input_path, blur_boxes, texts, width, height, custom_output_dir=None,
                        speed=1.0, strip_metadata=False, split_video=False,
                        font_size=30, text_color=(255, 255, 0)):
    """
    Xử lý video từng frame bằng OpenCV để làm mờ và chèn chữ,
    sau đó ghép âm thanh, tăng tốc, xóa metadata, cắt đôi nếu có bằng FFmpeg.
    """
    if custom_output_dir:
        output_dir = custom_output_dir
    else:
        output_dir = getattr(cfg, "OUTPUT_DIR", "outputs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = os.path.basename(input_path)
    temp_video = os.path.join(output_dir, f"temp_manual_{filename}")
    final_output = os.path.join(output_dir, f"MANUAL_EDIT_{filename}")
    
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))
    
    # Chuẩn bị Font chữ cho tiếng Việt
    try:
        font_path = getattr(cfg, "FONT_PATH", "/System/Library/Fonts/Helvetica.ttc")
        font = ImageFont.truetype(font_path, int(font_size))
    except:
        font = ImageFont.load_default()
        
    print(f"🎬 Bắt đầu Render thủ công: {filename}")
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        frame_count += 1
        
        # 1. XỬ LÝ LÀM MỜ (BLUR)
        for (x1, y1, x2, y2) in blur_boxes:
            # Đảm bảo tọa độ không vượt quá kích thước frame
            bx1, by1 = max(0, x1), max(0, y1)
            bx2, by2 = min(width, x2), min(height, y2)
            
            if bx2 > bx1 and by2 > by1:
                roi = frame[by1:by2, bx1:bx2]
                blurred_roi = cv2.GaussianBlur(roi, (99, 99), 30)
                frame[by1:by2, bx1:bx2] = blurred_roi
                
        # 2. XỬ LÝ CHÈN CHỮ (TEXT) BẰNG PIL (Hỗ trợ Tiếng Việt) - TỐI ƯU HÓA TỐC ĐỘ 10X
        if texts:
            current_time_sec = frame_count / fps if fps else 0
            # Lọc các chữ cần vẽ trong frame này trước để tránh convert ảnh dư thừa
            active_texts = [
                txt_info for txt_info in texts 
                if txt_info.get("start", 0) <= current_time_sec <= txt_info.get("end", 999999)
            ]
            
            if active_texts:
                # Direct conversion to PIL image (zero-copy BGR representation)
                pil_img = Image.fromarray(frame)
                draw = ImageDraw.Draw(pil_img)
                
                # Hoán đổi R-B cho màu chữ do frame gốc ở dạng BGR
                r, g, b = text_color
                swapped_text_color = (b, g, r)
                
                for txt_info in active_texts:
                    txt = txt_info["text"]
                    tx, ty = txt_info["x"], txt_info["y"]
                    
                    # Vẽ viền đen (Outline)
                    outline_color = (0, 0, 0)
                    thickness = 3
                    for adj_x in range(-thickness, thickness + 1):
                        for adj_y in range(-thickness, thickness + 1):
                            draw.text((tx + adj_x, ty + adj_y), txt, font=font, fill=outline_color)
                    
                    # Vẽ chữ màu tùy chọn (Fill) với màu đã hoán đổi R-B
                    draw.text((tx, ty), txt, font=font, fill=swapped_text_color)
                    
                # Convert back directly without conversion copy overhead
                frame = np.array(pil_img)
            
        out.write(frame)
        if frame_count % 30 == 0:
            print(f"   Tiến độ Render: {frame_count}/{total_frames} frames")
            
    cap.release()
    out.release()
    print("✅ Đã xử lý xong Hình ảnh (OpenCV)")
    
    # 3. XỬ LÝ ÂM THANH, TỐC ĐỘ, VÀ METADATA BẰNG FFmpeg
    print("🎵 Đang ghép Âm thanh, căn chỉnh tốc độ và xuất Video final...")
    try:
        if os.path.exists(final_output):
            os.remove(final_output)
            
        has_audio = has_audio_track(input_path)
        metadata_opts = ["-map_metadata", "-1"] if strip_metadata else []
        
        import platform
        codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
        preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "superfast", "-crf", "20"]

        if speed != 1.0:
            if has_audio:
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-i", input_path,
                    "-filter_complex", f"[0:v]setpts=PTS/{speed}[v];[1:a]atempo={speed}[a]",
                    "-map", "[v]",
                    "-map", "[a]",
                    "-c:v", codec
                ] + preset_args + [
                    "-c:a", "aac"
                ] + metadata_opts + [final_output]
            else:
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-filter_complex", f"[0:v]setpts=PTS/{speed}[v]",
                    "-map", "[v]",
                    "-c:v", codec
                ] + preset_args + metadata_opts + [final_output]
        else:
            if has_audio:
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-i", input_path,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0?",
                    "-shortest"
                ] + metadata_opts + [final_output]
            else:
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-c:v", "copy"
                ] + metadata_opts + [final_output]
                
        try:
            res = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Fallback to libx264 if hardware encoder fails
            if res.returncode != 0 and speed != 1.0 and codec == "h264_videotoolbox":
                fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in ffmpeg_cmd]
                try:
                    idx_codec = fallback_cmd.index("libx264")
                    fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "superfast", "-crf", "20"] + fallback_cmd[idx_codec+1:]
                except ValueError:
                    pass
                res = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            elif res.returncode != 0:
                raise RuntimeError(f"FFmpeg render failed: {res.stderr.decode('utf-8', errors='ignore')}")
        except Exception as run_err:
            raise run_err
        print(f"🎉 RENDER HOÀN TẤT VIDEO CHÍNH: {final_output}")
        
        # 4. CHIA ĐÔI VIDEO (NẾU ĐƯỢC CHỌN)
        if split_video:
            print("✂️ Đang tiến hành cắt đôi video thành Phần 1 & Phần 2...")
            try:
                cap_duration = cv2.VideoCapture(final_output)
                out_fps = cap_duration.get(cv2.CAP_PROP_FPS)
                out_total_frames = cap_duration.get(cv2.CAP_PROP_FRAME_COUNT)
                cap_duration.release()
                
                if out_fps > 0:
                    duration = out_total_frames / out_fps
                    half_duration = duration / 2
                    
                    # Lấy tên phim không chứa MANUAL_EDIT_
                    base_name = filename.replace("MANUAL_EDIT_", "")
                    base_name = os.path.splitext(base_name)[0]
                    
                    split_folder = os.path.join(output_dir, base_name)
                    os.makedirs(split_folder, exist_ok=True)
                    
                    part1_path = os.path.join(split_folder, f"Phần 1 - {base_name}.mp4")
                    part2_path = os.path.join(split_folder, f"Phần 2 - {base_name}.mp4")
                    
                    cmd_part1 = [
                        "ffmpeg", "-y",
                        "-i", final_output,
                        "-ss", "0",
                        "-to", f"{half_duration:.3f}",
                        "-c", "copy"
                    ] + metadata_opts + [part1_path]
                    
                    cmd_part2 = [
                        "ffmpeg", "-y",
                        "-i", final_output,
                        "-ss", f"{half_duration:.3f}",
                        "-to", f"{duration:.3f}",
                        "-c", "copy"
                    ] + metadata_opts + [part2_path]
                    
                    subprocess.run(cmd_part1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    subprocess.run(cmd_part2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    print(f"✅ Đã chia đôi video thành công trong thư mục: {split_folder}")
            except Exception as split_err:
                print(f"⚠️ Lỗi khi cắt đôi video: {split_err}")
                
    except Exception as e:
        print(f"❌ Lỗi ghép FFmpeg: {e}")
        # Nếu FFmpeg lỗi, fallback xài luôn file temp (không có tiếng)
        if os.path.exists(temp_video):
            os.rename(temp_video, final_output)
            
    # Dọn dẹp
    if os.path.exists(temp_video) and os.path.exists(final_output):
        os.remove(temp_video)
        
    return final_output