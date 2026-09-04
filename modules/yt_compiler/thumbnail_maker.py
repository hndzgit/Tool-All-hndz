import os
import json
import random
import subprocess
from PIL import Image, ImageDraw, ImageFont

def get_video_info(file_path):
    """Get video duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,duration,codec_type",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(res.stdout)
        info = {"width": 1920, "height": 1080, "duration": 0.0, "has_audio": False}
        streams = data.get("streams", [])
        for s in streams:
            codec_type = s.get("codec_type")
            if codec_type == "video":
                info["width"] = int(s.get("width", 1920))
                info["height"] = int(s.get("height", 1080))
                if "duration" in s:
                    try: info["duration"] = float(s["duration"])
                    except: pass
            elif codec_type == "audio":
                info["has_audio"] = True
        if info["duration"] == 0.0 and "format" in data:
            try: info["duration"] = float(data["format"].get("duration", 0.0))
            except: pass
        return info
    except Exception as e:
        print(f"Error reading video info: {e}")
        return {"width": 1920, "height": 1080, "duration": 0.0, "has_audio": False}

def create_collage_thumbnail(video_list, title_text, output_thumb_path, 
                             banner_border_color="#FE640B", text_fill_color="#FFFF00", text_stroke_color="#000000",
                             frame_percentages=[15.0, 33.0, 85.0], font_size=44, banner_bg_color="white",
                             auto_scan_food=True):
    import re
    
    def resolve_color(color_str, fallback):
        if not color_str:
            return fallback
        match = re.search(r'#[0-9A-Fa-f]{6}', color_str)
        if match:
            return match.group(0)
        color_lower = color_str.lower()
        if "white" in color_lower or "trắng" in color_lower:
            return "white"
        if "black" in color_lower or "đen" in color_lower:
            return "black"
        if "transparent" in color_lower or "trong suốt" in color_lower:
            return "#00000000"
        return color_str

    banner_border_color = resolve_color(banner_border_color, "#FE640B")
    text_fill_color = resolve_color(text_fill_color, "#FFFF00")
    banner_bg_color = resolve_color(banner_bg_color, "white")

    frames = []
    temp_files = []
    
    try:
        # Chọn ngẫu nhiên 3 video (hoặc trùng lặp nếu có ít hơn 3 video) để lấy 1 frame từ mỗi video
        chosen_videos = []
        if len(video_list) >= 3:
            chosen_videos = random.sample(video_list, 3)
        else:
            temp_list = list(video_list)
            while len(temp_list) < 3:
                temp_list.append(temp_list[0])
            chosen_videos = temp_list[:3]
            
        sources = []
        for idx, v_path in enumerate(chosen_videos):
            info = get_video_info(v_path)
            dur = info["duration"] if info["duration"] > 0 else 30.0
            
            if auto_scan_food:
                pct = find_best_food_frame_percentage(v_path, default_pct=frame_percentages[idx])
            else:
                pct = frame_percentages[idx]
                
            sources.append((v_path, dur * (pct / 100.0)))
                
        # Thực hiện trích xuất frame bằng FFmpeg
        for idx, (v_path, ss_sec) in enumerate(sources):
            temp_img_path = f"{output_thumb_path}_temp_f{idx}.jpg"
            temp_files.append(temp_img_path)
            
            # Format time string hh:mm:ss.xxx
            h = int(ss_sec // 3600)
            m = int((ss_sec % 3600) // 60)
            s = ss_sec % 60
            time_str = f"{h:02d}:{m:02d}:{s:06.3f}"
            
            cmd = [
                "ffmpeg", "-y", "-ss", time_str, "-i", v_path,
                "-frames:v", "1", "-q:v", "2", temp_img_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(temp_img_path):
                frames.append(temp_img_path)
                
        # Nếu trích xuất không đủ 3 frame, lấy lặp lại frame sẵn có
        if not frames:
            return False
            
        while len(frames) < 3:
            frames.append(frames[0])
            
        # 2. Tạo hình ảnh collage 1280x720 bằng Pillow
        canvas = Image.new("RGB", (1280, 720))
        
        # 3 panel xắp xếp ngang: panel1(426x720), panel2(428x720), panel3(426x720)
        panel_dims = [(0, 426), (426, 428), (854, 426)]
        
        for i in range(3):
            p_x, p_w = panel_dims[i]
            with Image.open(frames[i]) as img:
                # scale and crop to fill
                img_w, img_h = img.size
                scale = max(p_w / img_w, 720 / img_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Crop center
                left = (new_w - p_w) / 2
                top = (new_h - 720) / 2
                right = left + p_w
                bottom = top + 720
                cropped = img_resized.crop((left, top, right, bottom))
                
                # Paste on canvas
                canvas.paste(cropped, (p_x, 0))
                
        # 3. Vẽ Banner Trắng và Chèn Chữ Tiêu Đề
        draw = ImageDraw.Draw(canvas)
        
        # Chiều rộng banner: 90% chiều rộng ảnh = 1152px
        banner_w = 1152
        banner_h = 100
        banner_x = (1280 - banner_w) // 2
        banner_y = 720 - banner_h - 60 # Cách đáy 60px
        
        # Vẽ banner nền bo góc mềm mại
        try:
            draw.rounded_rectangle(
                [(banner_x, banner_y), (banner_x + banner_w, banner_y + banner_h)],
                radius=15, fill=banner_bg_color, outline=banner_border_color, width=6
            )
        except AttributeError:
            draw.rectangle(
                [(banner_x, banner_y), (banner_x + banner_w, banner_y + banner_h)],
                fill=banner_bg_color, outline=banner_border_color, width=6
            )
            
        # Load Roboto Bold or BeVietnam Pro if available in automation asset paths
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        roboto_path = os.path.join(current_dir, "automation", "assets", "Roboto-Bold.ttf")
        
        font_paths = [
            roboto_path,
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "Arial"
        ]
        
        font = None
        for p in font_paths:
            try:
                font = ImageFont.truetype(p, font_size)
                break
            except:
                pass
                
        if font is None:
            font = ImageFont.load_default()
            
        # Căn giữa chữ trong banner
        try:
            bbox = draw.textbbox((0, 0), title_text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except:
            text_w, text_h = draw.textsize(title_text, font=font)
            
        tx = banner_x + (banner_w - text_w) // 2
        ty = banner_y + (banner_h - text_h) // 2 - 4
        
        # Vẽ outline đỏ sẫm
        stroke_width = 4
        draw.text((tx, ty), title_text, font=font, fill=text_fill_color,
                  stroke_width=stroke_width, stroke_fill=text_stroke_color)
                  
        # Lưu Thumbnail
        canvas.save(output_thumb_path, "JPEG", quality=95)
        
        # Dọn dẹp tệp tạm
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                
        return True
    except Exception as e:
        print(f"Error creating collage thumbnail: {e}")
        for f in temp_files:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
        return False

def find_best_food_frame_percentage(video_path, default_pct=15.0):
    """
    Scans candidate positions in the video and returns the percentage of the frame
    with the highest visual richness (good saturation and visibility). Runs silently.
    """
    try:
        info = get_video_info(video_path)
        dur = info["duration"]
        if dur <= 0:
            return default_pct
            
        import tempfile
        import subprocess
        from PIL import Image
        
        candidates = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        best_pct = default_pct
        max_score = -1.0
        
        for pct in candidates:
            ss_sec = dur * (pct / 100.0)
            
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_img_path = tmp.name
            try:
                h = int(ss_sec // 3600)
                m = int((ss_sec % 3600) // 60)
                s = ss_sec % 60
                time_str = f"{h:02d}:{m:02d}:{s:06.3f}"
                
                cmd = [
                    "ffmpeg", "-y", "-ss", time_str, "-i", video_path,
                    "-frames:v", "1", "-s", "160x90", "-q:v", "5", tmp_img_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if os.path.exists(tmp_img_path):
                    with Image.open(tmp_img_path) as img:
                        hsv = img.convert("HSV")
                        width, height = hsv.size
                        pixels = hsv.getdata()
                        
                        rich_pixels = 0
                        for r_h, r_s, r_v in pixels:
                            # Rich/detailed scenes:
                            # Saturation >= 55 (color richness)
                            # Brightness between 50 and 230 (well-exposed)
                            if r_s >= 55 and 50 <= r_v <= 230:
                                rich_pixels += 1
                                
                        score = rich_pixels / float(width * height)
                        if score > max_score:
                            max_score = score
                            best_pct = pct
            except:
                pass
            finally:
                if os.path.exists(tmp_img_path):
                    try: os.remove(tmp_img_path)
                    except: pass
                    
        import random
        offset = random.uniform(-4.0, 4.0)
        best_pct = max(5.0, min(95.0, best_pct + offset))
        return best_pct
    except Exception:
        return default_pct
